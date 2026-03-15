# ================================================================
# models.py - ProofGraph Data Models
# ================================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class NodeStatus(str, Enum):
    PENDING    = "pending"
    VERIFIED   = "verified"
    CHALLENGED = "challenged"
    DISPUTED   = "disputed"


class NodeType(str, Enum):
    QUESTION    = "question"
    DEFINITION  = "definition"
    ANALYSIS    = "analysis"
    EVIDENCE    = "evidence"
    SYNTHESIS   = "synthesis"
    CONCLUSION  = "conclusion"


# ─── TEE Proof Object ─────────────────────────────────────────
class TEEProof(BaseModel):
    payment_hash:  Optional[str] = None
    tx_hash:       Optional[str] = None
    model_used:    str
    inference_mode: str           = "TEE"
    settlement_mode: str          = "SETTLE_METADATA"
    timestamp:     str
    verified:      bool           = False


# ─── A single reasoning node in the graph ─────────────────────
class ReasoningNode(BaseModel):
    id:           str         = Field(default_factory=lambda: str(uuid.uuid4()))
    question_id:  str
    node_type:    NodeType
    label:        str
    prompt:       str
    content:      str
    model_used:   str         = "openai/gpt-4.1"
    tee_proof:    Optional[TEEProof] = None
    parent_id:    Optional[str] = None
    children_ids: List[str]   = []
    citations:    int         = 0
    status:       NodeStatus  = NodeStatus.PENDING
    confidence:   float       = 0.0
    created_at:   str         = Field(default_factory=lambda: datetime.utcnow().isoformat())
    wallet_address: Optional[str] = None


# ─── A full question/answer session ───────────────────────────
class QuestionSession(BaseModel):
    id:           str         = Field(default_factory=lambda: str(uuid.uuid4()))
    question:     str
    final_answer: Optional[str] = None
    confidence:   float       = 0.0
    nodes:        List[ReasoningNode] = []
    related_ids:  List[str]   = []
    wallet_address: Optional[str] = None
    created_at:   str         = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status:       str         = "processing"


# ─── API Request/Response Models ──────────────────────────────
class QueryRequest(BaseModel):
    question:       str
    wallet_address: Optional[str] = None
    use_tee:        bool = True
    max_nodes:      int  = 6


class NodeChallengeRequest(BaseModel):
    node_id:         str
    challenger_wallet: str
    counter_reasoning: str


class GraphSearchRequest(BaseModel):
    query:  str
    limit:  int = 5


class UserProfile(BaseModel):
    wallet_address:  str
    total_nodes:     int = 0
    total_citations: int = 0
    total_questions: int = 0
    memories:        List[Dict[str, Any]] = []
    top_topics:      List[str] = []


# ─── WebSocket event types ────────────────────────────────────
class WSEventType(str, Enum):
    SESSION_START      = "session_start"
    NODE_PENDING       = "node_pending"
    NODE_VERIFIED      = "node_verified"
    NODE_FAILED        = "node_failed"
    SESSION_COMPLETE   = "session_complete"
    GRAPH_REUSE        = "graph_reuse"
    ERROR              = "error"


class WSEvent(BaseModel):
    type:    WSEventType
    data:    Dict[str, Any]
    session_id: str
