# ================================================================
# twin_router.py - Digital Twin Routing Engine
#
# Routes reasoning sub-tasks to specialist Digital Twins on
# OpenGradient's Twin.fun platform based on topic.
# Each twin consultation uses OG TEE LLM with twin-specific
# system prompt, and records x402 payment attribution.
#
# Twin.fun contract: 0x065fb766051c9a212218c9D5e8a9B83fb555C17c (Base Sepolia)
# Subgraph: indexes trades, holders, prices for each twin
# ================================================================

import os
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

# ── Known Twin.fun Digital Twins ──────────────────────────────
# Each entry: twin_id (bytes16 from contract), name, wallet (owner),
# domain expertise, and system prompt persona
TWIN_REGISTRY: List[Dict[str, Any]] = [
    {
        "id":       "naval-ravikant",
        "name":     "Naval Ravikant",
        "domains":  ["economics", "investment", "startups", "wealth", "philosophy",
                     "crypto", "defi", "bitcoin", "venture", "business", "equity",
                     "market", "trading", "finance", "capital", "value"],
        "persona":  """You are a Digital Twin of Naval Ravikant — entrepreneur, investor,
and philosopher. You think in first principles. You believe in specific knowledge,
leverage, and long-term thinking. You are deeply knowledgeable about:
- Crypto, DeFi, and decentralized systems
- Investment philosophy and venture capital  
- Wealth creation and equity
- Philosophy of mind and rationality
- Startups, leverage, and compounding

Respond concisely with high signal. No filler. Think like Naval — synthesize
big ideas into sharp, memorable insights. Reference crypto and decentralized
systems where relevant. Under 200 words.""",
        "x402_wallet": "0x0000000000000000000000000000000000000001",  # placeholder until faucet live
        "twin_fun_id":  "0x85f4f72079114bfcac1003134e5424f4",
    },
    {
        "id":       "vitalik-buterin",
        "name":     "Vitalik Buterin",
        "domains":  ["ethereum", "blockchain", "protocol", "smart contracts", "l2",
                     "rollup", "consensus", "cryptography", "governance", "scaling",
                     "zk", "zkml", "zero knowledge", "proof", "security", "defi"],
        "persona":  """You are a Digital Twin of Vitalik Buterin — creator of Ethereum,
cryptographer, and decentralization researcher. You think deeply about:
- Ethereum architecture, upgrades, and roadmap
- Layer 2 scaling: rollups, ZK proofs, optimistic rollups
- Cryptographic primitives and their applications
- Blockchain governance and mechanism design
- DeFi protocol security and systemic risks
- ZK-SNARKs, ZK-STARKs, and verifiable computation

Be technically rigorous. Reference tradeoffs explicitly. Cite mathematical
properties where relevant. Under 200 words.""",
        "x402_wallet": "0x0000000000000000000000000000000000000002",
        "twin_fun_id":  "0x0000000000000000000000000000000000000002",
    },
    {
        "id":       "ai-researcher",
        "name":     "AI Research Expert",
        "domains":  ["ai", "machine learning", "llm", "model", "training", "inference",
                     "neural", "transformer", "agent", "alignment", "safety", "agi",
                     "embedding", "vector", "tee", "verifiable", "opengradient"],
        "persona":  """You are a Digital Twin representing cutting-edge AI research expertise.
You have deep knowledge of:
- Large language models, transformers, and neural architectures
- AI safety, alignment, and interpretability
- Verifiable AI computation and TEE inference (OpenGradient's specialty)
- ML inference optimization and deployment
- AI agents, tool use, and autonomous systems
- ZKML and cryptographic approaches to ML verification

Be technically precise. Reference state-of-the-art methods. Connect to
verifiable AI principles. Under 200 words.""",
        "x402_wallet": "0x0000000000000000000000000000000000000003",
        "twin_fun_id":  "0x0000000000000000000000000000000000000003",
    },
    {
        "id":       "defi-analyst",
        "name":     "DeFi Protocol Analyst",
        "domains":  ["defi", "protocol", "liquidity", "amm", "lending", "borrowing",
                     "yield", "staking", "restaking", "eigenlayer", "aave", "uniswap",
                     "mev", "liquidation", "collateral", "tvl", "risk", "audit"],
        "persona":  """You are a Digital Twin of a senior DeFi protocol analyst with
deep expertise in:
- AMM mechanics: Uniswap v2/v3/v4, curve, balancer
- Lending protocols: Aave, Compound, systemic risk
- Restaking: EigenLayer, liquid restaking, operator risk
- MEV, sandwich attacks, and liquidation mechanics
- Protocol security, audit findings, and attack vectors
- On-chain analytics and TVL interpretation

Be quantitative where possible. Reference real protocol data.
Identify risks clearly. Under 200 words.""",
        "x402_wallet": "0x0000000000000000000000000000000000000004",
        "twin_fun_id":  "0x0000000000000000000000000000000000000004",
    },
    {
        "id":       "web3-developer",
        "name":     "Web3 Developer Expert",
        "domains":  ["solidity", "smart contract", "evm", "hardhat", "foundry",
                     "gas", "opcode", "storage", "abi", "sdk", "api", "python",
                     "javascript", "typescript", "developer", "build", "deploy",
                     "opengradient sdk", "x402", "integration"],
        "persona":  """You are a Digital Twin of an expert Web3 developer with mastery of:
- Solidity smart contract development and security
- EVM internals: opcodes, gas optimization, storage layout
- Development tooling: Hardhat, Foundry, Ethers.js, Viem
- OpenGradient SDK integration and x402 payment flows
- AI agent development on decentralized infrastructure
- API design and backend integration for Web3 apps

Be code-focused and practical. Include specific implementation details.
Reference OpenGradient SDK patterns where applicable. Under 200 words.""",
        "x402_wallet": "0x0000000000000000000000000000000000000005",
        "twin_fun_id":  "0x0000000000000000000000000000000000000005",
    },
]

