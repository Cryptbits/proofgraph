# ================================================================
# database.py - SQLite persistence for ProofGraph
# ================================================================

import json
import os
from datetime import datetime
from typing import List, Optional

import aiosqlite

DB_PATH = os.getenv("DATABASE_PATH", "./proofgraph.db")


# ─── Schema ───────────────────────────────────────────────────
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    question      TEXT NOT NULL,
    final_answer  TEXT,
    confidence    REAL DEFAULT 0.0,
    wallet_address TEXT,
    status        TEXT DEFAULT 'processing',
    created_at    TEXT NOT NULL
);
"""

CREATE_NODES_TABLE = """
CREATE TABLE IF NOT EXISTS nodes (
    id             TEXT PRIMARY KEY,
    question_id    TEXT NOT NULL,
    node_type      TEXT NOT NULL,
    label          TEXT NOT NULL,
    prompt         TEXT NOT NULL,
    content        TEXT NOT NULL,
    model_used     TEXT NOT NULL,
    tee_proof      TEXT,
    parent_id      TEXT,
    children_ids   TEXT DEFAULT '[]',
    citations      INTEGER DEFAULT 0,
    status         TEXT DEFAULT 'pending',
    confidence     REAL DEFAULT 0.0,
    wallet_address TEXT,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES sessions(id)
);
"""

CREATE_CITATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS citations (
    id              TEXT PRIMARY KEY,
    source_node_id  TEXT NOT NULL,
    citing_node_id  TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""


async def init_db():
    """Initialize the database and create tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SESSIONS_TABLE)
        await db.execute(CREATE_NODES_TABLE)
        await db.execute(CREATE_CITATIONS_TABLE)
        await db.commit()


# ─── Session Operations ───────────────────────────────────────
async def save_session(session: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO sessions
               (id, question, final_answer, confidence, wallet_address, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session["id"],
                session["question"],
                session.get("final_answer"),
                session.get("confidence", 0.0),
                session.get("wallet_address"),
                session.get("status", "processing"),
                session.get("created_at", datetime.utcnow().isoformat()),
            ),
        )
        await db.commit()


async def update_session(session_id: str, updates: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        set_clauses = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [session_id]
        await db.execute(
            f"UPDATE sessions SET {set_clauses} WHERE id = ?", values
        )
        await db.commit()


async def get_session(session_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_sessions(limit: int = 50) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ─── Node Operations ──────────────────────────────────────────
async def save_node(node: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO nodes
               (id, question_id, node_type, label, prompt, content, model_used,
                tee_proof, parent_id, children_ids, citations, status,
                confidence, wallet_address, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node["id"],
                node["question_id"],
                node["node_type"],
                node["label"],
                node["prompt"],
                node["content"],
                node.get("model_used", "openai/gpt-4.1"),
                json.dumps(node.get("tee_proof")) if node.get("tee_proof") else None,
                node.get("parent_id"),
                json.dumps(node.get("children_ids", [])),
                node.get("citations", 0),
                node.get("status", "pending"),
                node.get("confidence", 0.0),
                node.get("wallet_address"),
                node.get("created_at", datetime.utcnow().isoformat()),
            ),
        )
        await db.commit()


async def get_nodes_for_session(session_id: str) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM nodes WHERE question_id = ? ORDER BY created_at ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["tee_proof"] = json.loads(d["tee_proof"]) if d["tee_proof"] else None
                d["children_ids"] = json.loads(d["children_ids"])
                result.append(d)
            return result


async def get_all_nodes(limit: int = 200) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM nodes ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["tee_proof"] = json.loads(d["tee_proof"]) if d["tee_proof"] else None
                d["children_ids"] = json.loads(d["children_ids"])
                result.append(d)
            return result


async def search_nodes_by_topic(query_keywords: List[str], limit: int = 5) -> List[dict]:
    """Basic keyword search across node content/labels for graph reuse."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = " OR ".join(
            ["LOWER(content) LIKE ? OR LOWER(label) LIKE ?" for _ in query_keywords]
        )
        values = []
        for kw in query_keywords:
            values.extend([f"%{kw.lower()}%", f"%{kw.lower()}%"])
        values.append(limit)
        async with db.execute(
            f"""SELECT * FROM nodes
                WHERE status = 'verified' AND ({conditions})
                ORDER BY citations DESC
                LIMIT ?""",
            values,
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["tee_proof"] = json.loads(d["tee_proof"]) if d["tee_proof"] else None
                d["children_ids"] = json.loads(d["children_ids"])
                result.append(d)
            return result


async def increment_citation(node_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE nodes SET citations = citations + 1 WHERE id = ?", (node_id,)
        )
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM nodes") as c:
            total_nodes = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM nodes WHERE status='verified'") as c:
            verified_nodes = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM sessions") as c:
            total_sessions = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(citations) FROM nodes") as c:
            total_citations = (await c.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM nodes WHERE tee_proof IS NOT NULL") as c:
            live_proofs = (await c.fetchone())[0]
        return {
            "total_nodes":    total_nodes,
            "verified_nodes": verified_nodes,
            "total_sessions": total_sessions,
            "total_citations": total_citations,
            "live_proofs":    live_proofs,
        }
