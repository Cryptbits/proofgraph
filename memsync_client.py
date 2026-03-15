# ================================================================
# memsync_client.py - MemSync REST API Integration
# Persistent AI memory layer built on OpenGradient infrastructure
# ================================================================

import os
import json
from typing import Optional, List, Dict, Any

import httpx
from dotenv import load_dotenv

load_dotenv()


class MemSyncClient:
    """
    Client for OpenGradient's MemSync API.
    Handles long-term memory storage and semantic search
    for the ProofGraph knowledge accumulation layer.
    """

    def __init__(self):
        self.api_key  = os.getenv("MEMSYNC_API_KEY", "")
        self.base_url = os.getenv("MEMSYNC_BASE_URL", "https://api.memchat.io")
        self.enabled  = bool(self.api_key)

        if not self.enabled:
            print("ℹ️  MemSync: No API key found — running with local memory only")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    # ─── Store a reasoning node as a memory ───────────────────
    async def store_node_memory(
        self,
        user_id:    str,
        node_id:    str,
        label:      str,
        content:    str,
        node_type:  str,
        tx_hash:    Optional[str] = None,
        topic_tags: List[str] = [],
    ) -> bool:
        """Store a verified reasoning node in MemSync for future retrieval."""
        if not self.enabled:
            return False

        memory_content = f"""
ProofGraph Node [{node_type.upper()}]: {label}

Content: {content}

Verification: {'On-chain verified (TEE)' if tx_hash else 'Unverified'}
Transaction: {tx_hash or 'N/A'}
Node ID: {node_id}
Topics: {', '.join(topic_tags)}
"""

        payload = {
            "user_id":  user_id,
            "messages": [
                {
                    "role":    "assistant",
                    "content": memory_content.strip(),
                }
            ],
            "metadata": {
                "source":    "proofgraph",
                "node_id":   node_id,
                "node_type": node_type,
                "tx_hash":   tx_hash,
                "tags":      topic_tags,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/memories",
                    headers=self._headers(),
                    json=payload,
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            print(f"MemSync store error: {e}")
            return False

    # ─── Search memories for relevant nodes ───────────────────
    async def search_memories(
        self,
        user_id: str,
        query:   str,
        limit:   int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search across stored memories for a user."""
        if not self.enabled:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/memories/search",
                    headers=self._headers(),
                    json={
                        "user_id": user_id,
                        "query":   query,
                        "limit":   limit,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("memories", data.get("results", []))
                return []
        except Exception as e:
            print(f"MemSync search error: {e}")
            return []

    # ─── Get user profile / memory summary ────────────────────
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get a user's accumulated memory profile."""
        if not self.enabled:
            return {
                "user_id":       user_id,
                "total_memories": 0,
                "top_topics":    [],
                "memories":      [],
                "enabled":       False,
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/memories",
                    headers=self._headers(),
                    params={"user_id": user_id, "limit": 20},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    memories = data.get("memories", data.get("results", []))
                    return {
                        "user_id":        user_id,
                        "total_memories": len(memories),
                        "top_topics":     self._extract_topics(memories),
                        "memories":       memories[:10],
                        "enabled":        True,
                    }
                return {"user_id": user_id, "enabled": False, "memories": []}
        except Exception as e:
            print(f"MemSync profile error: {e}")
            return {"user_id": user_id, "enabled": False, "memories": []}

    # ─── Store a complete question session ────────────────────
    async def store_session_memory(
        self,
        user_id:      str,
        question:     str,
        final_answer: str,
        session_id:   str,
        node_count:   int,
    ) -> bool:
        """Store a completed reasoning session summary."""
        if not self.enabled:
            return False

        content = f"""
ProofGraph Session Completed

Question: {question}

Answer: {final_answer[:500]}{'...' if len(final_answer) > 500 else ''}

Stats: {node_count} verified reasoning nodes
Session ID: {session_id}
"""

        payload = {
            "user_id":  user_id,
            "messages": [
                {"role": "user",      "content": f"Research question: {question}"},
                {"role": "assistant", "content": content.strip()},
            ],
            "metadata": {
                "source":     "proofgraph",
                "session_id": session_id,
                "type":       "session_summary",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/memories",
                    headers=self._headers(),
                    json=payload,
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            print(f"MemSync session store error: {e}")
            return False

    def _extract_topics(self, memories: List[Dict]) -> List[str]:
        """Extract top topics from memories (simple heuristic)."""
        topic_words: Dict[str, int] = {}
        for mem in memories:
            text = str(mem.get("content", "") + str(mem.get("metadata", {})))
            for word in text.lower().split():
                if len(word) > 5 and word.isalpha():
                    topic_words[word] = topic_words.get(word, 0) + 1
        sorted_topics = sorted(topic_words.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_topics[:8]]


# Singleton
_memsync: Optional[MemSyncClient] = None


def get_memsync() -> MemSyncClient:
    global _memsync
    if _memsync is None:
        _memsync = MemSyncClient()
    return _memsync
