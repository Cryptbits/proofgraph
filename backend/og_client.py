# og_client.py
# OpenGradient SDK wrapper.
# Uses og.LLM — the current API as of 2026.
# Docs: docs.opengradient.ai/developers/sdk/llm.html

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
            print("No OG_PRIVATE_KEY set — Knowledge Mode")
            return

        try:
            import opengradient as og
            self._og  = og
            self._llm = og.LLM(private_key=self.private_key)

            try:
                approval = self._llm.ensure_opg_approval(opg_amount=10.0)
                print(f"Permit2 approval OK — allowance: {getattr(approval, 'allowance_after', 'set')}")
            except Exception as e:
                print(f"Permit2 note: {e}")

            self._initialized = True
            self.mode         = "OG_LIVE"
            self.wallet       = self.private_key[:8] + "..." + self.private_key[-4:]
            print(f"OpenGradient SDK initialized — OG LIVE")
            print(f"  Wallet: {self.wallet}")
            print(f"  Model:  {DEFAULT_MODEL}")

        except ImportError:
            print("opengradient package not installed — run: pip install opengradient")
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
        if self._initialized and self._llm:
            try:
                return await asyncio.wait_for(
                    self._call_llm(prompt, system_prompt, max_tokens),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                print("OG call timed out (60s)")
            except Exception as e:
                print(f"OG inference error: {e}")

        # Fallback — SDK not available
        return self._unavailable_fallback(prompt)

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ]

        model   = self._get_model()
        result  = await self._llm.chat(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )

        content      = self._extract_content(result)
        payment_hash = getattr(result, "payment_hash", None)
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
        try:
            og  = self._og
            if hasattr(og, "TEE_LLM"):
                tee = og.TEE_LLM
                for attr in ["GPT_4_1_2025_04_14", "GPT_5", "GPT_4_1", "CLAUDE_SONNET_4_6"]:
                    if hasattr(tee, attr):
                        return getattr(tee, attr)
            return DEFAULT_MODEL
        except Exception:
            return DEFAULT_MODEL

    def _extract_content(self, result) -> str:
        if result is None:
            return ""

        chat_output = getattr(result, "chat_output", None)
        if chat_output:
            if isinstance(chat_output, dict):
                return chat_output.get("content", "") or ""
            return str(chat_output)

        completion = getattr(result, "completion_output", None)
        if completion:
            return str(completion)

        if hasattr(result, "choices") and result.choices:
            try:
                return result.choices[0].message.content or ""
            except Exception:
                pass

        for attr in ("content", "output", "text"):
            val = getattr(result, attr, None)
            if val:
                return str(val)

        return str(result)

    def _unavailable_fallback(self, prompt: str) -> Dict[str, Any]:
        """
        Only used when OG SDK is completely unavailable (no private key).
        Returns a transparent message so the user knows what is happening.
        """
        return {
            "content": (
                "ProofGraph is running without a connected OpenGradient wallet. "
                "Add OG_PRIVATE_KEY to the backend environment to enable live "
                "TEE inference and get real verified answers for any question."
            ),
            "tx_hash":      None,
            "payment_hash": None,
            "model":        "unavailable",
            "mode":         "KNOWLEDGE",
            "verified":     False,
            "timestamp":    datetime.utcnow().isoformat(),
            "source":       "unavailable",
        }


_og_client: Optional[OGClient] = None


async def get_og_client() -> OGClient:
    global _og_client
    if _og_client is None:
        _og_client = OGClient()
        await _og_client.initialize()
    return _og_client
