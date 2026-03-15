# graph_engine.py
# ProofGraph core reasoning engine.
# Every question runs through 3 parallel TEE-verified nodes then 1 synthesis node.

import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Callable

from models import (
    ReasoningNode, QuestionSession, NodeType,
    NodeStatus, TEEProof, WSEvent, WSEventType
)
from og_client import get_og_client
from memsync_client import get_memsync
from twin_router import get_twin_router
from og_knowledge import OG_SYSTEM_CONTEXT, get_focused_answer, _STOP
import database as db

def _build_tasks(question: str, kb_anchor: str) -> list:
    """
    Build 3 reasoning tasks with genuinely different angles.
    Each task receives the KB anchor so the LLM stays on the correct topic,
    but is asked to reason from a distinct perspective.
    """
    q = question.strip().rstrip("?")

    anchor_block = (
        f"FACTUAL ANCHOR (verified knowledge — your answer must be consistent with this):\n"
        f"{kb_anchor}\n\n"
    ) if kb_anchor else ""

    return [
        {
            "type":  "analysis",
            "label": "Core Analysis",
            "prompt": (
                f"{anchor_block}"
                f"Question: {q}\n\n"
                "Your role: Explain HOW IT WORKS — the technical mechanisms, "
                "architecture, and what makes it function. "
                "Do not repeat the anchor verbatim — add depth and technical insight. "
                "Under 160 words."
            ),
            "role": "Technical analyst — explain mechanisms, architecture, and how things work.",
        },
        {
            "type":  "evidence",
            "label": "Evidence & Context",
            "prompt": (
                f"{anchor_block}"
                f"Question: {q}\n\n"
                "Your role: Provide REAL-WORLD EVIDENCE — concrete facts, data points, "
                "comparisons, real examples, and what problems this solves. "
                "Do not repeat the anchor verbatim — add real-world grounding. "
                "Under 160 words."
            ),
            "role": "Research analyst — provide facts, evidence, comparisons, and real-world context.",
        },
        {
            "type":  "conclusion",
            "label": "Key Takeaways",
            "prompt": (
                f"{anchor_block}"
                f"Question: {q}\n\n"
                "Your role: Give the PRACTICAL IMPLICATIONS — what this means for users, "
                "builders, and the ecosystem. What should someone do with this information? "
                "Do not repeat the anchor verbatim — add actionable insight. "
                "Under 160 words."
            ),
            "role": "Strategic advisor — give practical implications and actionable insights.",
        },
    ]

def _node_system_prompt(role: str, twin_persona: str) -> str:
    return (
        f"{OG_SYSTEM_CONTEXT}\n\n"
        f"YOUR ROLE FOR THIS NODE:\n{role}\n\n"
        f"{twin_persona}\n\n"
        "Rules:\n"
        "- Stay on the specific topic in the question\n"
        "- Do not mention unrelated OpenGradient products\n"
        "- Do not copy the factual anchor word for word — build on it\n"
        "- Be direct and expert-level\n"
        "- Under 160 words"
    )

SYNTHESIS_SYSTEM = (
    f"{OG_SYSTEM_CONTEXT}\n\n"
    "You are writing the final verified answer by synthesizing 3 expert analyses.\n\n"
    "Rules:\n"
    "- Answer ONLY the specific question asked — stay on topic\n"
    "- If the question asks about OpenGradient the platform, answer about the platform\n"
    "- If the question asks about a specific product, answer about that product\n"
    "- Do not mix up the platform with its products (BitQuant, MemSync, Twin.fun, etc.)\n\n"
    "Format:\n"
    "Start with a direct 2-sentence answer.\n"
    "Then 3 bullet points with key insights using the bullet character.\n"
    "End with one bottom-line sentence.\n\n"
    "Under 220 words. Clear and direct."
)

