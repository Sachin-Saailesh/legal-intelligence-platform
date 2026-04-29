import json
import time
from dataclasses import dataclass

from core.logging import get_logger
from rag.embeddings import AzureLLMClient
from rag.reranker import RankedChunk

logger = get_logger(__name__)

_GUARD_SYSTEM = """You are a legal citation verifier. Your task is to assess whether a given claim is
supported by the provided source chunks.

Respond ONLY with valid JSON in this exact format:
{
  "confidence": 0.85,
  "citation_indices": [0, 2],
  "reasoning": "The claim is directly supported by chunk 0 which states ... and chunk 2 which states ..."
}

Rules:
- confidence is a float from 0.0 to 1.0 representing how well the claim is grounded in the sources
- citation_indices is a list of chunk indices (0-based) that support the claim
- A confidence < 0.70 means the claim cannot be verified from the provided sources
- Be strict: only cite chunks that directly support the specific claim
- If the claim contains numbers, dates, or specific legal terms, verify them exactly against the sources
"""


@dataclass
class GuardResult:
    passed: bool
    confidence: float
    citation_indices: list[int]
    reasoning: str
    escalation_reason: str | None = None


class HallucinationGuard:
    def __init__(self, llm_client: AzureLLMClient, confidence_threshold: float = 0.70) -> None:
        self._llm = llm_client
        self._threshold = confidence_threshold

    async def validate(
        self, claim: str, source_chunks: list[RankedChunk]
    ) -> GuardResult:
        t0 = time.perf_counter()

        if not source_chunks:
            result = GuardResult(
                passed=False,
                confidence=0.0,
                citation_indices=[],
                reasoning="No source chunks provided.",
                escalation_reason="No supporting sources available for this claim.",
            )
            self._log(claim, result, time.perf_counter() - t0)
            return result

        # Build chunk context (limit to first 15 chunks to fit context window)
        context_parts = []
        for i, chunk in enumerate(source_chunks[:15]):
            context_parts.append(
                f"[Chunk {i}] (source: {chunk.doc_id}, page: {chunk.page_number}, "
                f"score: {chunk.rerank_score:.3f})\n{chunk.text[:800]}"
            )
        context = "\n\n---\n\n".join(context_parts)

        user_message = f"CLAIM TO VERIFY:\n{claim}\n\nSOURCE CHUNKS:\n{context}"

        try:
            raw = await self._llm.complete(
                system=_GUARD_SYSTEM,
                messages=[{"role": "user", "content": user_message}],
                temperature=0,
                max_tokens=600,
                trace_name="hallucination_guard",
            )
            data = json.loads(raw.strip())
            confidence = float(data.get("confidence", 0.0))
            citation_indices = [int(i) for i in data.get("citation_indices", [])]
            reasoning = data.get("reasoning", "")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("guard_parse_error", error=str(e), raw=raw[:200])
            confidence = 0.0
            citation_indices = []
            reasoning = "Failed to parse guard response."

        passed = confidence >= self._threshold
        escalation_reason = (
            None
            if passed
            else (
                f"Confidence {confidence*100:.0f}% is below threshold {self._threshold*100:.0f}%. "
                f"Reasoning: {reasoning}"
            )
        )

        result = GuardResult(
            passed=passed,
            confidence=confidence,
            citation_indices=citation_indices,
            reasoning=reasoning,
            escalation_reason=escalation_reason,
        )
        self._log(claim, result, time.perf_counter() - t0)
        return result

    def _log(self, claim: str, result: GuardResult, elapsed: float) -> None:
        logger.info(
            "hallucination_guard",
            claim_preview=claim[:100],
            passed=result.passed,
            confidence=round(result.confidence, 4),
            citation_count=len(result.citation_indices),
            elapsed_ms=round(elapsed * 1000, 2),
        )
