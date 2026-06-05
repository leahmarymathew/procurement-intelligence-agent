from __future__ import annotations
from datetime import datetime
from typing import Optional

from .base import BaseAgent
from ..rag.retriever import retrieve_supplier_chunks
from ..schemas import AuditLogEntry, SupplierScoreOutput, DimensionScore
from ..database import AsyncSessionLocal
from ..models import SupplierScore

PROMPT_VERSION = "supplier-score-v1.0"

WEIGHTS = {
    "reliability": 0.25,
    "compliance": 0.25,
    "cost": 0.20,
    "risk": 0.20,
    "fit": 0.10,
}


class SupplierScoringAgent(BaseAgent):
    agent_name = "supplier-scoring"

    async def score(
        self,
        supplier_name: str,
        category: str,
        request_id: Optional[str] = None,
        pilot_team: Optional[str] = None,
    ) -> SupplierScoreOutput:
        self._reset_retrieval()

        # ── Step 1: Mandatory retrieval ──────────────────────────────────────
        query = f"{supplier_name} {category} performance compliance pricing risk"
        chunks = await retrieve_supplier_chunks(query, top_k=10)
        self._mark_retrieval_done()

        context_payload = {
            "supplier_name": supplier_name,
            "category": category,
            "chunk_ids": [c["chunk_id"] for c in chunks],
        }
        input_hash = self.payload_hash(context_payload)
        confidence = round(min(1.0, len(chunks) / 8.0), 3)

        # ── Step 2: LLM scoring ──────────────────────────────────────────────
        self._require_retrieval()
        prompt = self.get_versioned_prompt(PROMPT_VERSION)
        chunks_text = "\n\n".join(
            f"[{c['chunk_id']}] (source: {c['source']})\n{c['content']}"
            for c in chunks
        ) if chunks else "No knowledge-base chunks found. Score conservatively."

        user_message = (
            f"Supplier: {supplier_name}\nCategory: {category}\n\n"
            f"Knowledge Base Chunks:\n{chunks_text}"
        )

        try:
            raw = await self._llm_call(prompt, user_message)
        except Exception as exc:
            raw = _fallback_scores(str(exc), chunks)

        # ── Step 3: Compute composite ────────────────────────────────────────
        composite = round(
            sum(raw.get(dim, 5.0) * w for dim, w in WEIGHTS.items()), 2
        )
        if composite >= 7.5:
            status = "preferred"
        elif composite >= 6.0:
            status = "conditional"
        elif composite >= 4.0:
            status = "watch-list"
        else:
            status = "disqualified"

        output = SupplierScoreOutput(
            supplier=supplier_name,
            reliability=DimensionScore(
                score=raw.get("reliability", 5.0),
                source_chunk=raw.get("reliability_source", "insufficient-data"),
            ),
            compliance=DimensionScore(
                score=raw.get("compliance", 5.0),
                source_chunk=raw.get("compliance_source", "insufficient-data"),
            ),
            cost=DimensionScore(
                score=raw.get("cost", 5.0),
                source_chunk=raw.get("cost_source", "insufficient-data"),
            ),
            risk=DimensionScore(
                score=raw.get("risk", 5.0),
                source_chunk=raw.get("risk_source", "insufficient-data"),
            ),
            fit=DimensionScore(
                score=raw.get("fit", 5.0),
                source_chunk=raw.get("fit_source", "insufficient-data"),
            ),
            composite=composite,
            status=status,
            prompt_version=PROMPT_VERSION,
            confidence=confidence,
            input_hash=input_hash,
        )

        # ── Step 4: Persist to SQLite ────────────────────────────────────────
        import json
        async with AsyncSessionLocal() as db:
            record = SupplierScore(
                supplier_name=supplier_name,
                request_id=request_id,
                reliability_score=output.reliability.score,
                compliance_score=output.compliance.score,
                cost_score=output.cost.score,
                risk_score=output.risk.score,
                fit_score=output.fit.score,
                composite_score=composite,
                status=status,
                source_chunks=json.dumps({
                    "reliability": output.reliability.source_chunk,
                    "compliance": output.compliance.source_chunk,
                    "cost": output.cost.source_chunk,
                    "risk": output.risk.source_chunk,
                    "fit": output.fit.source_chunk,
                }),
                prompt_version=PROMPT_VERSION,
                confidence=confidence,
            )
            db.add(record)
            await db.commit()

        # ── Step 5: Audit log (before returning) ────────────────────────────
        await self.emit_audit_log(AuditLogEntry(
            timestamp=self._utcnow(),
            agent=self.agent_name,
            action="supplier_score",
            request_id=request_id,
            confidence=confidence,
            prompt_version=PROMPT_VERSION,
            pilot_team=pilot_team,
            slack_channel="#supplier-intel",
            status=status,
            context_payload_hash=input_hash,
        ))

        return output


def _fallback_scores(error_reason: str, chunks: list) -> dict:
    """When Groq is unavailable, return conservative middle scores with attribution."""
    print(f"[supplier-scoring] LLM unavailable ({error_reason}), using fallback scores")
    source = chunks[0]["chunk_id"] if chunks else "insufficient-data"
    return {
        "reliability": 5.0, "reliability_source": source,
        "compliance": 5.0, "compliance_source": source,
        "cost": 5.0, "cost_source": source,
        "risk": 5.0, "risk_source": source,
        "fit": 5.0, "fit_source": source,
        "rationale": f"Fallback scores applied — LLM unavailable: {error_reason}",
    }
