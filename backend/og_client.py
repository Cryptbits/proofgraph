# ================================================================
# og_client.py — OpenGradient SDK Wrapper (MVP / Live)
#
# Correct OG SDK:
#   client = og.Client(private_key="0x...")
#   resp   = client.llm_chat(model_cid, messages,
#                inference_mode=og.LlmInferenceMode.TEE, ...)
# Response is a tuple: (model_output, tx_hash) for TEE
#                      (model_output,)          for VANILLA
# model_output has .choices[0].message.content  (OpenAI-style)
# ================================================================

import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

# Model priority list — tried in order until one succeeds
OG_MODELS = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.2",
]

_PLACEHOLDER_KEYS = {
    "", "0x", "0xyour_private_key_here",
    "0xyour_wallet_private_key_here", "0x...",
    "your_private_key", "add_your_key_here",
}


class OGClient:

    def __init__(self):
        self.private_key  = os.getenv("OG_PRIVATE_KEY", "").strip()
        self.email        = os.getenv("OG_EMAIL", "").strip()
        self.password     = os.getenv("OG_PASSWORD", "").strip()
        self._executor    = ThreadPoolExecutor(max_workers=4)
        self._client      = None   # og.Client instance
        self._og          = None   # opengradient module
        self._initialized = False
        self.mode         = "KNOWLEDGE"
        self.wallet       = None

    # ── Initialization ─────────────────────────────────────────

    def _init_sdk(self):
        if self.private_key.lower() in _PLACEHOLDER_KEYS:
            print("ℹ️  No OG_PRIVATE_KEY set — Knowledge Mode")
            print("   Add private key to backend/.env for live TEE inference")
            return

        try:
            import opengradient as og
            self._og = og

            if self.email and self.password:
                self._client = og.Client(
                    private_key=self.private_key,
                    email=self.email,
                    password=self.password,
                )
            else:
                self._client = og.Client(private_key=self.private_key)

            self._initialized = True
            self.mode   = "OG_LIVE"
            self.wallet = self.private_key[:8] + "..." + self.private_key[-4:]
            print(f"✅ OpenGradient SDK initialized — LIVE MODE")
            print(f"   Wallet : {self.wallet}")
            print(f"   Models : {OG_MODELS[0]}")

        except ImportError:
            print("❌ opengradient not installed — run: pip install opengradient")
        except Exception as e:
            print(f"⚠️  OG SDK init error: {e}")
            print("   Falling back to Knowledge Mode")

    async def initialize(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._init_sdk)
        print(f"   ProofGraph mode: {self.mode}")

    # ── Core inference call ─────────────────────────────────────

    def _call_og(self, messages: list, max_tokens: int) -> Dict[str, Any]:
        """
        Call og.Client.llm_chat(). Tries TEE first, falls back to VANILLA.

        OG SDK returns:
          TEE     → tuple: (ChatCompletionOutput, tx_hash_str)
          VANILLA → ChatCompletionOutput  (single object)

        ChatCompletionOutput.choices[0].message.content  → text
        """
        og   = self._og
        cli  = self._client
        last_err = None

        for model in OG_MODELS:
            try:
                print(f"   → Calling OG [{model}] ...")

                # ── Attempt TEE ───────────────────────────────
                try:
                    raw = cli.llm_chat(
                        model_cid      = model,
                        messages       = messages,
                        inference_mode = og.LlmInferenceMode.TEE,
                        max_tokens     = max_tokens,
                        temperature    = 0.3,
                    )
                    content, tx_hash, payment_hash = self._parse_response(raw)
                    mode     = "TEE"
                    verified = True
                    print(f"   ✅ TEE inference complete — tx: {tx_hash}")

                except Exception as tee_err:
                    if self._is_payment_error(tee_err):
                        raise RuntimeError(f"PAYMENT_REQUIRED:{tee_err}")
                    print(f"   ⚠️  TEE failed ({tee_err}), trying VANILLA...")

                    raw = cli.llm_chat(
                        model_cid      = model,
                        messages       = messages,
                        inference_mode = og.LlmInferenceMode.VANILLA,
                        max_tokens     = max_tokens,
                        temperature    = 0.3,
                    )
                    content, tx_hash, payment_hash = self._parse_response(raw)
                    mode     = "VANILLA"
                    verified = False
                    print(f"   ✅ VANILLA inference complete")

                if not content or len(content.strip()) < 5:
                    raise ValueError("Empty response from OG")

                return {
                    "content":      content,
                    "tx_hash":      tx_hash,
                    "payment_hash": payment_hash,
                    "model":        model,
                    "mode":         mode,
                    "verified":     verified,
                    "timestamp":    datetime.utcnow().isoformat(),
                    "source":       "opengradient_live",
                }

            except RuntimeError as e:
                if "PAYMENT_REQUIRED" in str(e):
                    raise
                last_err = e
                print(f"   ⚠️  {model} failed: {e}")
                continue
            except Exception as e:
                last_err = e
                print(f"   ⚠️  {model} error: {e}")
                continue

        raise RuntimeError(f"All OG models failed. Last error: {last_err}")

    def _parse_response(self, raw) -> tuple:
        """
        Parse OG SDK response into (content, tx_hash, payment_hash).

        Handles all known OG response formats:
         - tuple(output, tx_hash)
         - tuple(output, tx_hash, payment_hash)
         - raw ChatCompletionOutput object
         - dict with 'choices' key
        """
        tx_hash      = None
        payment_hash = None
        output       = raw

        # Unpack tuple formats
        if isinstance(raw, (tuple, list)):
            if len(raw) >= 2:
                output  = raw[0]
                tx_hash = str(raw[1]) if raw[1] else None
            if len(raw) >= 3:
                payment_hash = str(raw[2]) if raw[2] else None

        # Extract content
        content = self._extract_content(output)

        # Try pulling hashes from object attributes if not in tuple
        if tx_hash is None:
            tx_hash = (
                getattr(output, "tx_hash", None) or
                getattr(output, "transaction_hash", None)
            )
        if payment_hash is None:
            payment_hash = (
                getattr(output, "payment_hash", None) or
                getattr(output, "payment_transaction_hash", None)
            )

        return content, tx_hash, payment_hash

    def _extract_content(self, r) -> str:
        """Extract text content from any OG/OpenAI-style response object."""
        if r is None:
            return ""
        if isinstance(r, str):
            return r

        # OpenAI-style: choices[0].message.content
        if hasattr(r, "choices") and r.choices:
            try:
                return r.choices[0].message.content or ""
            except Exception:
                pass

        # Dict OpenAI-style
        if isinstance(r, dict):
            try:
                return r["choices"][0]["message"]["content"]
            except Exception:
                return str(r.get("content", r.get("output", str(r))))

        # Direct attributes
        for attr in ("content", "output", "text", "completion"):
            val = getattr(r, attr, None)
            if val:
                return str(val)

        return str(r)

    def _is_payment_error(self, err) -> bool:
        msg = str(err).lower()
        return any(x in msg for x in
                   ["insufficient", "balance", "payment", "402", "funds", "no funds"])

    # ── Public async interface ─────────────────────────────────

    async def infer_tee(
        self,
        prompt:        str,
        system_prompt: str,
        max_tokens:    int = 600,
    ) -> Dict[str, Any]:
        """
        Main entry point. Uses live OG if wallet funded,
        otherwise answers from knowledge base.
        """
        if self._initialized and self._client:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ]
            loop = asyncio.get_event_loop()
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        lambda: self._call_og(messages, max_tokens),
                    ),
                    timeout=45.0,  # fail fast — don't hang forever
                )
            except asyncio.TimeoutError:
                print("   ⚠️  OG call timed out (45s) — falling back for this call only")
                # Do NOT flip self.mode — wallet may be funded, just a slow call
            except RuntimeError as e:
                if "PAYMENT_REQUIRED" in str(e):
                    print("   ⚠️  Insufficient $OPG — this call falls back to knowledge")
                    # Do NOT flip self.mode — user may top up between queries
                else:
                    print(f"   ⚠️  OG error: {e} — falling back for this call only")
                    # Do NOT flip self.mode permanently

        return self._knowledge_inference(prompt, system_prompt)

    def _knowledge_inference(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Structured answer from the local OG knowledge base."""
        from og_knowledge import get_focused_answer

        answer = get_focused_answer(prompt)

        if not answer:
            answer = (
                "OpenGradient is a decentralized AI infrastructure protocol — "
                "a Layer 1 blockchain where every AI inference is cryptographically "
                "proven on-chain. Products include TEE inference, x402 micropayments, "
                "MemSync memory, Model Hub, BitQuant, and Twin.fun.\n\n"
                "🌐 opengradient.ai  •  𝕏 x.com/OpenGradient  •  Discord: discord.gg/2t5sx5BCpB"
            )

        return {
            "content":      answer,
            "tx_hash":      None,
            "payment_hash": None,
            "model":        "og-knowledge-base",
            "mode":         "KNOWLEDGE",
            "verified":     False,
            "timestamp":    datetime.utcnow().isoformat(),
            "source":       "knowledge_base",
        }


# ── Singleton ──────────────────────────────────────────────────
_og_client: Optional[OGClient] = None


async def get_og_client() -> OGClient:
    global _og_client
    if _og_client is None:
        _og_client = OGClient()
        await _og_client.initialize()
    return _og_client
