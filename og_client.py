# ================================================================
# og_client.py - OpenGradient SDK Wrapper
# Handles TEE LLM inference + x402 payments
# ================================================================

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()


class OGClient:
    """
    Async-friendly wrapper around the OpenGradient Python SDK.
    The OG SDK is synchronous, so we run it in a thread executor.
    """

    def __init__(self):
        self.private_key  = os.getenv("OG_PRIVATE_KEY")
        self.email        = os.getenv("OG_EMAIL")
        self.password     = os.getenv("OG_PASSWORD")
        self._client      = None
        self._executor    = ThreadPoolExecutor(max_workers=4)
        self._initialized = False

    def _init_client(self):
        """Initialize the OG SDK client (runs in thread)."""
        try:
            import opengradient as og

            self._client = og.new_client(
                private_key=self.private_key,
                email=self.email if self.email else None,
                password=self.password if self.password else None,
            )
            self._og = og
            self._initialized = True
            print("✅ OpenGradient client initialized")
        except Exception as e:
            print(f"⚠️  OpenGradient client init failed: {e}")
            print("   Running in DEMO mode (simulated proofs)")
            self._initialized = False

    async def initialize(self):
        """Async initialization."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._init_client)

    def _run_tee_inference(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 800,
        model: str = "openai/gpt-4.1",
    ) -> Dict[str, Any]:
        """
        Synchronous TEE inference call.
        Returns dict with: content, payment_hash, tx_hash, model, mode
        """
        if not self._initialized:
            return self._demo_inference(prompt, model)

        try:
            import opengradient as og

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ]

            result = self._client.llm_chat(
                model_cid=model,
                messages=messages,
                inference_mode=og.LlmInferenceMode.TEE,
                settlement_mode=og.x402SettlementMode.SETTLE_METADATA,
                max_tokens=max_tokens,
                temperature=0.3,
            )

            # Handle both object-style and tuple-style returns
            if hasattr(result, "completion_output"):
                content      = result.completion_output
                payment_hash = getattr(result, "payment_hash", None)
                tx_hash      = getattr(result, "tx_hash", None)
            elif isinstance(result, (tuple, list)):
                content      = result[-1] if len(result) >= 1 else ""
                payment_hash = result[0] if len(result) >= 3 else None
                tx_hash      = result[0] if len(result) >= 1 else None
                # Handle dict message object
                if isinstance(content, dict):
                    content = content.get("content", str(content))
            else:
                content      = str(result)
                payment_hash = None
                tx_hash      = None

            return {
                "content":      content,
                "payment_hash": payment_hash,
                "tx_hash":      tx_hash,
                "model":        model,
                "mode":         "TEE",
                "verified":     True,
                "timestamp":    datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"⚠️  TEE inference failed: {e}. Falling back to VANILLA.")
            return self._run_vanilla_inference(prompt, system_prompt, max_tokens, model)

    def _run_vanilla_inference(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 800,
        model: str = "openai/gpt-4.1",
    ) -> Dict[str, Any]:
        """Fallback vanilla inference."""
        if not self._initialized:
            return self._demo_inference(prompt, model)

        try:
            import opengradient as og

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ]

            result = self._client.llm_chat(
                model_cid=model,
                messages=messages,
                inference_mode=og.LlmInferenceMode.VANILLA,
                max_tokens=max_tokens,
                temperature=0.3,
            )

            if hasattr(result, "completion_output"):
                content = result.completion_output
                payment_hash = getattr(result, "payment_hash", None)
            elif isinstance(result, (tuple, list)):
                content = result[-1] if result else ""
                payment_hash = result[0] if len(result) >= 3 else None
                if isinstance(content, dict):
                    content = content.get("content", str(content))
            else:
                content = str(result)
                payment_hash = None

            return {
                "content":      content,
                "payment_hash": payment_hash,
                "tx_hash":      None,
                "model":        model,
                "mode":         "VANILLA",
                "verified":     False,
                "timestamp":    datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"⚠️  Vanilla inference also failed: {e}")
            return self._demo_inference(prompt, model)

    def _demo_inference(self, prompt: str, model: str) -> Dict[str, Any]:
        """
        Demo mode when OG SDK isn't configured.
        Returns realistic simulated output so the UI still works.
        """
        import hashlib, time
        fake_hash = "0x" + hashlib.sha256(
            (prompt + str(time.time())).encode()
        ).hexdigest()[:40]

        return {
            "content":      f"[DEMO MODE] This is a simulated response for: {prompt[:80]}...\n\nIn production, this runs inside an OpenGradient TEE with cryptographic attestation.",
            "payment_hash": fake_hash,
            "tx_hash":      "0x" + fake_hash[2:].replace("a", "b"),
            "model":        model,
            "mode":         "DEMO",
            "verified":     False,
            "timestamp":    datetime.utcnow().isoformat(),
        }

    async def infer_tee(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 800,
        model: str = "openai/gpt-4.1",
    ) -> Dict[str, Any]:
        """Async wrapper for TEE inference."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self._run_tee_inference(prompt, system_prompt, max_tokens, model),
        )


# Singleton
_og_client: Optional[OGClient] = None


async def get_og_client() -> OGClient:
    global _og_client
    if _og_client is None:
        _og_client = OGClient()
        await _og_client.initialize()
    return _og_client
