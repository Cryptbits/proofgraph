# ================================================================
# graph_engine.py - ProofGraph Core Reasoning Engine
#
# This is the brain:
# 1. Receives a question
# 2. Searches existing graph for reusable verified nodes
# 3. Decomposes into reasoning tasks via OG TEE LLM
# 4. Mints each reasoning step as a verified node
# 5. Synthesizes final answer
# 6. Stores in DB + MemSync
# ================================================================

import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator, Callable

from models import (
    ReasoningNode, QuestionSession, NodeType,
    NodeStatus, TEEProof, WSEvent, WSEventType
)
from og_client import get_og_client
from memsync_client import get_memsync
import database as db


# ─── System prompts ───────────────────────────────────────────

DECOMPOSE_SYSTEM = """You are a reasoning decomposition engine for ProofGraph — 
a decentralized verifiable intelligence system built on OpenGradient.

Your job: Break a question into exactly 4-6 logical reasoning sub-tasks.
Each sub-task becomes a verified node in the knowledge graph.

Respond ONLY with valid JSON in this exact format:
{
  "decomposition": [
    {
      "type": "definition|analysis|evidence|synthesis|conclusion",
      "label": "Short title for this reasoning step",
      "prompt": "The specific question/task for this reasoning step"
    }
  ],
  "keywords": ["keyword1", "keyword2", "keyword3"]
}

Node types:
- definition: Establish foundational concepts
- analysis: Examine mechanisms or relationships  
- evidence: Gather supporting data/facts
- synthesis: Connect multiple concepts
- conclusion: Draw final inference

Keep labels concise (4-7 words max). Make prompts specific and answerable."""


REASONING_SYSTEM = """You are a verifiable reasoning engine running inside an 
OpenGradient Trusted Execution Environment (TEE). 

Your outputs are cryptographically attested on-chain. Be precise, factual, 
and analytical. Cite your reasoning steps clearly. 
Keep responses focused and under 300 words.

This is node analysis for the ProofGraph decentralized intelligence network."""


SYNTHESIS_SYSTEM = """You are the synthesis layer of ProofGraph — a decentralized 
verifiable intelligence system.

You receive verified reasoning nodes (each cryptographically attested via 
OpenGradient TEE) and must synthesize them into a final coherent answer.

Structure your response as:
1. A clear direct answer (2-3 sentences)
2. Key insights from the reasoning graph (3-5 bullet points)  
3. Confidence assessment and limitations

Keep total response under 400 words. This synthesis will be the final verified 
node in the reasoning graph."""


CONFIDENCE_SYSTEM = """Rate the confidence of a reasoning conclusion on a scale 
of 0.0 to 1.0 based on the reasoning chain provided.

Respond with ONLY a JSON object: {"confidence": 0.85, "reasoning": "brief explanation"}"""


