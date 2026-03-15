# ================================================================
# main.py - ProofGraph FastAPI Backend
# ================================================================

import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from models import QueryRequest, NodeChallengeRequest, WSEventType
from graph_engine import get_engine
from memsync_client import get_memsync
import database as db

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────
app = FastAPI(
    title="ProofGraph API",
    description="Verifiable Intelligence Graph — Built on OpenGradient",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections per session
ws_connections: dict = {}


@app.on_event("startup")
async def startup():
    await db.init_db()
    print("✅ ProofGraph backend ready")
    print("   TEE Inference: OpenGradient SDK")
    print("   Memory Layer:  MemSync")
    print("   Storage:       SQLite")


# ─── Health ───────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name":    "ProofGraph",
        "tagline": "Verifiable Intelligence Graph",
        "version": "1.0.0",
        "stack":   "OpenGradient TEE + MemSync + x402",
        "status":  "operational",
    }


@app.get("/api/health")
async def health():
    stats = await db.get_stats()
    return {"status": "ok", "stats": stats, "timestamp": datetime.utcnow().isoformat()}


# ─── WebSocket: Real-time streaming ───────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    ws_connections[session_id] = websocket

    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "ProofGraph WebSocket connected",
        })
        # Keep alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_connections.pop(session_id, None)


async def emit_to_session(session_id: str, event: dict):
    """Send WebSocket event to a specific session."""
    ws = ws_connections.get(session_id)
    if ws:
        try:
            await ws.send_json(event)
        except Exception:
            ws_connections.pop(session_id, None)


# ─── Core: Submit a question ──────────────────────────────────
@app.post("/api/query")
async def submit_query(req: QueryRequest):
    """
    Submit a question to ProofGraph.
    Kicks off the full reasoning pipeline async.
    Returns session_id immediately — stream progress via WebSocket.
    """
    session_id = str(uuid.uuid4())

    # Save session immediately
    await db.save_session({
        "id":             session_id,
        "question":       req.question,
        "wallet_address": req.wallet_address,
        "status":         "processing",
        "created_at":     datetime.utcnow().isoformat(),
    })

    # Run pipeline in background
    asyncio.create_task(
        _run_pipeline(
            session_id=session_id,
            question=req.question,
            wallet_address=req.wallet_address,
            max_nodes=req.max_nodes,
        )
    )

    return {
        "session_id": session_id,
        "status":     "processing",
        "message":    "Reasoning pipeline started. Connect to WebSocket for live updates.",
        "ws_url":     f"/ws/{session_id}",
    }


async def _run_pipeline(
    session_id:     str,
    question:       str,
    wallet_address: Optional[str],
    max_nodes:      int,
):
    engine = get_engine()
    try:
        await engine.process_question(
            question=question,
            session_id=session_id,
            wallet_address=wallet_address,
            emit=lambda event: emit_to_session(session_id, event),
            max_nodes=max_nodes,
        )
    except Exception as e:
        print(f"Pipeline error for {session_id}: {e}")
        await db.update_session(session_id, {"status": "error"})
        await emit_to_session(session_id, {
            "type":       WSEventType.ERROR,
            "session_id": session_id,
            "data":       {"error": str(e)},
        })


# ─── Get session + nodes ──────────────────────────────────────
@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    nodes = await db.get_nodes_for_session(session_id)
    return {**session, "nodes": nodes}


# ─── Get full knowledge graph ─────────────────────────────────
@app.get("/api/graph")
async def get_graph(limit: int = 100):
    """Returns all sessions + nodes formatted for D3.js graph visualization."""
    sessions = await db.get_all_sessions(limit=20)
    all_nodes = await db.get_all_nodes(limit=limit)

    # Build D3-compatible nodes + links
    d3_nodes = []
    d3_links = []

    # Add session nodes (question nodes)
    for s in sessions:
        d3_nodes.append({
            "id":       s["id"],
            "label":    s["question"][:60] + ("..." if len(s["question"]) > 60 else ""),
            "type":     "question",
            "status":   s["status"],
            "group":    "session",
        })

    # Add reasoning nodes
    for n in all_nodes:
        d3_nodes.append({
            "id":         n["id"],
            "label":      n["label"],
            "type":       n["node_type"],
            "status":     n["status"],
            "citations":  n["citations"],
            "confidence": n["confidence"],
            "has_proof":  bool(n.get("tee_proof")),
            "group":      "node",
            "content_preview": n["content"][:120] + "...",
        })
        # Link to parent
        parent = n.get("parent_id") or n.get("question_id")
        if parent:
            d3_links.append({
                "source": parent,
                "target": n["id"],
                "type":   "reasoning",
            })

    return {
        "nodes": d3_nodes,
        "links": d3_links,
        "stats": await db.get_stats(),
    }


# ─── Get a specific node ──────────────────────────────────────
@app.get("/api/node/{node_id}")
async def get_node(node_id: str):
    nodes = await db.get_all_nodes(limit=500)
    node = next((n for n in nodes if n["id"] == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


# ─── Get all recent sessions ──────────────────────────────────
@app.get("/api/sessions")
async def get_sessions(limit: int = 20):
    sessions = await db.get_all_sessions(limit=limit)
    return {"sessions": sessions, "total": len(sessions)}


# ─── Challenge a node ─────────────────────────────────────────
@app.post("/api/challenge")
async def challenge_node(req: NodeChallengeRequest):
    """
    Challenge a reasoning node with counter-reasoning.
    In production this triggers on-chain ML evaluation.
    """
    nodes = await db.get_all_nodes(limit=500)
    target = next((n for n in nodes if n["id"] == req.node_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Node not found")

    # Run counter-reasoning via OG
    engine = get_engine()
    await engine.ensure_clients()

    result = await engine.og.infer_tee(
        prompt=f"""
Evaluate this dispute:

ORIGINAL NODE: {target['label']}
Original Content: {target['content'][:400]}

CHALLENGER ARGUMENT: {req.counter_reasoning}

Assess: Is the challenge valid? Who has stronger reasoning? 
Respond with: verdict (uphold/overturn), confidence (0-1), and explanation.
""",
        system_prompt="You are an impartial on-chain arbitration node evaluating a reasoning dispute.",
        max_tokens=400,
    )

    return {
        "node_id":     req.node_id,
        "challenger":  req.challenger_wallet,
        "verdict":     result["content"],
        "tee_proof":   {
            "payment_hash": result.get("payment_hash"),
            "tx_hash":      result.get("tx_hash"),
            "mode":         result.get("mode"),
            "timestamp":    result.get("timestamp"),
        },
        "status": "challenge_processed",
    }


# ─── User Profile (MemSync) ───────────────────────────────────
@app.get("/api/profile/{wallet_address}")
async def get_profile(wallet_address: str):
    memsync = get_memsync()
    profile = await memsync.get_user_profile(wallet_address)

    # Also pull local stats
    all_nodes = await db.get_all_nodes(limit=500)
    user_nodes = [n for n in all_nodes if n.get("wallet_address") == wallet_address]
    total_citations = sum(n["citations"] for n in user_nodes)

    return {
        **profile,
        "local_stats": {
            "nodes_created":  len(user_nodes),
            "total_citations": total_citations,
            "verified_nodes": sum(1 for n in user_nodes if n["status"] == "verified"),
        },
    }


# ─── Stats ────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    return await db.get_stats()


# ─── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    print(f"\n🚀 ProofGraph Backend starting on http://{host}:{port}")
    print("   API docs: http://localhost:8000/docs\n")
    uvicorn.run("main:app", host=host, port=port, reload=True)
