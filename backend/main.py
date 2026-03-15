# ================================================================
# main.py — ProofGraph FastAPI Backend (MVP)
# ================================================================

import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import QueryRequest, NodeChallengeRequest, WSEventType
from graph_engine import get_engine
from memsync_client import get_memsync
import database as db

load_dotenv()

app = FastAPI(
    title="ProofGraph API",
    description="Verifiable Intelligence Graph — Built on OpenGradient",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_connections: dict  = {}
ws_event_buffer: dict = {}   # buffers events emitted before WS connects; replayed on connect


@app.on_event("startup")
async def startup():
    await db.init_db()
    # Auto-purge any demo/stale nodes so graph starts clean
    import aiosqlite, os
    db_path = os.getenv("DATABASE_PATH", "./proofgraph.db")
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                "DELETE FROM nodes WHERE inference_mode='DEMO' OR model_used LIKE '%demo%' OR content LIKE '%DEMO MODE%'"
            )
            await conn.execute(
                "DELETE FROM sessions WHERE id NOT IN (SELECT DISTINCT question_id FROM nodes)"
            )
            await conn.commit()
    except Exception as e:
        print(f"  Cleanup skipped: {e}")
    # Pre-initialize OG client so first query is instant
    engine = get_engine()
    await engine.ensure_clients()
    mode = getattr(engine.og, "mode", "KNOWLEDGE")
    print(f"\n{'='*50}")
    print(f"  ProofGraph MVP — {mode}")
    if mode == "OG_LIVE":
        print(f"  Wallet: {engine.og.wallet}")
        print(f"  TEE Inference: ACTIVE ✅")
        print(f"  x402 Payments: ACTIVE ✅")
    else:
        print(f"  Add OG_PRIVATE_KEY to .env for live inference")
    print(f"  API docs: http://localhost:8000/docs")
    print(f"{'='*50}\n")


# Health / Mode
@app.get("/")
async def root():
    engine = get_engine()
    mode   = getattr(engine.og, "mode", "KNOWLEDGE") if engine.og else "KNOWLEDGE"
    return {
        "name":    "ProofGraph",
        "tagline": "Verifiable Intelligence Graph",
        "version": "2.0.0",
        "mode":    mode,
        "stack":   "OpenGradient TEE + MemSync + x402",
        "status":  "operational",
    }


@app.get("/api/health")
async def health():
    engine = get_engine()
    mode   = getattr(engine.og, "mode", "KNOWLEDGE") if engine.og else "KNOWLEDGE"
    wallet = getattr(engine.og, "wallet", None) if engine.og else None
    stats  = await db.get_stats()
    return {
        "status":    "ok",
        "mode":      mode,
        "wallet":    wallet,
        "live":      mode == "OG_LIVE",
        "stats":     stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


# WebSocket
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    ws_connections[session_id] = websocket
    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
        })
        # Replay any events that fired before WS was open
        buffered = ws_event_buffer.pop(session_id, [])
        for event in buffered:
            try:
                await websocket.send_json(event)
            except Exception:
                break
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=90.0)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_connections.pop(session_id, None)


async def emit_to_session(session_id: str, event: dict):
    ws = ws_connections.get(session_id)
    if ws:
        try:
            await ws.send_json(event)
        except Exception:
            ws_connections.pop(session_id, None)
    else:
        # WS not connected yet — buffer the event for replay
        if session_id not in ws_event_buffer:
            ws_event_buffer[session_id] = []
        ws_event_buffer[session_id].append(event)