class GraphEngine:
    """
    Core engine that orchestrates the full ProofGraph reasoning pipeline.
    """

    def __init__(self):
        self.og    = None
        self.memsync = None

    async def ensure_clients(self):
        if not self.og:
            self.og = await get_og_client()
        if not self.memsync:
            self.memsync = get_memsync()

    # ─── Main Entry Point ─────────────────────────────────────
    async def process_question(
        self,
        question:       str,
        session_id:     str,
        wallet_address: Optional[str] = None,
        emit:           Optional[Callable] = None,
        max_nodes:      int = 6,
    ) -> QuestionSession:
        """
        Full pipeline: decompose → infer → mint → synthesize → store.
        `emit` is an async callback for WebSocket streaming.
        """
        await self.ensure_clients()

        async def send(event_type: WSEventType, data: dict):
            if emit:
                event = WSEvent(type=event_type, data=data, session_id=session_id)
                await emit(event.model_dump())

        # ── Step 1: Notify session start ──
        await send(WSEventType.SESSION_START, {
            "session_id": session_id,
            "question":   question,
            "message":    "Initializing verifiable reasoning pipeline..."
        })

        # ── Step 2: Search existing graph for reusable nodes ──
        await send(WSEventType.SESSION_START, {
            "session_id": session_id,
            "question":   question,
            "message":    "Searching knowledge graph for existing verified nodes..."
        })

        # ── Step 3: Decompose question ──
        decomposition = await self._decompose_question(question)
        keywords      = decomposition.get("keywords", [])
        tasks         = decomposition.get("decomposition", [])[:max_nodes]

        # Search graph for reusable nodes
        existing_nodes = await db.search_nodes_by_topic(keywords, limit=3)
        reused = []
        for en in existing_nodes:
            await db.increment_citation(en["id"])
            reused.append(en)
            await send(WSEventType.GRAPH_REUSE, {
                "node_id": en["id"],
                "label":   en["label"],
                "message": f"♻️  Reusing verified node: {en['label']}"
            })

        # ── Step 4: Run reasoning nodes ──
        minted_nodes: List[ReasoningNode] = []
        parent_id = None

        for i, task in enumerate(tasks):
            node_id = str(uuid.uuid4())

            # Notify: node pending
            await send(WSEventType.NODE_PENDING, {
                "node_id":  node_id,
                "label":    task["label"],
                "position": i + 1,
                "total":    len(tasks),
                "message":  f"🔄 Running TEE inference: {task['label']}"
            })

            # Build context from prior nodes
            prior_context = "\n\n".join([
                f"[{n.node_type.upper()}] {n.label}:\n{n.content[:300]}"
                for n in minted_nodes[-2:]
            ])

            # Run TEE inference
            full_prompt = task["prompt"]
            if prior_context:
                full_prompt += f"\n\nContext from prior reasoning:\n{prior_context}"

            result = await self.og.infer_tee(
                prompt=full_prompt,
                system_prompt=REASONING_SYSTEM,
                max_tokens=600,
            )

            # Build TEE proof object
            tee_proof = TEEProof(
                payment_hash=result.get("payment_hash"),
                tx_hash=result.get("tx_hash"),
                model_used=result.get("model", "openai/gpt-4.1"),
                inference_mode=result.get("mode", "TEE"),
                timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
                verified=result.get("verified", False),
            )

            # Create node
            node = ReasoningNode(
                id=node_id,
                question_id=session_id,
                node_type=NodeType(task.get("type", "analysis")),
                label=task["label"],
                prompt=task["prompt"],
                content=result["content"],
                model_used=result.get("model", "openai/gpt-4.1"),
                tee_proof=tee_proof,
                parent_id=parent_id,
                status=NodeStatus.VERIFIED if result.get("verified") else NodeStatus.PENDING,
                confidence=0.8 if result.get("verified") else 0.6,
                wallet_address=wallet_address,
                created_at=datetime.utcnow().isoformat(),
            )

            # Save to DB
            await db.save_node(node.model_dump())

            # Store in MemSync (non-blocking)
            if wallet_address:
                asyncio.create_task(
                    self.memsync.store_node_memory(
                        user_id=wallet_address,
                        node_id=node_id,
                        label=task["label"],
                        content=result["content"],
                        node_type=task.get("type", "analysis"),
                        tx_hash=result.get("tx_hash"),
                        topic_tags=keywords,
                    )
                )

            minted_nodes.append(node)
            parent_id = node_id

            # Notify: node verified
            await send(WSEventType.NODE_VERIFIED, {
                "node_id":      node_id,
                "label":        task["label"],
                "content":      result["content"][:200] + "...",
                "tee_proof":    tee_proof.model_dump(),
                "node_type":    task.get("type", "analysis"),
                "position":     i + 1,
                "total":        len(tasks),
            })

            # Small delay between nodes for visual effect + rate limiting
            await asyncio.sleep(0.5)

        # ── Step 5: Synthesize final answer ──
        await send(WSEventType.NODE_PENDING, {
            "node_id":  "synthesis",
            "label":    "Synthesizing verified reasoning...",
            "position": len(tasks) + 1,
            "total":    len(tasks) + 1,
            "message":  "🧠 Synthesizing final answer from verified nodes..."
        })

        synthesis_prompt = f"""
Original Question: {question}

Verified Reasoning Nodes:
{self._format_nodes_for_synthesis(minted_nodes)}

Reused Graph Nodes: {len(reused)} existing verified nodes cited.

Please synthesize a final comprehensive answer.
"""

        synthesis_result = await self.og.infer_tee(
            prompt=synthesis_prompt,
            system_prompt=SYNTHESIS_SYSTEM,
            max_tokens=800,
        )

        final_answer = synthesis_result["content"]

        # ── Step 6: Calculate confidence ──
        confidence = await self._calculate_confidence(question, final_answer, minted_nodes)

        # ── Step 7: Save synthesis node ──
        synthesis_node = ReasoningNode(
            id=str(uuid.uuid4()),
            question_id=session_id,
            node_type=NodeType.SYNTHESIS,
            label="Final Synthesis",
            prompt=synthesis_prompt[:200],
            content=final_answer,
            model_used=synthesis_result.get("model", "openai/gpt-4.1"),
            tee_proof=TEEProof(
                payment_hash=synthesis_result.get("payment_hash"),
                tx_hash=synthesis_result.get("tx_hash"),
                model_used=synthesis_result.get("model", "openai/gpt-4.1"),
                inference_mode=synthesis_result.get("mode", "TEE"),
                timestamp=datetime.utcnow().isoformat(),
                verified=synthesis_result.get("verified", False),
            ),
            parent_id=parent_id,
            status=NodeStatus.VERIFIED,
            confidence=confidence,
            wallet_address=wallet_address,
        )
        await db.save_node(synthesis_node.model_dump())
        minted_nodes.append(synthesis_node)

        # ── Step 8: Update session ──
        await db.update_session(session_id, {
            "final_answer": final_answer,
            "confidence":   confidence,
            "status":       "complete",
        })

        # Store session in MemSync
        if wallet_address:
            asyncio.create_task(
                self.memsync.store_session_memory(
                    user_id=wallet_address,
                    question=question,
                    final_answer=final_answer,
                    session_id=session_id,
                    node_count=len(minted_nodes),
                )
            )

        # ── Step 9: Emit completion ──
        await send(WSEventType.SESSION_COMPLETE, {
            "session_id":    session_id,
            "final_answer":  final_answer,
            "confidence":    confidence,
            "nodes_minted":  len(minted_nodes),
            "nodes_reused":  len(reused),
            "total_proofs":  len([n for n in minted_nodes if n.tee_proof and n.tee_proof.verified]),
        })

        session = QuestionSession(
            id=session_id,
            question=question,
            final_answer=final_answer,
            confidence=confidence,
            nodes=minted_nodes,
            wallet_address=wallet_address,
            status="complete",
        )
        return session

    # ─── Helpers ──────────────────────────────────────────────
    async def _decompose_question(self, question: str) -> Dict[str, Any]:
        """Use OG TEE LLM to decompose question into reasoning tasks."""
        result = await self.og.infer_tee(
            prompt=f"Decompose this question into reasoning steps: {question}",
            system_prompt=DECOMPOSE_SYSTEM,
            max_tokens=600,
        )

        content = result["content"]
        try:
            # Strip markdown code blocks if present
            clean = content.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            # Fallback decomposition
            return {
                "decomposition": [
                    {"type": "definition", "label": "Define Core Concepts",    "prompt": f"Define the key concepts in: {question}"},
                    {"type": "analysis",   "label": "Analyze Mechanisms",      "prompt": f"Analyze how the mechanisms work in: {question}"},
                    {"type": "evidence",   "label": "Gather Supporting Facts",  "prompt": f"What evidence or data supports the answer to: {question}"},
                    {"type": "synthesis",  "label": "Connect Key Insights",     "prompt": f"How do these concepts connect to answer: {question}"},
                    {"type": "conclusion", "label": "Draw Conclusion",          "prompt": f"What is the final conclusion for: {question}"},
                ],
                "keywords": question.lower().split()[:5],
            }

    async def _calculate_confidence(
        self,
        question: str,
        answer:   str,
        nodes:    List[ReasoningNode],
    ) -> float:
        """Calculate confidence score for the final synthesis."""
        verified_count = sum(1 for n in nodes if n.tee_proof and n.tee_proof.verified)
        base_confidence = verified_count / max(len(nodes), 1)
        # Blend with a base of 0.6 for non-TEE nodes
        return round(min(0.6 + (base_confidence * 0.35), 0.98), 2)

    def _format_nodes_for_synthesis(self, nodes: List[ReasoningNode]) -> str:
        parts = []
        for i, n in enumerate(nodes):
            proof_status = "✅ TEE Verified" if (n.tee_proof and n.tee_proof.verified) else "⚪ Unverified"
            parts.append(
                f"{i+1}. [{n.node_type.upper()}] {n.label} {proof_status}\n{n.content[:400]}"
            )
        return "\n\n".join(parts)


# Singleton
_engine: Optional[GraphEngine] = None


def get_engine() -> GraphEngine:
    global _engine
    if _engine is None:
        _engine = GraphEngine()
    return _engine
