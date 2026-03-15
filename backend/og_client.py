# og_client.py
# OpenGradient SDK wrapper using the current API.
# Docs: docs.opengradient.ai/developers/sdk/llm.html
#
# Current API (as of 2026):
#   llm = og.LLM(private_key="0x...")
#   await llm.ensure_opg_approval(opg_amount=5.0)
#   result = await llm.chat(model=og.TEE_LLM.GPT_4_1_2025_04_14, messages=[...])
#   result.chat_output['content']  -> text
#   result.payment_hash            -> payment tx hash

import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

_PLACEHOLDER_KEYS = {
    "", "0x", "0xyour_private_key_here",
    "0xyour_wallet_private_key_here", "0x...",
    "your_private_key", "add_your_key_here",
}

# Default model — GPT-4.1 via OG TEE
DEFAULT_MODEL = "openai/gpt-4.1-2025-04-14"


class OGClient:

    def __init__(self):
        self.private_key  = os.getenv("OG_PRIVATE_KEY", "").strip()
        self._llm         = None
        self._og          = None
        self._initialized = False
        self.mode         = "KNOWLEDGE"
        self.wallet       = None

    def _init_sdk(self):
        if self.private_key.lower() in _PLACEHOLDER_KEYS:
            print("No OG_PRIVATE_KEY set — running in Knowledge Mode")
            return

        try:
            import opengradient as og
            self._og  = og

            # New API: og.LLM — not og.Client
            self._llm = og.LLM(private_key=self.private_key)

            # Ensure Permit2 approval so payments work automatically
            try:
                approval = self._llm.ensure_opg_approval(opg_amount=10.0)
                print(f"Permit2 approval OK — allowance: {getattr(approval, 'allowance_after', 'set')}")
            except Exception as e:
                print(f"Permit2 approval note: {e} — will attempt on first call")

            self._initialized = True
            self.mode         = "OG_LIVE"
            self.wallet       = self.private_key[:8] + "..." + self.private_key[-4:]
            print(f"OpenGradient SDK initialized — OG LIVE")
            print(f"  Wallet: {self.wallet}")
            print(f"  Model:  {DEFAULT_MODEL}")

        except ImportError:
            print("opengradient not installed — run: pip install opengradient")
        except Exception as e:
            print(f"OG SDK init error: {e}")
            print("Falling back to Knowledge Mode")

    async def initialize(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._init_sdk)
        print(f"ProofGraph mode: {self.mode}")

    async def infer_tee(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 400,
    ) -> Dict[str, Any]:
        """
        Run inference via OpenGradient TEE.
        Falls back to local knowledge base if SDK not initialized.
        """
        if self._initialized and self._llm:
            try:
                return await asyncio.wait_for(
                    self._call_llm(prompt, system_prompt, max_tokens),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                print("OG call timed out (60s) — using knowledge base for this call")
            except Exception as e:
                print(f"OG inference error: {e} — using knowledge base for this call")

        return self._knowledge_inference(prompt, system_prompt)

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """
        Call og.LLM.chat() with the current API.
        result.chat_output['content'] -> text
        result.payment_hash           -> payment hash string
        """
        og = self._og

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ]

        # Determine which model enum to use
        model = self._get_model()

        result = await self._llm.chat(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )

        content      = self._extract_content(result)
        payment_hash = getattr(result, "payment_hash", None)
        # payment_hash acts as the tx hash in the new API
        tx_hash      = str(payment_hash) if payment_hash else None

        print(f"OG TEE inference complete — payment: {tx_hash}")

        return {
            "content":      content,
            "tx_hash":      tx_hash,
            "payment_hash": tx_hash,
            "model":        DEFAULT_MODEL,
            "mode":         "TEE",
            "verified":     True,
            "timestamp":    datetime.utcnow().isoformat(),
            "source":       "opengradient_live",
        }

    def _get_model(self):
        """Return the correct og.TEE_LLM enum for the default model."""
        try:
            og = self._og
            # Try GPT-4.1 first (current default)
            if hasattr(og, "TEE_LLM"):
                tee = og.TEE_LLM
                # Try each model name in preference order
                for attr in ["GPT_4_1_2025_04_14", "GPT_5", "GPT_4_1", "CLAUDE_SONNET_4_6"]:
                    if hasattr(tee, attr):
                        return getattr(tee, attr)
            # Fallback: return string model name (older SDK versions)
            return DEFAULT_MODEL
        except Exception:
            return DEFAULT_MODEL

    def _extract_content(self, result) -> str:
        """Extract text from og.LLM response."""
        if result is None:
            return ""

        # New API: result.chat_output is a dict with 'content' key
        chat_output = getattr(result, "chat_output", None)
        if chat_output:
            if isinstance(chat_output, dict):
                return chat_output.get("content", "") or ""
            return str(chat_output)

        # Fallback: completion output
        completion_output = getattr(result, "completion_output", None)
        if completion_output:
            return str(completion_output)

        # Fallback: OpenAI-style choices
        if hasattr(result, "choices") and result.choices:
            try:
                return result.choices[0].message.content or ""
            except Exception:
                pass

        # Last resort
        for attr in ("content", "output", "text"):
            val = getattr(result, attr, None)
            if val:
                return str(val)

        return str(result)

    def _knowledge_inference(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Local knowledge base fallback — used when OG SDK is unavailable."""
        from og_knowledge import get_focused_answer

        answer = get_focused_answer(prompt)

        if not answer:
            answer = (
                "OpenGradient is the first permissionless platform for open-source AI model "
                "hosting, secure inference, agentic reasoning, and application deployment. "
                "Every inference is cryptographically verified on-chain via TEE.\n\n"
                "Website: opengradient.ai  |  Twitter: x.com/OpenGradient"
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


_og_client: Optional[OGClient] = None


async def get_og_client() -> OGClient:
    global _og_client
    if _og_client is None:
        _og_client = OGClient()
        await _og_client.initialize()
    return _og_client
