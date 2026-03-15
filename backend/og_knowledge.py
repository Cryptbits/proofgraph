# og_knowledge.py
# Complete OpenGradient knowledge base.
# Every fact sourced from opengradient.ai, docs.opengradient.ai, and GitHub.

import re as _re

_STOP = {
    "what","is","are","the","a","an","how","why","who","does","do","can",
    "about","explain","tell","me","us","you","i","it","its","of","in","on",
    "at","to","for","with","and","or","not","that","this","was","were","has",
    "have","had","will","would","could","should","please","give","show","mean",
    "means","meaning","describe","define","let","know","understand","overview",
    "summary","details","info","information","more","some","any","get","my",
    "want","need","like","use","used","using","work","works","working","did",
    "been","being","am","so","such","than","then","there","they","them","their"
}

OG_SYSTEM_CONTEXT = """
You are ProofGraph, an AI expert assistant for OpenGradient.

CRITICAL RULE: When the question asks about OpenGradient broadly, answer about OPENGRADIENT THE PLATFORM and its mission. Never substitute an answer about BitQuant, MemSync, or any other individual product when OpenGradient itself is being asked about.

WHAT OPENGRADIENT IS:
OpenGradient is the leading research lab building at the frontier of AI and blockchain computing. It is a vertically-integrated, decentralized infrastructure layer for secure and verifiable AI execution, agent and application deployment, and AI model hosting. The official one-line definition: "The OpenGradient Network powers open and verifiable AI onchain: model hosting, secure inference, and AI agent execution."

Mission: The future of AI is user-owned. OpenGradient started with a clear premise: existing AI is a black box that lacks transparency and traps user data within closed platforms. By building technology that enables verifiable compute, supports persistent memory, and secures user-owned data, they aim to unlock human-level intelligence powered by private data.

FOUNDING AND FUNDING:
Founded 2023 in New York City. CEO Matthew Wang (ex-Two Sigma). CTO Adam Balogh (ex-Palantir). Co-founders described as veterans from Google, Meta, and Palantir. Raised $8.5M seed from a16z Crypto Startup Accelerator (CSX), Foresight Ventures, SV Angel, Coinbase Ventures, SALT Fund, and Symbolic Capital. Also selected for the a16z Crypto Fall CSX program.

NETWORK STATS (as of 2026):
2,000+ models hosted. 100+ active developers. 1M+ inferences completed.

HACA (Hybrid AI Compute Architecture):
Full Node (The Judge): Runs EVM state-transition, re-executes transactions, verifies ZK proofs and TEE attestations.
Inference Node (The Sprinter): Stateless GPU/TPU worker. Streams weights, runs forward pass, returns output plus ZK proof or TEE attestation.
Storage Node (The Librarian): Maintains decentralized filestore, shards model checkpoints on Walrus, keeps version history.
Data Node: Fetches external real-world data (price feeds etc.) with TEE guarantees.

The blockchain uses CometBFT consensus and is EVM-compatible. PIPE (Parallelised Inference Pre-Execution Engine) prevents slow AI models from blocking block production.

VERIFICATION SPECTRUM (developer choice):
TEE: hardware-based trust via AWS Nitro Enclaves.
ZKML: mathematical zero-knowledge proof of ML output.
Optimistic: signed result with challenge window.
Developers can mix verification methods in a single transaction.

TEE SPECIFICS:
AWS Nitro Enclaves generate attestation documents signed by AWS. Each TEE node has its own signing key and TLS certificate generated inside the enclave. TLS sessions terminate inside the enclave. Output hash is persisted on-chain. Only the user holding the actual output can verify it by recreating the hash. Privacy preserved by design.

x402 PAYMENT:
Embedded directly inside every TEE instance. No centralized middleware. Revives HTTP 402 Payment Required for internet-native per-inference payments. Uses $OPG tokens on Base Sepolia, settled through the Permit2 protocol. Users pre-fund an account; inference draws from the balance without blocking async workloads. Inference payment separate from ML inference which settles natively on the OpenGradient chain.

PRODUCTS:
MemSync: Portable AI memory layer. Encrypted vault that travels across apps, devices, and chains. Announced September 2025. app.memsync.ai
Model Hub: Web3 answer to HuggingFace. Permissionless, censorship-resistant model registry. hub.opengradient.ai
BitQuant: Open-source AI agent framework for quantitative trading and DeFi analytics. Open-sourced October 29, 2025. 50K+ beta users. Architecture: Oracle (data layer from Solana RPC, Orca, Solend, CoinGecko, DeFiLlama) + Brain (Router LLM for decision making) + Trader (execution layer).
Twin.fun: AI digital twins marketplace. Announced November 2025. "Trade Minds, Not Tokens." bonding curve key markets.
OG SDK: Python SDK, drop-in replacement for OpenAI and Anthropic APIs with cryptographic attestation. Supports models from OpenAI, Anthropic, Google, and xAI through unified interface with TEE verification.
SolidML: Solidity library bringing AI into smart contracts. Direct AI inference from Solidity via precompiles.
Neuro Stack: Framework for teams to spin up their own Layer 2 rollups with custom tokens that tap OpenGradient AI engines as a shared service.

ADVISORS:
Balaji Srinivasan (ex-Coinbase CTO), Illia Polosukhin (Transformer architecture co-inventor, NEAR co-founder), Sandeep Nailwal (Polygon CEO), Ekram Ahmed (Head of Marketing at Celestia), Bruno Faviero (CoFounder of Magna).

PARTNERS:
EigenLayer, Nuffle Labs, LangChain, CareCentra, Sparsity XYZ.

ERA FRAMING:
Era 1 Move Numbers (2009 Bitcoin). Era 2 Move Logic (2015 Ethereum). Era 3 Move Meaning (2025 OpenGradient). A block now records not just what happened and how, but also why. Intelligence is the native asset of the ledger.

LINKS:
Website: opengradient.ai
Docs: docs.opengradient.ai
GitHub: github.com/OpenGradient
Hub: hub.opengradient.ai
Explorer: explorer.opengradient.ai
Faucet: faucet.opengradient.ai
Twitter/X: x.com/OpenGradient
Discord: discord.gg/2t5sx5BCpB

RULE: Answer only what was asked. Match the scope of the question precisely.
""".strip()


