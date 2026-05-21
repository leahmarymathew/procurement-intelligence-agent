"""
BaseAgent enforces the two non-negotiable invariants from the spec:
  1. Retrieval (RAG or policy lookup) MUST precede every scoring / routing action.
  2. Every action is audit-logged via POST /audit-log before the result is returned.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from typing import Optional

import httpx

from ..config import settings
from ..prompts.library import get_prompt
from ..schemas import AuditLogEntry


AUDIT_URL = f"http://localhost:{settings.api_port}/audit-log"


class BaseAgent:
    agent_name: str = "base"
    _retrieval_done: bool = False

    def _require_retrieval(self):
        if not self._retrieval_done:
            raise RuntimeError(
                f"[{self.agent_name}] Retrieval step not completed. "
                "Call a retrieval method before invoking the LLM."
            )

    def _mark_retrieval_done(self):
        self._retrieval_done = True

    def _reset_retrieval(self):
        self._retrieval_done = False

    def get_versioned_prompt(self, name: str) -> str:
        return get_prompt(name)

    def payload_hash(self, payload: dict) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    async def emit_audit_log(self, entry: AuditLogEntry) -> None:
        payload = entry.model_dump()
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(AUDIT_URL, json=payload)
        except Exception:
            # Audit log failure must not block agent output — but must be surfaced
            print(f"[{self.agent_name}] WARN: audit log POST failed for action={entry.action}")

    def _utcnow(self) -> str:
        return datetime.utcnow().isoformat()

    async def _llm_call(self, system_prompt: str, user_message: str) -> dict:
        """Shared OpenAI JSON-mode call. Returns parsed dict."""
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content)