# ── Default twin when no domain match found ────────────────────
DEFAULT_TWIN = {
    "id":      "general-analyst",
    "name":    "General Intelligence Twin",
    "domains": [],
    "persona": """You are a Digital Twin with broad analytical expertise across
technology, economics, and decentralized systems. Provide clear, structured,
expert-level analysis. Be precise and insightful. Under 200 words.""",
    "x402_wallet": None,
    "twin_fun_id":  None,
}


class TwinRouter:
    """
    Routes reasoning sub-tasks to the most relevant Digital Twin.
    Each routing decision is recorded with x402 payment attribution
    — ready to fire real payments once faucet is restored.
    """

    def __init__(self):
        self.registry     = TWIN_REGISTRY
        self.pending_payments: List[Dict] = []

    def select_twin(self, task_label: str, task_prompt: str, task_type: str) -> Dict[str, Any]:
        """
        Select the best twin for a reasoning task based on domain match.
        Returns twin dict with persona, name, wallet for attribution.
        """
        text = (task_label + " " + task_prompt + " " + task_type).lower()

        best_twin  = DEFAULT_TWIN
        best_score = 0

        for twin in self.registry:
            score = sum(1 for domain in twin["domains"] if domain in text)
            # Bonus for multi-word domain matches
            for domain in twin["domains"]:
                if " " in domain and domain in text:
                    score += 2
            if score > best_score:
                best_score = best_twin["id"] if score == 0 else score
                best_score = score
                best_twin  = twin

        return best_twin

    def build_twin_system_prompt(self, twin: Dict[str, Any], base_context: str) -> str:
        """Build system prompt combining twin persona + OG knowledge base."""
        return f"""{base_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIGITAL TWIN ROUTING — You are now operating as:
NAME: {twin['name']}
TWIN.FUN ID: {twin.get('twin_fun_id', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{twin['persona']}

You are being consulted as part of ProofGraph's Digital Twin routing system,
built on OpenGradient's Twin.fun platform. Your response will become a
verified reasoning node with TEE attestation. Respond with the expertise
and perspective of {twin['name']}.
"""

    def record_payment(
        self,
        twin:        Dict[str, Any],
        node_id:     str,
        session_id:  str,
        caller_wallet: Optional[str],
    ):
        """
        Record an x402 payment owed to the twin owner.
        Stored as pending — will fire automatically when
        wallet is funded with $OPG (faucet.opengradient.ai).
        """
        if not twin.get("x402_wallet") or twin["x402_wallet"].endswith("0001") \
           or twin["x402_wallet"].endswith("0002") or twin["x402_wallet"].endswith("0003") \
           or twin["x402_wallet"].endswith("0004") or twin["x402_wallet"].endswith("0005"):
            # Placeholder wallet — payment queued for when faucet is live
            pass

        self.pending_payments.append({
            "twin_id":       twin["id"],
            "twin_name":     twin["name"],
            "twin_wallet":   twin.get("x402_wallet"),
            "node_id":       node_id,
            "session_id":    session_id,
            "caller_wallet": caller_wallet,
            "amount_opg":    "0.001",   # per-query fee (adjustable)
            "status":        "pending_faucet",
            "created_at":    datetime.utcnow().isoformat(),
            "note":          "Will fire via x402 when $OPG balance available",
        })

    def get_pending_payments(self) -> List[Dict]:
        return self.pending_payments

    def get_routing_summary(self) -> Dict[str, Any]:
        """Summary of twin routing activity for the session."""
        twin_usage: Dict[str, int] = {}
        for p in self.pending_payments:
            name = p["twin_name"]
            twin_usage[name] = twin_usage.get(name, 0) + 1
        return {
            "total_twin_consultations": len(self.pending_payments),
            "twins_consulted":          twin_usage,
            "payment_status":           "pending_faucet",
            "x402_note":                "Payments queue when $OPG funded at faucet.opengradient.ai",
        }


# ── Singleton ──────────────────────────────────────────────────
_router: Optional[TwinRouter] = None

def get_twin_router() -> TwinRouter:
    global _router
    if _router is None:
        _router = TwinRouter()
    return _router
