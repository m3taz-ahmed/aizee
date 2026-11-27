#!/usr/bin/env python3
"""Versioned iterative response refinement with a regression guard.

Clean-room implementation of one narrow idea: a draft can be improved by
iterating — but only when each iteration is *measured* and regressions are
*rejected*. Everything here is deterministic and offline; the refinement
and scoring callables are dependency-injected, so tests never touch a
network and production decides what "better" means.

Design rules (aiZee governance-first):

- **Opt-in only.** Nothing refines unless a caller explicitly invokes
  ``refine()`` — there is no hidden mutation of model output anywhere
  in the pipeline.
- **Hard iteration cap.** ``max_iterations`` is the cost guard. Each
  iteration is potentially one more paid LLM call in production, so the
  cap is small by default and not adjustable per-candidate.
- **Regression guard.** A candidate scoring strictly worse than the
  incumbent is rejected — the incumbent survives. "Refinement" that
  makes things worse is not refinement.
- **Full version history.** Every candidate (accepted or not) is
  retained with its score for audit/revert; ``max_versions`` bounds
  memory on pathological loops.
- **Crash-safe.** A refiner exception stops the loop and returns the
  best version so far — refinement failure never loses the draft.

Usage::

    from runtime.response_refiner import refine, RefineConfig

    result = refine(
        draft,
        refine_fn=lambda text, i: llm_improve(text),
        config=RefineConfig(max_iterations=3),
    )
    final = result.final_text
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_logger = logging.getLogger(__name__)

# refine_fn contract: (current_best_text, iteration_number) -> candidate text.
RefineFn = Callable[[str, int], str]
# score_fn contract: text -> scalar score, higher is better.
ScoreFn = Callable[[str], float]


class StopReason(str, Enum):
    """Why the refinement loop ended."""

    MAX_ITERATIONS = "max_iterations"  # improved every round until the cap
    CONVERGED = "converged"  # improvement fell below min_improvement
    REGRESSED = "regressed"  # candidate scored worse — rejected
    REFINER_ERROR = "refiner_error"  # refiner raised — best-so-far kept


@dataclass(frozen=True)
class RefineConfig:
    """Tunables for one refinement loop.

    Memory is implicitly bounded: at most ``max_iterations + 1`` versions
    can ever exist, because every loop round produces exactly one.
    """

    max_iterations: int = 3  # hard cost cap — each round may be a paid call
    min_improvement: float = 0.02  # score gain needed to keep iterating


@dataclass
class Version:
    """One draft version: the initial text or one refinement candidate."""

    text: str
    score: float
    iteration: int  # 0 = initial draft
    accepted: bool  # True when this version became the new incumbent

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "score": round(self.score, 4),
            "accepted": self.accepted,
            "chars": len(self.text),
        }


@dataclass
class RefinementResult:
    """Loop outcome: winning text plus the full audit trail."""

    final_text: str
    final_score: float
    iterations_run: int
    stop_reason: StopReason
    versions: list[Version] = field(default_factory=list)

    @property
    def improved(self) -> bool:
        """True when refinement beat the initial draft's score."""
        return len(self.versions) > 1 and any(v.accepted for v in self.versions[1:])

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_score": round(self.final_score, 4),
            "iterations_run": self.iterations_run,
            "stop_reason": self.stop_reason.value,
            "improved": self.improved,
            "versions": [v.to_dict() for v in self.versions],
        }


# -- Default heuristic scorer ---------------------------------------------------
# A deliberately crude, deterministic stand-in for a real quality judge.
# Production callers should inject a domain score_fn (rubric LLM-judge,
# test-pass-rate, spec-compliance checker). This default only rewards
# structure and penalizes repetition/emptiness — enough for the loop
# mechanics to be exercised without any model in the loop.


def heuristic_score(text: str) -> float:
    """Score text 0..1 on structure, non-repetition, and vocabulary breadth.

    Crude by design: it exists so the loop has *a* monotone signal when no
    domain scorer is injected, not because it is a good proxy for quality.
    """
    if not text or not text.strip():
        return 0.0
    stripped = text.strip()

    # Length sanity: empty-ish is bad; very short caps low; long is fine.
    length_score = min(1.0, len(stripped) / 400.0) * 0.3

    # Structure: headings, bullets, multiple paragraphs.
    structure = 0.0
    if re.search(r"^#{1,4}\s|\*\*\w", stripped, re.MULTILINE):
        structure += 0.1
    if re.search(r"^\s*[-*•]\s", stripped, re.MULTILINE):
        structure += 0.1
    if "\n\n" in stripped:
        structure += 0.1
    structure = min(0.3, structure)

    # Repetition penalty: duplicate non-empty lines drag the score down.
    # Dampened by sample size — a one-line text is not "perfectly diverse",
    # it is just too small to judge. (stripped non-empty ⇒ lines non-empty.)
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    unique_ratio = len(set(lines)) / len(lines)
    line_confidence = min(1.0, len(lines) / 5.0)
    repetition_score = unique_ratio * line_confidence * 0.2

    # Vocabulary diversity over word tokens, dampened the same way.
    words = re.findall(r"\w+", stripped.lower())
    diversity = (len(set(words)) / len(words)) if words else 0.0
    word_confidence = min(1.0, len(words) / 20.0)
    diversity_score = min(1.0, diversity * 1.5) * word_confidence * 0.2

    return round(min(1.0, length_score + structure + repetition_score + diversity_score), 4)


# -- The refinement loop ----------------------------------------------------------


def refine(
    initial_text: str,
    refine_fn: RefineFn,
    *,
    score_fn: ScoreFn | None = None,
    config: RefineConfig | None = None,
) -> RefinementResult:
    """Hill-climb text quality: generate → measure → accept/reject → repeat.

    Args:
        initial_text: The draft to improve (iteration 0).
        refine_fn: Produces the next candidate from the incumbent text.
        score_fn: Quality measurement; defaults to :func:`heuristic_score`.
        config: Caps and convergence thresholds.

    Returns:
        A :class:`RefinementResult` with the best text and full history.
    """
    cfg = config or RefineConfig()
    score = score_fn or heuristic_score
    max_iterations = max(0, cfg.max_iterations)

    best_text = initial_text
    best_score = score(initial_text)
    versions: list[Version] = [
        Version(text=initial_text, score=best_score, iteration=0, accepted=True)
    ]
    iterations_run = 0
    stop_reason = StopReason.MAX_ITERATIONS

    for iteration in range(1, max_iterations + 1):
        iterations_run = iteration
        try:
            candidate = refine_fn(best_text, iteration)
        except Exception as exc:
            _logger.warning("refine_fn raised at iteration %d (keeping best): %s", iteration, exc)
            stop_reason = StopReason.REFINER_ERROR
            iterations_run = iteration - 1
            break

        candidate_score = score(candidate)
        gain = candidate_score - best_score

        if gain >= cfg.min_improvement:
            best_text, best_score = candidate, candidate_score
            versions.append(Version(candidate, candidate_score, iteration, True))
            continue

        if gain > 0:
            # Real but tiny improvement: accept it and stop — iterating
            # further spends budget for noise-level gains.
            best_text, best_score = candidate, candidate_score
            versions.append(Version(candidate, candidate_score, iteration, True))
            stop_reason = StopReason.CONVERGED
        else:
            # Flat or worse: reject the candidate, keep the incumbent.
            versions.append(Version(candidate, candidate_score, iteration, False))
            stop_reason = StopReason.REGRESSED
        break

    return RefinementResult(
        final_text=best_text,
        final_score=best_score,
        iterations_run=iterations_run,
        stop_reason=stop_reason,
        versions=versions,
    )