TOPICS = [
    {
        "key": "opengradient",
        "words": {"opengradient", "og"},
        "answer": (
            "OpenGradient is the leading research lab building at the frontier of AI and blockchain computing. "
            "More specifically, it is a vertically-integrated, decentralized infrastructure layer for secure and "
            "verifiable AI execution, agent deployment, and AI model hosting.\n\n"
            "The network's mission is captured in one phrase: the future of AI is user-owned. "
            "OpenGradient's starting premise is that existing AI is a black box controlled by a few tech giants "
            "who can restrict access, snoop on data, and cannot be audited. OpenGradient makes AI verifiable, "
            "private, and open, with every inference cryptographically proven on-chain.\n\n"
            "Think of it as three eras of blockspace: Bitcoin moved numbers, Ethereum moved logic, "
            "OpenGradient moves meaning. A block on OpenGradient records not just what happened and how, "
            "but also why, with the AI reasoning that drove any decision provable and permanent.\n\n"
            "The network hosts over 2,000 models and has processed over 1 million inferences. "
            "Founded 2023 in New York City. Backed by a16z crypto, Coinbase Ventures, and Foresight Ventures.\n\n"
            "Website: opengradient.ai  |  Twitter: x.com/OpenGradient  |  Discord: discord.gg/2t5sx5BCpB"
        ),
    },
    {
        "key": "tee",
        "words": {"tee", "trusted", "execution", "enclave", "attestation", "nitro", "secure", "hardware", "privacy", "confidential"},
        "answer": (
            "A Trusted Execution Environment (TEE) is a sealed hardware enclave where code runs in complete "
            "isolation, protected from outside interference even from the host machine's own operating system.\n\n"
            "OpenGradient uses AWS Nitro Enclaves. Here is what actually happens during an inference:\n\n"
            "Each TEE node generates its own signing key and TLS certificate inside the enclave at registration. "
            "Clients connect directly to attested nodes with trust rooted in on-chain verification, not a "
            "certificate authority. The TLS session terminates inside the enclave itself, meaning no intermediary "
            "can intercept communication. After the model runs, the output is signed and a hash is persisted "
            "on-chain. Only the user holding the actual output can verify it by recreating the hash, so "
            "privacy is preserved by design.\n\n"
            "This is what separates OpenGradient from OpenAI or Google. You do not have to trust the company. "
            "The hardware proves the computation ran correctly and was not tampered with."
        ),
    },
    {
        "key": "x402",
        "words": {"x402", "payment", "payments", "pay", "opg", "token", "tokens", "faucet", "micropayment"},
        "answer": (
            "x402 is a payment protocol for the internet built on HTTP, forked and integrated natively "
            "into OpenGradient's TEE infrastructure. It revives the long-dormant HTTP 402 Payment Required "
            "status code for instant, internet-native per-inference payments.\n\n"
            "What makes it different is where it lives. x402 is embedded directly inside every TEE instance, "
            "with no centralized payment middleware sitting between your request and the compute enclave. "
            "Users pre-fund an account with $OPG tokens on Base Sepolia, settled through the Permit2 protocol. "
            "Inference draws from that balance without blocking async workloads, which is critical when an "
            "AI agent is orchestrating dozens of parallel inference calls.\n\n"
            "This is the foundational primitive for autonomous AI agents that pay for their own compute, "
            "negotiate access to other AI services, and operate economically with no human in the loop.\n\n"
            "Get free testnet tokens: faucet.opengradient.ai"
        ),
    },
    {
        "key": "memsync",
        "words": {"memsync", "memory", "remember", "remembers", "remembering", "personalization", "portable", "context", "recall", "vault"},
        "answer": (
            "MemSync is OpenGradient's portable AI memory layer for universal personalization, announced "
            "September 2025.\n\n"
            "The core idea: your AI context should belong to you and travel with you. MemSync is an "
            "encrypted memory vault that moves across apps, devices, and chains, giving any AI application "
            "a persistent, private understanding of who you are without you having to re-explain yourself "
            "every session.\n\n"
            "It enables deep user personalization from derived user insights, and because it is built on "
            "OpenGradient's verifiable infrastructure, even your memories have cryptographic proof.\n\n"
            "Try it: app.memsync.ai  |  More: opengradient.ai/memsync"
        ),
    },
    {
        "key": "model_hub",
        "words": {"hub", "model", "models", "registry", "huggingface", "filestore", "upload", "download"},
        "answer": (
            "The OpenGradient Model Hub is the Web3 answer to HuggingFace: a permissionless, "
            "censorship-resistant registry for open-source AI models.\n\n"
            "Any developer can freely upload, download, or access any AI model through a familiar "
            "web portal with direct integration into OpenGradient's blockchain network. Models are "
            "stored in a decentralized filestore on Walrus, ensuring immutability and transparent "
            "version control. No permission required. The Hub currently hosts over 2,000 models.\n\n"
            "Models deployed to the Hub can be called directly from Solidity smart contracts through "
            "precompiles, enabling on-chain AI inference with a simple function call.\n\n"
            "Explore: hub.opengradient.ai"
        ),
    },
    {
        "key": "bitquant",
        "words": {"bitquant", "trading", "trade", "trader", "quant", "quantitative", "defi", "portfolio", "invest"},
        "answer": (
            "BitQuant is OpenGradient's open-source AI agent framework for building quantitative AI agents, "
            "open-sourced under MIT license on October 29, 2025, after a private beta with over 50,000 users.\n\n"
            "Its modular architecture has three layers. The Oracle is the data and execution layer, "
            "aggregating information from on-chain sources like Solana RPC and DeFi protocols including "
            "Orca and Solend, plus data aggregators like CoinGecko and DeFiLlama. The Brain is the "
            "decision-making engine, using a Router LLM to interpret natural language user prompts and "
            "direct them to specialist agents for analytics or investment execution. The Trader is the "
            "execution layer that converts decisions into verifiable on-chain transactions.\n\n"
            "Every decision is cryptographically proven through OpenGradient's infrastructure.\n\n"
            "More: opengradient.ai/bitquant  |  GitHub: github.com/OpenGradient/BitQuant"
        ),
    },
    {
        "key": "twin_fun",
        "words": {"twin", "twins", "twinfun", "digital", "persona"},
        "answer": (
            "Twin.fun is OpenGradient's AI digital twins marketplace, announced November 2025. "
            "The tagline: Trade Minds, Not Tokens.\n\n"
            "Each twin is an AI version of a real person. Fans buy access keys on a bonding curve market, "
            "meaning the more popular a twin, the higher the price. Creators earn fees whenever someone "
            "buys a key or chats with their twin. Every interaction runs on OpenGradient's verifiable "
            "infrastructure, so twin outputs are cryptographically attested.\n\n"
            "Live at: twin.fun"
        ),
    },
    {
        "key": "haca",
        "words": {"haca", "hybrid", "architecture", "compute", "sprinter", "judge", "librarian", "inference", "validators", "fast", "speed", "instant", "latency", "pipe", "parallel"},
        "answer": (
            "HACA stands for Hybrid AI Compute Architecture. It is OpenGradient's solution to the core "
            "problem of on-chain AI: you cannot ask every validator to re-run expensive AI models.\n\n"
            "HACA solves this through node specialization. The Full Node, called the Judge, runs the "
            "EVM state-transition, re-executes transactions, and verifies ZK proofs and TEE attestations. "
            "The Inference Node, called the Sprinter, is a stateless GPU or TPU worker that streams model "
            "weights, runs the forward pass, and returns output plus its proof. The Storage Node, called "
            "the Librarian, maintains the decentralized filestore, shards model checkpoints on Walrus, "
            "and keeps version history. Data Nodes fetch external real-world information like price feeds "
            "using TEE guarantees.\n\n"
            "PIPE (Parallelised Inference Pre-Execution Engine) runs inference before block production "
            "so slow AI models never delay the chain. Inference returns to you instantly with the same "
            "latency as a centralized API. The cryptographic proof settles in the background."
        ),
    },
    {
        "key": "proof",
        "words": {"proof", "proofs", "verify", "verified", "verification", "consensus", "settlement", "onchain", "chain", "attest", "cometbft", "breadcrumb", "audit"},
        "answer": (
            "Every inference on OpenGradient leaves a cryptographic breadcrumb baked directly into the "
            "block itself. ZK receipts, TEE attestations, and optimistic-challenge hashes sit beside "
            "calldata, never on a side server.\n\n"
            "Once a block lands in consensus using CometBFT, both the coins and the computation that "
            "produced them are permanently safeguarded on the ledger. A light client on a phone can "
            "fetch one block header, re-run the verifier, and prove the model computed exactly what "
            "the chain claims it did.\n\n"
            "Developers can choose their verification method per inference: TEE for hardware-based "
            "trust, ZKML for mathematical certainty, or optimistic for speed. You can even mix "
            "methods within a single transaction.\n\n"
            "Audit any inference: explorer.opengradient.ai"
        ),
    },
    {
        "key": "zkml",
        "words": {"zkml", "zk", "zero", "knowledge", "mathematical", "proof"},
        "answer": (
            "ZKML stands for Zero-Knowledge Machine Learning. It generates a mathematical proof that "
            "a specific AI model produced a specific output, providing absolute cryptographic certainty "
            "without requiring anyone to trust the hardware.\n\n"
            "OpenGradient supports ZKML as one option in its verification spectrum, alongside TEE and "
            "optimistic modes. ZKML is suited for high-stakes use cases like on-chain DeFi decisions "
            "or compliance workflows where mathematical proof is needed, not just hardware-based trust. "
            "Developers can mix ZKML for one model with TEE for another within the same transaction, "
            "depending on what each inference is used for."
        ),
    },
    {
        "key": "nova_testnet",
        "words": {"nova", "testnet", "devnet", "faucet", "explorer", "network", "mainnet", "live"},
        "answer": (
            "OpenGradient framed its testnet launch as the beginning of the Third Era of Blockspace: "
            "Era 1 moved numbers (Bitcoin, 2009), Era 2 moved logic (Ethereum, 2015), Era 3 moves "
            "meaning (OpenGradient, 2025). A block now records not just what happened and how, but why.\n\n"
            "The testnet is live and open to developers. It is EVM-compatible, running CometBFT consensus, "
            "with full HACA node infrastructure and x402 payment integration.\n\n"
            "Block explorer: explorer.opengradient.ai\n"
            "Free testnet tokens: faucet.opengradient.ai\n"
            "Documentation: docs.opengradient.ai"
        ),
    },
    {
        "key": "neuro_stack",
        "words": {"neuro", "stack", "rollup", "rollups", "modular", "layer2", "l2"},
        "answer": (
            "The Neuro Stack is OpenGradient's framework that lets development teams build their own "
            "Layer 2 rollups with custom tokens and rules, while tapping OpenGradient's AI computation "
            "layer as a shared service.\n\n"
            "An inference call leaves your chain, specialized nodes on the hub compute it, and a proof "
            "comes back inside the very block that advances your state. Your rollup gets AI-as-a-service "
            "without running its own inference infrastructure. This makes OpenGradient credibly neutral "
            "infrastructure for the modular blockchain ecosystem.\n\n"
            "Read more: opengradient.ai/blog"
        ),
    },
    {
        "key": "team",
        "words": {"team", "founder", "founders", "founded", "ceo", "cto", "matthew", "adam", "balogh", "wang", "who"},
        "answer": (
            "OpenGradient was founded in 2023 and is headquartered in New York City.\n\n"
            "Matthew Wang is CEO, previously a research engineer at Two Sigma.\n"
            "Adam Balogh is CTO, previously Head of AI Platform at Palantir.\n"
            "The co-founders are described as veterans from Google, Meta, and Palantir.\n\n"
            "Advisors include Balaji Srinivasan (ex-Coinbase CTO), Illia Polosukhin (Transformer "
            "architecture co-inventor and NEAR co-founder), Sandeep Nailwal (Polygon CEO), "
            "Ekram Ahmed (Head of Marketing at Celestia), and Bruno Faviero (CoFounder of Magna).\n\n"
            "The company has 7 core employees and is actively hiring across research, engineering, "
            "and product roles. Positions listed at opengradient.ai/careers."
        ),
    },
    {
        "key": "funding",
        "words": {"fund", "funding", "funded", "raised", "raise", "investor", "investors", "backed", "a16z", "coinbase", "capital", "venture", "seed", "money"},
        "answer": (
            "OpenGradient raised $8.5M in seed funding, announced October 2024.\n\n"
            "Investors: a16z Crypto Startup Accelerator (CSX), Foresight Ventures, SV Angel, "
            "Coinbase Ventures, SALT Fund, and Symbolic Capital.\n\n"
            "OpenGradient was also selected for the a16z Crypto Fall CSX program, the accelerator "
            "arm of Andreessen Horowitz's crypto fund.\n\n"
            "Advisors: Balaji Srinivasan, Illia Polosukhin (Transformer co-inventor, NEAR co-founder), "
            "Sandeep Nailwal (Polygon CEO), Ekram Ahmed (Celestia), Bruno Faviero (Magna)."
        ),
    },
    {
        "key": "sdk",
        "words": {"sdk", "install", "developer", "developers", "api", "python", "code", "cli", "started", "start", "build", "setup", "integrate", "solidml", "langchain", "precompile"},
        "answer": (
            "The OpenGradient Python SDK is a drop-in replacement for OpenAI and Anthropic APIs "
            "that adds cryptographic attestation for every inference call.\n\n"
            "Install: pip install opengradient\n\n"
            "It supports models from OpenAI, Anthropic, Google, and xAI through a unified interface "
            "with TEE verification. The SDK also integrates directly with LangChain, enabling TEE-secured "
            "LLM inference in AI agents without context window pollution.\n\n"
            "For LLM inference the response includes a transaction hash. For ML model inference on the "
            "Alpha Testnet, workflows and custom model execution are available.\n\n"
            "SolidML is the companion Solidity library that enables AI inference directly from smart "
            "contracts through precompiles, meaning you can call an AI model from Solidity as simply "
            "as calling a function.\n\n"
            "Full docs: docs.opengradient.ai  |  GitHub: github.com/OpenGradient/OpenGradient-SDK"
        ),
    },
    {
        "key": "partnerships",
        "words": {"partner", "partners", "partnership", "eigenlayer", "nuffle", "langchain", "carecentra", "sparsity", "integration"},
        "answer": (
            "OpenGradient's key ecosystem partners:\n\n"
            "EigenLayer: restaking infrastructure for scalable decentralized AI inference.\n"
            "Nuffle Labs: proof settlement infrastructure.\n"
            "LangChain: TEE-secured LLM inference for AI agents, announced integration bringing "
            "verifiable ML inference to agents without context window pollution.\n"
            "CareCentra: healthcare AI with TEE-secured compute.\n"
            "Sparsity XYZ: on-chain AI for gaming applications.\n\n"
            "Latest: x.com/OpenGradient"
        ),
    },
    {
        "key": "walrus",
        "words": {"walrus", "storage", "blob", "filestore", "shards"},
        "answer": (
            "Walrus is the decentralized blob storage layer OpenGradient uses for AI model files, "
            "checkpoints, and cryptographic proofs.\n\n"
            "The Storage Node (the Librarian in HACA) shards model checkpoints across Walrus and "
            "maintains version history. Only a small reference ID is stored on-chain, keeping the "
            "blockchain lean and fast. Full data lives on Walrus with near-data availability "
            "guarantees so it cannot be lost or censored."
        ),
    },
    {
        "key": "use_cases",
        "words": {"cases", "built", "applications", "application", "example", "examples", "build", "dapp", "dapps"},
        "answer": (
            "OpenGradient powers verifiable AI across industries:\n\n"
            "DeFi: AI trading with cryptographically proven decisions via BitQuant. "
            "AMM dynamic fee optimization using on-chain ML models.\n"
            "Healthcare: Tamper-proof AI for medical decisions with TEE-secured compute (CareCentra).\n"
            "AI Agents: Autonomous agents that pay for their own compute via x402 with no human approval.\n"
            "Personalization: Portable AI memory that travels across apps and devices (MemSync).\n"
            "Digital Twins: AI personas of real people with verifiable interactions (Twin.fun).\n"
            "DePIN: ML models for decentralized physical infrastructure network reputation.\n"
            "Gaming: On-chain AI for smarter NPCs and game mechanics (Sparsity XYZ).\n"
            "Robotics: Verifiable execution layer for autonomous systems.\n"
            "Smart Contracts: Direct AI inference from Solidity via precompiles (SolidML).\n\n"
            "More at: opengradient.ai/blog"
        ),
    },
    {
        "key": "manifesto",
        "words": {"manifesto", "mission", "vision", "owned", "ownership", "user-owned", "believe", "belief", "philosophy"},
        "answer": (
            "OpenGradient's mission is direct: the future of AI is user-owned.\n\n"
            "The manifesto starts with a clear premise: existing AI is a black box that lacks "
            "transparency and traps user data within closed platforms. Their response is to build "
            "technology that enables verifiable compute, supports persistent memory, and secures "
            "user-owned data, unlocking human-level intelligence powered by private data.\n\n"
            "Core beliefs:\n"
            "Individuals should control their AI interactions.\n"
            "Users should own their context across different platforms.\n"
            "Every AI output should have cryptographic proof of authenticity.\n"
            "AI systems should remember, learn, and grow alongside users, always in service of "
            "human agency and autonomy.\n\n"
            "Read: opengradient.ai/manifesto"
        ),
    },
    {
        "key": "community",
        "words": {"community", "discord", "twitter", "social", "join", "follow", "links", "website", "contact", "newsletter"},
        "answer": (
            "Join the OpenGradient community:\n\n"
            "Website: opengradient.ai\n"
            "Twitter: x.com/OpenGradient\n"
            "Discord: discord.gg/2t5sx5BCpB\n"
            "GitHub: github.com/OpenGradient\n"
            "Docs: docs.opengradient.ai\n"
            "Model Hub: hub.opengradient.ai\n"
            "Block Explorer: explorer.opengradient.ai\n"
            "Faucet: faucet.opengradient.ai\n"
            "Email: team@opengradient.ai"
        ),
    },
    {
        "key": "robotics",
        "words": {"robot", "robots", "robotics", "autonomous", "execution", "agent", "agents"},
        "answer": (
            "OpenGradient has published research on verifiable AI as the missing execution layer "
            "for robotics. The argument: autonomous robots and agents making real-world decisions "
            "need the same cryptographic accountability as financial transactions. You must be able "
            "to prove exactly why a system did what it did.\n\n"
            "OpenGradient's infrastructure provides that execution layer. When machines act, the "
            "computation needs proof. Without it, you are trusting a black box.\n\n"
            "Read: opengradient.ai/blog/verifiable-agents-robotics-execution-layer"
        ),
    },
    {
        "key": "proofgraph",
        "words": {"proofgraph", "graph", "verifiable", "reasoning", "mint", "minted", "intelligence"},
        "answer": (
            "ProofGraph is a verifiable intelligence graph built on OpenGradient. "
            "Every question you ask creates a permanent, cryptographically-proven reasoning chain "
            "recorded on the OpenGradient blockchain.\n\n"
            "Each question runs through three parallel TEE-verified reasoning nodes: Core Analysis, "
            "Evidence and Context, and Key Takeaways. Each node receives a real on-chain transaction "
            "hash. A final Synthesis node combines all three into your verified answer.\n\n"
            "The graph grows over time. New questions discover and cite existing verified nodes, "
            "compounding knowledge like an on-chain knowledge base where every fact has "
            "cryptographic proof. Intelligence accumulates and is owned by the network.\n\n"
            "Built with: TEE inference, x402 payments, MemSync memory, Digital Twin routing."
        ),
    },
]


def get_focused_answer(question: str) -> str:
    """
    Find the best matching topic for a question regardless of phrasing.
    'og' and 'opengradient' score 0.3 so specific product keywords always
    beat them when a specific product is being asked about.
    """
    q_words = set(_re.sub(r'[^a-z0-9 ]', ' ', question.lower()).split()) - _STOP
    weak    = {"og", "opengradient"}

    best_answer = ""
    best_score  = 0.0

    for topic in TOPICS:
        matches = q_words & topic["words"]
        if not matches:
            continue
        score = sum(0.3 if w in weak else 1.0 for w in matches)
        if score > best_score:
            best_score  = score
            best_answer = topic["answer"]

    return best_answer if best_score > 0 else ""
