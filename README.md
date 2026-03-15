# ⬡ ProofGraph — Verifiable Intelligence Graph

> Every AI reasoning step becomes a permanent, cryptographically-proven node in a public knowledge graph. Built entirely on OpenGradient's decentralized AI infrastructure.

---

## What This Is

ProofGraph turns ephemeral AI answers into **persistent, verifiable reasoning infrastructure**.

When you ask a question:
1. OpenGradient TEE LLM decomposes it into reasoning tasks
2. Each task runs as a **TEE-secured inference** — cryptographically attested
3. Each step becomes an immutable **node with on-chain proof**
4. MemSync stores your reasoning history persistently
5. x402 micropayments fire per inference automatically
6. The graph grows — future queries **reuse existing verified nodes**

---

## OpenGradient Tech Stack

| Component | Role in ProofGraph |
|---|---|
| **TEE LLM Inference** | Every reasoning node runs inside a verified enclave |
| **x402 micropayments** | Automatic per-inference payment via $OPG on Base Sepolia |
| **MemSync** | Persistent cross-session memory — your intellectual identity |
| **Model Hub** | Reasoning models versioned and pinned |
| **On-chain ML Workflows** | Dispute arbitration + confidence scoring |
| **Digital Twins** | Expert oracle routing (extension) |

---

## Prerequisites

- Ubuntu 20.04+ (or WSL2 on Windows)
- Python 3.10, 3.11, or 3.12
- A MetaMask wallet with $OPG testnet tokens (Base Sepolia)
- MemSync API key (https://api.memchat.io)
- OpenGradient Model Hub account (https://hub.opengradient.ai)

---

## Step-by-Step Setup

### Step 1 — Clone / Enter project directory

```bash
cd proofgraph
```

### Step 2 — Run setup script

```bash
chmod +x setup.sh
./setup.sh
```

This installs all system and Python dependencies.

### Step 3 — Activate the virtual environment

```bash
source venv/bin/activate
```

### Step 4 — Configure OpenGradient SDK

Run the OG setup wizard:

```bash
opengradient config init
```

This guides you to:
- Connect your wallet
- Fund with $OPG from the testnet faucet
- Verify your configuration

Test it works:

```bash
opengradient config show
```

### Step 5 — Configure your .env

```bash
nano backend/.env
```

Fill in:

```
OG_PRIVATE_KEY=0xyour_private_key
OG_EMAIL=your@email.com
OG_PASSWORD=your_password
MEMSYNC_API_KEY=your_memsync_key
```

Save with: `Ctrl+O` → Enter → `Ctrl+X`

### Step 6 — Start the backend

```bash
cd backend
python main.py
```

You should see:
```
✅ OpenGradient client initialized
✅ ProofGraph backend ready
🚀 ProofGraph Backend starting on http://0.0.0.0:8000
```

### Step 7 — Open the frontend

Open a new terminal (or browser):

```bash
# Option A: Open directly in browser
xdg-open frontend/index.html

# Option B: Serve with Python (recommended for WebSocket)
cd frontend && python3 -m http.server 3000
# Then open http://localhost:3000
```

### Step 8 — Get testnet tokens (if needed)

Visit: https://faucet.opengradient.ai

Enter your wallet address to receive $OPG on Base Sepolia.

---

## Using Docker (Alternative)

If you prefer Docker:

```bash
# Copy and configure env
cp backend/.env.example backend/.env
nano backend/.env  # fill in your keys

# Build and run
docker-compose up --build

# Frontend: open frontend/index.html in browser
```

---

## How to Use ProofGraph

1. **Open the frontend** at http://localhost:3000
2. **Type a question** in the query box (e.g. "What risks does restaking introduce to Ethereum?")
3. **Optional**: Enter your wallet address for MemSync profile tracking
4. **Click "Run Verifiable Reasoning"**
5. **Watch live** as reasoning nodes are minted in the TEE
6. **Explore the graph** — click nodes to see TEE proofs, payment hashes
7. **Challenge nodes** — contest reasoning with your own counter-argument
8. **View your profile** — see accumulated memories and citation economy

---

## Project Structure

```
proofgraph/
├── backend/
│   ├── main.py              # FastAPI server + WebSocket
│   ├── graph_engine.py      # Core reasoning pipeline
│   ├── og_client.py         # OpenGradient SDK wrapper
│   ├── memsync_client.py    # MemSync REST API client
│   ├── database.py          # SQLite persistence
│   ├── models.py            # Pydantic data models
│   └── .env                 # Your credentials (git-ignored)
├── frontend/
│   └── index.html           # Complete single-file app
├── requirements.txt
├── setup.sh
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/query` | Submit a question |
| GET | `/api/graph` | Full graph (D3-ready) |
| GET | `/api/session/{id}` | Get session + nodes |
| GET | `/api/node/{id}` | Get node with proof |
| POST | `/api/challenge` | Challenge a node |
| GET | `/api/profile/{wallet}` | MemSync user profile |
| GET | `/api/stats` | Network statistics |
| WS | `/ws/{session_id}` | Live reasoning stream |

API docs: http://localhost:8000/docs

---

## Troubleshooting

**"OpenGradient client init failed"**
→ Check `opengradient config show`
→ Make sure wallet has $OPG tokens on Base Sepolia

**"MemSync: No API key found"**
→ App still works — just uses local memory only
→ Get key from https://api.memchat.io

**WebSocket not connecting**
→ Make sure backend is running: `python main.py`
→ Check CORS settings if using different port

**TEE inference failing**
→ The SDK falls back to VANILLA mode automatically
→ Demo mode works without any credentials for UI testing

---

Built on **OpenGradient** — Trustless, Verifiable, Open AI Infrastructure
