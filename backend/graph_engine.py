# graph_engine.py
# ProofGraph core reasoning pipeline.
# 3 parallel TEE nodes + 1 synthesis node.
# No knowledge base injection — LLM answers everything directly from OG system context.

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
from og_knowledge import OG_SYSTEM_CONTEXT, _STOP
import database as db


def _build_tasks(question: str) -> list:
    """
    3 tasks with genuinely different angles on the question.
    No shared context — each node reasons independently from its role.
    """
    q = question.strip().rstrip("?")

    return [
        {
            "type":  "analysis",
            "label": "Core Analysis",
            "role":  "Technical analyst. Explain mechanisms, how it works, and the architecture.",
            "prompt": (
                f"Question: {q}\n\n"
                "Explain the core mechanisms and how this works technically. "
                "What is it, how does it function, what makes it unique? "
                "Be specific and expert-level. Under 160 words."
            ),
        },
        {
            "type":  "evidence",
            "label": "Evidence & Context",
            "role":  "Research analyst. Provide facts, real examples, data, and real-world context.",
            "prompt": (
                f"Question: {q}\n\n"
                "Provide the key facts, real-world evidence, and concrete examples. "
                "What problems does this solve? What are the risks or limitations? "
                "Be factual and grounded. Under 160 words."
            ),
        },
        {
            "type":  "conclusion",
            "label": "Key Takeaways",
            "role":  "Strategic advisor. Give practical implications and actionable insights.",
            "prompt": (
                f"Question: {q}\n\n"
                "What are the practical implications and bottom line? "
                "What should someone do with this information? "
                "What is the impact? Be direct and actionable. Under 160 words."
            ),
        },
    ]


def _node_system(role: str, twin_persona: str) -> str:
    return (
        f"{OG_SYSTEM_CONTEXT}\n\n"
        f"YOUR ROLE: {role}\n\n"
        f"{twin_persona}\n\n"
        "Answer the question directly from your role's perspective. "
        "Under 160 words. No filler."
    )


SYNTHESIS_SYSTEM = (
    f"{OG_SYSTEM_CONTEXT}\n\n"
    "Synthesize the 3 expert analyses into one clear final answer.\n\n"
    "Format:\n"
    "2-sentence direct answer.\n"
    "3 bullet points of key insights.\n"
    "1 bottom-line sentence.\n\n"
    "Stay on the topic of the question. Under 220 words."
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

        return await self._pipeline(question, session_id, wallet_address, send)

    async def _pipeline(self, question, session_id, wallet_address, send):

        keywords = [w for w in question.lower().split() if w not in _STOP][:6]

        # Check graph for reusable nodes from previous sessions
        existing = await db.search_nodes_by_topic(keywords, limit=2)
        for en in existing:
            await db.increment_citation(en["id"])
            await send(WSEventType.GRAPH_REUSE, {
                "node_id": en["id"],
                "label":   en["label"],
                "message": f"Reusing verified node: {en['label']}",
            })

        # Build 3 independent tasks — no shared KB context
        tasks = _build_tasks(question)

        # Route each task to the most relevant Digital Twin
        twins = [
            self.router.select_twin(t["label"], t["prompt"], t["type"])
            for t in tasks
        ]

        twin_names = list(dict.fromkeys(t["name"] for t in twins))
        await send(WSEventType.SESSION_START, {
            "session_id": session_id,
            "question":   question,
            "message":    f"Consulting: {', '.join(twin_names)} — running in parallel...",
        })

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

        async def run_node(i: int, task: dict, twin: dict, node_id: str):
            system_prompt = _node_system(
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

        # Final synthesis
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
