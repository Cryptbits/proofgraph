# ProofGraph

A verifiable intelligence graph built on OpenGradient. Every question you ask becomes a cryptographically proven reasoning chain recorded permanently on the OpenGradient blockchain.

Live: [proofgraph.vercel.app](https://proofgraph.vercel.app)
Code: [github.com/Cryptbits/proofgraph](https://github.com/Cryptbits/proofgraph)

---

## What it does

Most AI tools give you an answer and ask you to trust it. ProofGraph proves the answer instead.

When you submit a question, three parallel reasoning nodes fire simultaneously inside OpenGradient's TEE. Each node approaches the problem from a distinct angle. Core Analysis breaks down the technical mechanisms. Evidence and Context brings the real-world facts and comparisons. Key Takeaways gives the practical implications. All three run at the same time, each inside a hardware-sealed AWS Nitro Enclave, each paying for itself autonomously via x402 in $OPG on Base Sepolia, each producing its own transaction hash on the OpenGradient Nova Testnet.

Once all three complete, a fourth node — the Final Synthesis — takes all three outputs and combines them into one clear, structured, verified answer. That is four TEE inference calls, four transaction hashes, and four nodes on the graph per query.

Every node appears live on a D3.js force graph as it completes. Every node is clickable. Every node links to [explorer.opengradient.ai](https://explorer.opengradient.ai) so the proof can be independently verified by anyone.

The graph grows over time. New questions find and cite verified nodes from previous sessions, building a permanent tamper-proof record where knowledge compounds across queries instead of resetting with every session.

---

## The OpenGradient stack

**TEE Inference**
All four inference calls run via `og.LLM` inside AWS Nitro Enclaves. The hardware proves each computation ran correctly and the output hash settles on-chain. No trust in any company required.

**x402 Payments**
Each of the four inference calls is paid per-request in $OPG via Permit2 on Base Sepolia, embedded directly inside the TEE. No subscriptions, no middleware, no human approval needed between the request and the compute.

**Digital Twin Routing**
Each of the three reasoning nodes routes to the most relevant specialist persona from Twin.fun based on the question topic. Technical questions go to an AI Research Expert. DeFi and protocol questions go to a DeFi Analyst. Investment and economics questions go to Naval Ravikant. Each twin's perspective shapes the node output before the synthesis step.

**MemSync**
Completed sessions are stored in OpenGradient's portable memory layer, giving the graph persistent cross-session context that carries forward with every new query.

**Nova Testnet**
Every proof hash from every node settles on the OpenGradient Nova Testnet. Every node detail panel in the UI links directly to the block explorer for public verification.

---

## Running locally

You need Python 3.11+, $OPG testnet tokens from [faucet.opengradient.ai](https://faucet.opengradient.ai), and Base Sepolia ETH for Permit2 gas from [alchemy.com/faucets/base-sepolia](https://www.alchemy.com/faucets/base-sepolia).

Clone the repo and run setup:

```bash
git clone https://github.com/Cryptbits/proofgraph
cd proofgraph
bash setup.sh
```

Add your wallet private key to `backend/.env`:

```
OG_PRIVATE_KEY=0x_your_private_key_here
```

Start the backend in one terminal:

```bash
source venv/bin/activate
cd backend && python main.py
```

Start the frontend in a second terminal:

```bash
cd frontend && python3 -m http.server 3000
```

Open [http://localhost:3000](http://localhost:3000).

---

## Deploying

**Backend on Render**
Connect the repo to [render.com](https://render.com), set `OG_PRIVATE_KEY` in the environment variables, and Render handles the rest via the Procfile.

**Frontend on Vercel**
Connect the repo to [vercel.com](https://vercel.com), set `BACKEND_URL` in `frontend/index.html` to your Render service URL, and push. Both platforms redeploy automatically on every push to main.

---

## Project structure

```
proofgraph/
  backend/
    main.py             FastAPI server, WebSocket streaming, event buffering
    graph_engine.py     3-node parallel pipeline and synthesis
    og_client.py        OpenGradient SDK wrapper using og.LLM and Permit2
    og_knowledge.py     OG knowledge base for offline fallback
    twin_router.py      Digital Twin routing engine
    memsync_client.py   MemSync memory storage
    database.py         SQLite persistence
    models.py           Pydantic data models
  frontend/
    index.html          Single-file UI with D3.js graph and WebSocket streaming
```

---

## Stack

| Layer | Technology |
|---|---|
| Verifiable inference | OpenGradient TEE via og.LLM |
| Payments | x402 with $OPG on Base Sepolia |
| Memory | OpenGradient MemSync |
| Digital Twins | Twin.fun persona routing |
| Proof settlement | OpenGradient Nova Testnet |
| Frontend | D3.js, vanilla JS, WebSockets |
| Backend | FastAPI, Python, SQLite |

---

## Security

Never commit your private key. The `backend/.env` file is in `.gitignore`. For production deployments, set `OG_PRIVATE_KEY` exclusively through your hosting platform's environment variable settings and never in code or config files.

---

## Links

[opengradient.ai](https://opengradient.ai) · [explorer.opengradient.ai](https://explorer.opengradient.ai) · [faucet.opengradient.ai](https://faucet.opengradient.ai) · [docs.opengradient.ai](https://docs.opengradient.ai) · [x.com/OpenGradient](https://x.com/OpenGradient) · [discord.gg/2t5sx5BCpB](https://discord.gg/2t5sx5BCpB)