# Submit Question
@app.post("/api/query")
async def submit_query(req: QueryRequest):
    session_id = str(uuid.uuid4())

    await db.save_session({
        "id":             session_id,
        "question":       req.question,
        "wallet_address": req.wallet_address,
        "status":         "processing",
        "created_at":     datetime.utcnow().isoformat(),
    })

    asyncio.create_task(_run_pipeline(
        session_id=session_id,
        question=req.question,
        wallet_address=req.wallet_address,
        max_nodes=req.max_nodes,
    ))

    return {
        "session_id": session_id,
        "status":     "processing",
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
        print(f"❌ Pipeline error [{session_id[:8]}]: {e}")
        import traceback; traceback.print_exc()
        await db.update_session(session_id, {"status": "error"})
        await emit_to_session(session_id, {
            "type":       WSEventType.ERROR,
            "session_id": session_id,
            "data":       {"error": str(e)},
        })


# Read endpoints
@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    nodes = await db.get_nodes_for_session(session_id)
    return {**session, "nodes": nodes}


@app.get("/api/graph")
async def get_graph(limit: int = 60, session_id: str = None):
    # If session_id given, return only that session's nodes
    if session_id:
        sessions  = [s for s in await db.get_all_sessions(limit=100) if s["id"] == session_id]
        all_nodes = await db.get_nodes_for_session(session_id)
    else:
        sessions  = await db.get_all_sessions(limit=20)
        all_nodes = await db.get_all_nodes(limit=limit)

    d3_nodes, d3_links = [], []

    for s in sessions:
        d3_nodes.append({
            "id":     s["id"],
            "label":  s["question"][:60] + ("..." if len(s["question"]) > 60 else ""),
            "type":   "question",
            "status": s["status"],
            "group":  "session",
        })

    for n in all_nodes:
        proof    = n.get("tee_proof") or {}
        tx_hash  = proof.get("tx_hash")  if isinstance(proof, dict) else None
        mode     = proof.get("inference_mode", "KNOWLEDGE") if isinstance(proof, dict) else "KNOWLEDGE"
        verified = proof.get("verified", False) if isinstance(proof, dict) else False

        d3_nodes.append({
            "id":              n["id"],
            "label":           n["label"],
            "type":            n["node_type"],
            "status":          n["status"],
            "citations":       n["citations"],
            "confidence":      n["confidence"],
            "has_proof":       bool(tx_hash),
            "mode":            mode,
            "verified":        verified,
            "group":           "node",
            "content_preview": n["content"][:120] + "...",
        })

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


@app.get("/api/node/{node_id}")
async def get_node(node_id: str):
    nodes = await db.get_all_nodes(limit=1000)
    node  = next((n for n in nodes if n["id"] == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.get("/api/sessions")
async def get_sessions(limit: int = 20):
    sessions = await db.get_all_sessions(limit=limit)
    return {"sessions": sessions, "total": len(sessions)}


# Challenge
@app.post("/api/challenge")
async def challenge_node(req: NodeChallengeRequest):
    nodes  = await db.get_all_nodes(limit=1000)
    target = next((n for n in nodes if n["id"] == req.node_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Node not found")

    engine = get_engine()
    await engine.ensure_clients()

    result = await engine.og.infer_tee(
        prompt=(
            f"DISPUTE ARBITRATION\n\n"
            f"Original node: {target['label']}\n"
            f"Content: {target['content'][:400]}\n\n"
            f"Challenger argument: {req.counter_reasoning}\n\n"
            f"Assess: uphold or overturn. Give verdict, confidence 0-1, and reasoning."
        ),
        system_prompt="You are an impartial on-chain arbitration node.",
        max_tokens=400,
    )

    return {
        "node_id":    req.node_id,
        "challenger": req.challenger_wallet,
        "verdict":    result["content"],
        "tee_proof": {
            "tx_hash":      result.get("tx_hash"),
            "payment_hash": result.get("payment_hash"),
            "mode":         result.get("mode"),
            "timestamp":    result.get("timestamp"),
        },
        "status": "arbitration_complete",
    }


# Profile
@app.get("/api/profile/{wallet_address}")
async def get_profile(wallet_address: str):
    memsync   = get_memsync()
    profile   = await memsync.get_user_profile(wallet_address)
    all_nodes = await db.get_all_nodes(limit=1000)
    user_nodes = [n for n in all_nodes if n.get("wallet_address") == wallet_address]

    return {
        **profile,
        "local_stats": {
            "nodes_created":   len(user_nodes),
            "total_citations": sum(n["citations"] for n in user_nodes),
            "verified_nodes":  sum(1 for n in user_nodes if n["status"] == "verified"),
            "live_proofs":     sum(
                1 for n in user_nodes
                if isinstance(n.get("tee_proof"), dict) and n["tee_proof"].get("tx_hash")
            ),
        },
    }


@app.get("/api/stats")
async def get_stats():
    return await db.get_stats()


# Entry point
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    print(f"\n🚀 ProofGraph starting on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
