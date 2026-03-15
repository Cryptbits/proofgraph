# og_client.py
# OpenGradient SDK wrapper — og.LLM API (2026)
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

# Model strings exactly as listed in OG docs supported models
OG_MODELS = [
    "openai/gpt-4.1-2025-04-14",
    "openai/gpt-5-mini",
    "openai/gpt-5",
    "anthropic/claude-sonnet-4-6",
]


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
            print("No OG_PRIVATE_KEY — Knowledge Mode")
            return

        try:
            import opengradient as og
            self._og  = og

            print(f"opengradient version: {getattr(og, '__version__', 'unknown')}")
            print(f"og.LLM available: {hasattr(og, 'LLM')}")
            print(f"og.TEE_LLM available: {hasattr(og, 'TEE_LLM')}")

            self._llm = og.LLM(private_key=self.private_key)
            print("og.LLM initialized")

            # Permit2 approval — needed before inference calls
            try:
                approval = self._llm.ensure_opg_approval(opg_amount=10.0)
                print(f"Permit2 approval: allowance={getattr(approval, 'allowance_after', 'ok')}")
            except Exception as e:
                print(f"Permit2 note (non-fatal): {e}")

            self._initialized = True
            self.mode         = "OG_LIVE"
            self.wallet       = self.private_key[:8] + "..." + self.private_key[-4:]
            print(f"OG LIVE — wallet: {self.wallet}, model: {OG_MODELS[0]}")

        except ImportError:
            print("ERROR: opengradient not installed — pip install opengradient")
        except Exception as e:
            print(f"OG SDK init FAILED: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

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
            # Try each model in order until one works
            for model_str in OG_MODELS:
                try:
                    result = await asyncio.wait_for(
                        self._call_llm(prompt, system_prompt, max_tokens, model_str),
                        timeout=90.0
                    )
                    if result and result.get("content"):
                        return result
                except asyncio.TimeoutError:
                    print(f"Timeout on {model_str} — trying next")
                    continue
                except Exception as e:
                    print(f"ERROR on {model_str}: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            print("All OG models failed — using fallback")

        return self._unavailable_fallback(prompt)

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        model_str: str,
    ) -> Dict[str, Any]:
        og = self._og

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ]

        # Resolve model — try TEE_LLM enum first, fall back to string
        model = self._resolve_model(model_str)
        print(f"Calling og.LLM.chat — model={model}, max_tokens={max_tokens}")

        result = await self._llm.chat(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,  # low temperature = consistent, deterministic answers
        )

        content      = self._extract_content(result)
        payment_hash = getattr(result, "payment_hash", None)
        tx_hash      = str(payment_hash) if payment_hash else None

        if not content:
            raise ValueError(f"Empty response from OG — result type: {type(result)}, value: {str(result)[:200]}")

        print(f"OG inference OK — chars: {len(content)}, payment: {tx_hash}")

        return {
            "content":      content,
            "tx_hash":      tx_hash,
            "payment_hash": tx_hash,
            "model":        model_str,
            "mode":         "TEE",
            "verified":     True,
            "timestamp":    datetime.utcnow().isoformat(),
            "source":       "opengradient_live",
        }

    def _resolve_model(self, model_str: str):
        """
        Return og.TEE_LLM enum if available, otherwise return the string.
        The SDK accepts both in current versions.
        """
        og = self._og
        if not hasattr(og, "TEE_LLM"):
            return model_str

        tee = og.TEE_LLM
        # Map model strings to enum attribute names
        mapping = {
            "openai/gpt-4.1-2025-04-14":    "GPT_4_1_2025_04_14",
            "openai/gpt-5-mini":             "GPT_5_MINI",
            "openai/gpt-5":                  "GPT_5",
            "anthropic/claude-sonnet-4-6":   "CLAUDE_SONNET_4_6",
        }
        attr = mapping.get(model_str)
        if attr and hasattr(tee, attr):
            return getattr(tee, attr)

        # Fall back to string — newer SDK versions accept strings directly
        return model_str

    def _extract_content(self, result) -> str:
        if result is None:
            return ""

        # Current API: result.chat_output is a dict with 'content' key
        chat_output = getattr(result, "chat_output", None)
        if chat_output:
            if isinstance(chat_output, dict):
                return chat_output.get("content", "") or ""
            if isinstance(chat_output, str):
                return chat_output

        # Completion API
        completion = getattr(result, "completion_output", None)
        if completion:
            return str(completion)

        # OpenAI-style choices
        if hasattr(result, "choices") and result.choices:
            try:
                return result.choices[0].message.content or ""
            except Exception:
                pass

        # Direct attributes
        for attr in ("content", "output", "text", "message"):
            val = getattr(result, attr, None)
            if val and isinstance(val, str):
                return val

        return ""

    def _unavailable_fallback(self, prompt: str) -> Dict[str, Any]:
        from og_knowledge import get_focused_answer

        # Extract question from prompt if it has a Question: line
        question = prompt
        for line in prompt.split("\n"):
            if line.strip().startswith("Question:"):
                question = line.strip().replace("Question:", "").strip()
                break

        # Try KB for OG-specific topics
        kb_answer = get_focused_answer(question)

        content = kb_answer if kb_answer else (
            "ProofGraph could not reach the OpenGradient network for this query. "
            "Please check that your backend has a valid OG_PRIVATE_KEY and sufficient $OPG balance."
        )

        return {
            "content":      content,
            "tx_hash":      None,
            "payment_hash": None,
            "model":        "fallback",
            "mode":         "KNOWLEDGE",
            "verified":     False,
            "timestamp":    datetime.utcnow().isoformat(),
            "source":       "fallback",
        }


_og_client: Optional[OGClient] = None


async def get_og_client() -> OGClient:
    global _og_client
    if _og_client is None:
        _og_client = OGClient()
        await _og_client.initialize()
    return _og_client