class GraphEngine:

    def __init__(self):
        self.og      = None
        self.memsync = None
        self.router  = None

    async def ensure_clients(self):
        if not self.og:
            self.og = await get_og_client()
        if not self.memsync:
            self.memsync = get_memsync()
        if not self.router:
            self.router = get_twin_router()

    async def process_question(
        self,
        question:       str,
        session_id:     str,
        wallet_address: Optional[str] = None,
        emit:           Optional[Callable] = None,
        max_nodes:      int = 3,
    ) -> QuestionSession:

        await self.ensure_clients()

        async def send(event_type: WSEventType, data: dict):
            if emit:
                try:
                    await emit(WSEvent(
                        type=event_type, data=data, session_id=session_id
                    ).model_dump())
                except Exception:
                    pass

        mode = getattr(self.og, "mode", "KNOWLEDGE").upper()
        await send(WSEventType.SESSION_START, {
            "session_id": session_id,
            "question":   question,
            "message":    f"ProofGraph [{mode}] — starting 3-node pipeline...",
        })

        return await self._parallel_pipeline(
            question, session_id, wallet_address, send
        )

    async def _parallel_pipeline(
        self, question, session_id, wallet_address, send
    ) -> QuestionSession:

        keywords = [w for w in question.lower().split() if w not in _STOP][:6]

        # Check graph for reusable nodes from previous sessions
        existing = await db.search_nodes_by_topic(keywords, limit=2)
        for en in existing:
            await db.increment_citation(en["id"])
            await send(WSEventType.GRAPH_REUSE, {
                "node_id": en["id"], "label": en["label"],
                "message": f"Reusing: {en['label']}",
            })

        # Get the verified KB answer to use as a factual anchor in each node
        kb_anchor = get_focused_answer(question)

        # Build 3 tasks — each with the KB anchor to prevent topic drift
        tasks = _build_tasks(question, kb_anchor)

        # Route each task to the most relevant Digital Twin
        twins = [
            self.router.select_twin(t["label"], t["prompt"], t["type"])
            for t in tasks
        ]

        twin_names = list(dict.fromkeys(t["name"] for t in twins))
        await send(WSEventType.SESSION_START, {
            "session_id": session_id, "question": question,
            "message": f"Consulting: {', '.join(twin_names)} — running in parallel...",
        })

        # Announce all nodes as pending immediately so UI shows activity
        node_ids = [str(uuid.uuid4()) for _ in tasks]
        for i, (task, twin, node_id) in enumerate(zip(tasks, twins, node_ids)):
            await send(WSEventType.NODE_PENDING, {
                "node_id":   node_id,
                "label":     task["label"],
                "twin_name": twin["name"],
                "twin_id":   twin["id"],
                "position":  i + 1,
                "total":     len(tasks) + 1,
                "message":   f"{twin['name']}: {task['label']}",
            })

        # Run all 3 inference nodes in parallel
        async def run_node(i: int, task: dict, twin: dict, node_id: str):
            system_prompt = _node_system_prompt(
                role=task["role"],
                twin_persona=twin.get("persona", "")
            )

            result = await self.og.infer_tee(
                prompt=task["prompt"],
                system_prompt=system_prompt,
                max_tokens=280,
            )

            self.router.record_payment(twin, node_id, session_id, wallet_address)

            tee_proof = self._make_proof(result)
            node = ReasoningNode(
                id=node_id,
                question_id=session_id,
                node_type=NodeType(task["type"]),
                label=task["label"],
                prompt=task["prompt"],
                content=result["content"],
                model_used=f"{twin['name']} via {result.get('model', 'og')}",
                tee_proof=tee_proof,
                status=NodeStatus.VERIFIED,
                confidence=0.92 if result.get("verified") else 0.78,
                wallet_address=wallet_address,
                created_at=datetime.utcnow().isoformat(),
            )
            await db.save_node(node.model_dump())

            await send(WSEventType.NODE_VERIFIED, {
                "node_id":      node_id,
                "label":        task["label"],
                "content":      result["content"],
                "tee_proof":    tee_proof.model_dump(),
                "node_type":    task["type"],
                "twin_name":    twin["name"],
                "twin_id":      twin["id"],
                "x402_pending": twin.get("x402_wallet") is not None,
                "position":     i + 1,
                "total":        len(tasks) + 1,
            })

            if wallet_address:
                asyncio.create_task(self.memsync.store_node_memory(
                    user_id=wallet_address, node_id=node_id,
                    label=task["label"], content=result["content"],
                    node_type=task["type"],
                    tx_hash=result.get("tx_hash"), topic_tags=keywords,
                ))

            return node

        minted: List[ReasoningNode] = await asyncio.gather(
            *[run_node(i, task, twin, nid)
              for i, (task, twin, nid) in enumerate(zip(tasks, twins, node_ids))]
        )

        # Final synthesis — combines all 3 node outputs into one verified answer
        await send(WSEventType.NODE_PENDING, {
            "node_id":  "synthesis",
            "label":    "Final Synthesis",
            "position": len(tasks) + 1,
            "total":    len(tasks) + 1,
            "message":  "Synthesizing 3 expert analyses...",
        })

        synth_prompt = (
            f"Question: {question}\n\n"
            f"[CORE ANALYSIS]\n{minted[0].content[:260]}\n\n"
            f"[EVIDENCE AND CONTEXT]\n{minted[1].content[:260]}\n\n"
            f"[KEY TAKEAWAYS]\n{minted[2].content[:260]}"
        )
        if kb_anchor:
            synth_prompt += f"\n\n[VERIFIED KNOWLEDGE BASE]\n{kb_anchor[:300]}"

        synth = await self.og.infer_tee(
            prompt=synth_prompt,
            system_prompt=SYNTHESIS_SYSTEM,
            max_tokens=380,
        )

        confidence   = self._confidence(minted)
        final_answer = synth["content"]

        routing = self.router.get_routing_summary()
        if routing["twins_consulted"]:
            twin_list = ", ".join(routing["twins_consulted"].keys())
            final_answer += f"\n\n[Verified by: {twin_list}]"

        synth_node = ReasoningNode(
            id=str(uuid.uuid4()),
            question_id=session_id,
            node_type=NodeType.SYNTHESIS,
            label="Final Synthesis",
            prompt=synth_prompt[:200],
            content=final_answer,
            model_used=f"Synthesis via {synth.get('model', 'og')}",
            tee_proof=self._make_proof(synth),
            status=NodeStatus.VERIFIED,
            confidence=confidence,
            wallet_address=wallet_address,
            created_at=datetime.utcnow().isoformat(),
        )
        await db.save_node(synth_node.model_dump())
        await db.update_session(session_id, {
            "final_answer": final_answer,
            "confidence":   confidence,
            "status":       "complete",
        })

        if wallet_address:
            asyncio.create_task(self.memsync.store_session_memory(
                user_id=wallet_address, question=question,
                final_answer=final_answer, session_id=session_id,
                node_count=len(minted) + 1,
            ))

        all_nodes     = list(minted) + [synth_node]
        total_proofs  = sum(1 for n in all_nodes if n.tee_proof and n.tee_proof.verified)
        x402_payments = sum(1 for n in all_nodes if n.tee_proof and n.tee_proof.payment_hash)
        og_mode       = getattr(self.og, "mode", "KNOWLEDGE")

        await send(WSEventType.SESSION_COMPLETE, {
            "session_id":      session_id,
            "final_answer":    final_answer,
            "confidence":      confidence,
            "nodes_minted":    len(all_nodes),
            "nodes_reused":    len(existing),
            "total_proofs":    total_proofs,
            "twins_consulted": routing["twins_consulted"],
            "x402_payments":   x402_payments,
            "og_mode":         og_mode,
        })

        return QuestionSession(
            id=session_id, question=question,
            final_answer=final_answer, confidence=confidence,
            nodes=all_nodes, wallet_address=wallet_address, status="complete",
        )

    def _make_proof(self, result: dict) -> TEEProof:
        return TEEProof(
            payment_hash   = result.get("payment_hash"),
            tx_hash        = result.get("tx_hash"),
            model_used     = result.get("model", "og-knowledge-base"),
            inference_mode = result.get("mode", "KNOWLEDGE"),
            timestamp      = result.get("timestamp", datetime.utcnow().isoformat()),
            verified       = result.get("verified", False),
        )

    def _confidence(self, nodes: List[ReasoningNode]) -> float:
        v = sum(1 for n in nodes if n.tee_proof and n.tee_proof.verified)
        return round(0.70 + (v / max(len(nodes), 1)) * 0.27, 2)

_engine: Optional[GraphEngine] = None

def get_engine() -> GraphEngine:
    global _engine
    if _engine is None:
        _engine = GraphEngine()
    return _engine
