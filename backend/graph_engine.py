# graph_engine.py
# ProofGraph reasoning pipeline.
# 3 parallel TEE nodes answering from distinct roles, then 1 synthesis node.
# The LLM answers everything directly — no knowledge base injection.

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
from og_knowledge import OG_SYSTEM_CONTEXT
import database as db

STOP_WORDS = {
    "what","is","are","the","a","an","how","why","who","does","do","can",
    "about","tell","me","of","in","on","to","for","and","or","this","that",
    "it","its","with","from","by","at","was","were","has","have","had",
    "will","would","could","should","give","show","explain","describe",
}

NODE_SYSTEM = (
    f"{OG_SYSTEM_CONTEXT}\n\n"
    "YOUR ROLE FOR THIS REASONING NODE:\n{{role}}\n\n"
    "{{persona}}\n\n"
    "Answer the question from your specific role. "
    "Be direct, accurate, and expert-level. Under 160 words."
)

SYNTHESIS_SYSTEM = (
    f"{OG_SYSTEM_CONTEXT}\n\n"
    "Synthesize 3 expert analyses into one clear final answer.\n\n"
    "Format:\n"
    "- 2 sentences direct answer\n"
    "- 3 bullet points of key insights\n"
    "- 1 bottom-line sentence\n\n"
    "Stay precisely on the topic of the question. Under 220 words."
)

ROLES = [
    {
        "type":   "analysis",
        "label":  "Core Analysis",
        "role":   "Technical analyst — explain the core mechanisms, how it works, and why.",
        "prompt": (
            "Question: {q}\n\n"
            "Explain the core mechanisms and how this works technically. "
            "What is it, how does it function, what makes it unique or important? "
            "Be specific. Under 160 words."
        ),
    },
    {
        "type":   "evidence",
        "label":  "Evidence & Context",
        "role":   "Research analyst — provide facts, real examples, data, and real-world context.",
        "prompt": (
            "Question: {q}\n\n"
            "Provide key facts, real-world evidence, and concrete examples. "
            "What problems does this solve? What are the risks or limitations? "
            "Be factual. Under 160 words."
        ),
    },
    {
        "type":   "conclusion",
        "label":  "Key Takeaways",
        "role":   "Strategic advisor — give practical implications and actionable insights.",
        "prompt": (
            "Question: {q}\n\n"
            "What are the practical implications and the bottom line? "
            "What should someone do with this information? "
            "What is the real-world impact? Be direct. Under 160 words."
        ),
    },
]


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

        keywords = [w for w in question.lower().split() if w not in STOP_WORDS][:6]

        # Check for reusable verified nodes from previous sessions
        existing = await db.search_nodes_by_topic(keywords, limit=2)
        for en in existing:
            await db.increment_citation(en["id"])
            await send(WSEventType.GRAPH_REUSE, {
                "node_id": en["id"],
                "label":   en["label"],
                "message": f"Reusing verified node: {en['label']}",
            })

        # Build tasks — question substituted directly, no KB injection
        tasks = [
            {**r, "prompt": r["prompt"].format(q=question)}
            for r in ROLES
        ]

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

        async def run_node(i: int, task: dict, twin: dict, node_id: str) -> ReasoningNode:
            system_prompt = NODE_SYSTEM.replace(
                "{{role}}", task["role"]
            ).replace(
                "{{persona}}", twin.get("persona", "")
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
                    user_id=wallet_address,
                    node_id=node_id,
                    label=task["label"],
                    content=result["content"],
                    node_type=task["type"],
                    tx_hash=result.get("tx_hash"),
                    topic_tags=keywords,
                ))

            return node

        minted: List[ReasoningNode] = await asyncio.gather(
            *[run_node(i, t, tw, nid)
              for i, (t, tw, nid) in enumerate(zip(tasks, twins, node_ids))]
        )

        # Synthesis node
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
                user_id=wallet_address,
                question=question,
                final_answer=final_answer,
                session_id=session_id,
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
            model_used     = result.get("model", "og"),
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
