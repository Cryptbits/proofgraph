# og_client.py
# OpenGradient SDK wrapper.
# Current API: og.LLM(private_key=...) / await llm.chat(model, messages)
# Docs: docs.opengradient.ai/developers/sdk/llm.html

import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

_PLACEHOLDER_KEYS = {
    "", "0x", "0xyour_private_key_here", "0x...",
    "your_private_key", "add_your_key_here",
}


class OGClient:

    def __init__(self):
        self.private_key  = os.getenv("OG_PRIVATE_KEY", "").strip()
        self._llm         = None
        self._og          = None
        self._initialized = False
        self.mode         = "KNOWLEDGE"
        self.wallet       = None
        self._working_model = None  # set on first successful call

    def _init_sdk(self):
        if self.private_key.lower() in _PLACEHOLDER_KEYS:
            print("No OG_PRIVATE_KEY set — Knowledge Mode")
            return

        try:
            import opengradient as og
            self._og  = og
            self._llm = og.LLM(private_key=self.private_key)

            # Ensure Permit2 so x402 payments work
            try:
                self._llm.ensure_opg_approval(opg_amount=10.0)
                print("Permit2 approval OK")
            except Exception as e:
                print(f"Permit2 note (non-fatal): {e}")

            # Discover which models are actually available on this SDK version
            self._working_model = self._discover_model()
            if not self._working_model:
                print("WARNING: Could not resolve any model enum — will try string names")

            self._initialized = True
            self.mode         = "OG_LIVE"
            self.wallet       = self.private_key[:8] + "..." + self.private_key[-4:]
            print(f"OG LIVE — wallet: {self.wallet}")
            print(f"Model: {self._working_model}")

        except ImportError:
            print("ERROR: opengradient not installed — run: pip install opengradient")
        except Exception as e:
            print(f"OG SDK init failed: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()

    def _discover_model(self):
        """
        Find a working model enum from the installed SDK.
        Prints all available TEE_LLM attributes so we can see what exists.
        """
        og = self._og
        if not hasattr(og, "TEE_LLM"):
            print("WARNING: og.TEE_LLM not found — SDK may have changed")
            return None

        available = [a for a in dir(og.TEE_LLM) if not a.startswith("_")]
        print(f"Available TEE_LLM models: {available}")

        # Preference order — use first one that exists
        preferred = [
            "GPT_4_1_2025_04_14",
            "GPT_5",
            "GPT_5_MINI",
            "CLAUDE_SONNET_4_6",
            "CLAUDE_SONNET_4_5",
            "GEMINI_2_5_FLASH",
        ]
        for name in preferred:
            if name in available:
                model = getattr(og.TEE_LLM, name)
                print(f"Selected model: og.TEE_LLM.{name} = {model}")
                return model

        # Fall back to first available
        if available:
            model = getattr(og.TEE_LLM, available[0])
            print(f"Using first available model: og.TEE_LLM.{available[0]} = {model}")
            return model

        return None

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

        if not (self._initialized and self._llm):
            return self._knowledge_fallback(prompt)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ]

        # Try the discovered model first, then fall back to string names
        models_to_try = []
        if self._working_model is not None:
            models_to_try.append(("enum", self._working_model))

        # Also try raw strings in case the SDK accepts them
        for s in ["openai/gpt-4.1-2025-04-14", "openai/gpt-5-mini", "openai/gpt-5"]:
            models_to_try.append(("string", s))

        last_error = None
        for kind, model in models_to_try:
            try:
                print(f"Trying model ({kind}): {model}")
                result = await asyncio.wait_for(
                    self._llm.chat(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.1,
                    ),
                    timeout=90.0
                )

                content      = self._extract_content(result)
                payment_hash = getattr(result, "payment_hash", None)
                tx_hash      = str(payment_hash) if payment_hash else None

                if not content:
                    raise ValueError(f"Empty response — result: {str(result)[:100]}")

                print(f"OG inference OK — {len(content)} chars, payment: {tx_hash}")
                # Cache the working model so future calls skip the loop
                if kind == "enum":
                    self._working_model = model
                return {
                    "content":      content,
                    "tx_hash":      tx_hash,
                    "payment_hash": tx_hash,
                    "model":        str(model),
                    "mode":         "TEE",
                    "verified":     True,
                    "timestamp":    datetime.utcnow().isoformat(),
                    "source":       "opengradient_live",
                }

            except asyncio.TimeoutError:
                print(f"Timeout on {model}")
                last_error = "timeout"
                continue
            except Exception as e:
                print(f"ERROR on {model}: {type(e).__name__}: {e}")
                import traceback; traceback.print_exc()
                last_error = str(e)
                continue

        print(f"All models failed. Last error: {last_error}")
        return self._knowledge_fallback(prompt)

    def _extract_content(self, result) -> str:
        if result is None:
            return ""

        # New API: result.chat_output dict
        chat_output = getattr(result, "chat_output", None)
        if chat_output:
            if isinstance(chat_output, dict):
                return chat_output.get("content", "") or ""
            return str(chat_output)

        # Completion output
        co = getattr(result, "completion_output", None)
        if co:
            return str(co)

        # OpenAI-style choices
        if hasattr(result, "choices") and result.choices:
            try:
                return result.choices[0].message.content or ""
            except Exception:
                pass

        for attr in ("content", "output", "text"):
            val = getattr(result, attr, None)
            if val:
                return str(val)

        return ""

    def _knowledge_fallback(self, prompt: str) -> Dict[str, Any]:
        """
        Fallback when OG SDK is unavailable.
        For OG-specific topics uses the knowledge base.
        For everything else returns an honest empty response.
        """
        from og_knowledge import get_focused_answer

        # Extract the actual question from node prompt format
        question = prompt
        for line in prompt.split("\n"):
            if line.strip().startswith("Question:"):
                question = line.strip().replace("Question:", "").strip()
                break

        answer = get_focused_answer(question)

        if not answer:
            # Return empty so the frontend shows nothing rather than wrong text
            answer = ""

        return {
            "content":      answer,
            "tx_hash":      None,
            "payment_hash": None,
            "model":        "knowledge-base",
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
