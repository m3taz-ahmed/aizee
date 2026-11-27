#!/usr/bin/env python3
"""Adaptive sampling-parameter selection (deterministic, offline).

Clean-room reimplementation of a simple idea: not every prompt wants the
same ``temperature``. A code diff wants determinism; a brainstorm wants
spread. This module classifies request context with transparent heuristics
and proposes bounded sampling parameters — never calling the network,
never mutating the user's prompt, and always yielding precedence to
explicit user overrides.

Design rules (aiZee governance-first):

- **User overrides win.** Any parameter the caller pins is never blended,
  clamped away, or learned over — it is echoed back verbatim.
- **Confidence-gated blending.** Below ``BLEND_THRESHOLD`` confidence the
  class profile is blended toward the BALANCED profile, so a shaky
  classification produces mild parameters rather than extreme ones.
- **Bounded everything.** Outputs are clamped to provider-safe ranges
  (OpenAI-compatible: temperature 0..2, top_p (0,1], penalties -2..2).
- **Full transparency.** Every decision carries ``param_deltas``,
  ``pattern_matches`` and ``confidence`` so the audit log can answer
  "why these parameters?" without guesswork.
- **Feedback is a bias, not a rewrite.** The EMA feedback loop nudges a
  class profile's temperature toward BALANCED when users keep rejecting
  its outputs — capped at ``MAX_LEARNED_PULL`` of the gap.

Usage::

    from runtime.sampling_advisor import SamplingAdvisor

    advisor = SamplingAdvisor()
    decision = advisor.advise("write a python function that parses yaml")
    params = decision.to_openai_params()
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

_logger = logging.getLogger(__name__)


class TaskClass(str, Enum):
    """Request-context classes the advisor can distinguish."""

    CODE = "code"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    CONVERSATIONAL = "conversational"
    FACTUAL = "factual"
    BALANCED = "balanced"  # fallback / blending anchor — never classified into


# -- Bounded parameter ranges (OpenAI-compatible semantics) -----------------
TEMP_MIN, TEMP_MAX = 0.0, 2.0
TOP_P_MIN, TOP_P_MAX = 0.0, 1.0
TOP_K_MIN, TOP_K_MAX = 1, 512
PENALTY_MIN, PENALTY_MAX = -2.0, 2.0


@dataclass(frozen=True)
class SamplingProfile:
    """One immutable sampling profile."""

    temperature: float
    top_p: float = 1.0
    top_k: int = 0  # 0 = unset (provider default)
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    def clamped(self) -> SamplingProfile:
        """Return a copy clamped to provider-safe ranges."""
        return SamplingProfile(
            temperature=min(TEMP_MAX, max(TEMP_MIN, self.temperature)),
            top_p=min(TOP_P_MAX, max(TOP_P_MIN, self.top_p)),
            top_k=min(TOP_K_MAX, max(TOP_K_MIN, self.top_k)) if self.top_k else 0,
            frequency_penalty=min(PENALTY_MAX, max(PENALTY_MIN, self.frequency_penalty)),
            presence_penalty=min(PENALTY_MAX, max(PENALTY_MIN, self.presence_penalty)),
        )

    def blend(self, other: SamplingProfile, weight: float) -> SamplingProfile:
        """Linear blend toward ``other``; ``weight`` is other's share (0..1)."""
        w = min(1.0, max(0.0, weight))
        mine = 1.0 - w

        def _mix(a: float, b: float) -> float:
            return a * mine + b * w

        top_k = 0
        if self.top_k and other.top_k:
            top_k = round(_mix(self.top_k, other.top_k))
        elif self.top_k or other.top_k:
            top_k = round((self.top_k or other.top_k) * mine) or (self.top_k or other.top_k)
        return SamplingProfile(
            temperature=_mix(self.temperature, other.temperature),
            top_p=_mix(self.top_p, other.top_p),
            top_k=top_k,
            frequency_penalty=_mix(self.frequency_penalty, other.frequency_penalty),
            presence_penalty=_mix(self.presence_penalty, other.presence_penalty),
        ).clamped()

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": round(self.temperature, 4),
            "top_p": round(self.top_p, 4),
            "top_k": self.top_k,
            "frequency_penalty": round(self.frequency_penalty, 4),
            "presence_penalty": round(self.presence_penalty, 4),
        }


# -- Base profiles ------------------------------------------------------------
# Determinism-leaning for precise work, spread-leaning for generative work.
# All values stay well inside provider-safe bounds even before clamping.
BASE_PROFILES: dict[TaskClass, SamplingProfile] = {
    TaskClass.CODE: SamplingProfile(temperature=0.2, top_p=0.9, top_k=40),
    TaskClass.ANALYTICAL: SamplingProfile(temperature=0.4, top_p=0.95),
    TaskClass.FACTUAL: SamplingProfile(temperature=0.1, top_p=0.85, top_k=30),
    TaskClass.CONVERSATIONAL: SamplingProfile(temperature=0.7, top_p=0.95),
    TaskClass.CREATIVE: SamplingProfile(
        temperature=0.9, top_p=0.98, frequency_penalty=0.3, presence_penalty=0.2
    ),
    TaskClass.BALANCED: SamplingProfile(temperature=0.5, top_p=0.95),
}


@dataclass(frozen=True)
class SamplingDecision:
    """Advisory output: final parameters plus full transparency metadata."""

    params: SamplingProfile
    task_class: TaskClass
    confidence: float
    pattern_matches: dict[str, int]
    param_deltas: dict[str, float]
    overridden_keys: tuple[str, ...] = ()
    learned_pull: float = 0.0
    blended_to_balanced: bool = False

    def to_openai_params(self) -> dict[str, Any]:
        """Export as an OpenAI-compatible request fragment (unset keys omitted)."""
        out: dict[str, Any] = {
            "temperature": round(self.params.temperature, 4),
            "top_p": round(self.params.top_p, 4),
        }
        if self.params.top_k:
            out["top_k"] = self.params.top_k
        if self.params.frequency_penalty:
            out["frequency_penalty"] = round(self.params.frequency_penalty, 4)
        if self.params.presence_penalty:
            out["presence_penalty"] = round(self.params.presence_penalty, 4)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_class": self.task_class.value,
            "confidence": round(self.confidence, 3),
            "params": self.params.to_dict(),
            "param_deltas": self.param_deltas,
            "pattern_matches": self.pattern_matches,
            "overridden_keys": list(self.overridden_keys),
            "learned_pull": round(self.learned_pull, 3),
            "blended_to_balanced": self.blended_to_balanced,
        }


# -- Classification patterns ----------------------------------------------------
# Weighted keyword/regex hits per class. Order of evaluation decides ties;
# CODE first because code-ish prompts are the most cost-sensitive to
# temperature mistakes.
_CLASS_PATTERNS: dict[TaskClass, tuple[tuple[str, int], ...]] = {
    TaskClass.CODE: (
        (r"\b(function|def|class|import|compile|debug|refactor|regex|sql|api endpoint)\b", 2),
        (r"\b(python|typescript|javascript|rust|golang|c\+\+|yaml|json|dockerfile)\b", 2),
        (r"```", 3),
        (r"\b(write|fix|implement|optimize)\s+(a\s+|the\s+)?(code|script|function|program)\b", 3),
    ),
    TaskClass.ANALYTICAL: (
        (r"\b(analy[sz]e|compare|evaluate|trade-?off|pros and cons|assess|critique)\b", 2),
        (r"\b(architecture|design decision|root cause|why did|explain the reasoning)\b", 2),
        (r"\b(step[- ]by[- ]step|systematically|in depth)\b", 1),
    ),
    TaskClass.FACTUAL: (
        (r"\b(what is|who is|when did|where is|define|list the|name the)\b", 2),
        (r"\b(exact|precise|correct answer|fact|verifiable|cite|source)\b", 2),
    ),
    TaskClass.CREATIVE: (
        (r"\b(story|poem|haiku|fiction|brainstorm|imagine|invent|creative)\b", 3),
        (r"\b(marketing copy|slogan|tagline|narrative|screenplay|lyrics)\b", 2),
        (r"\b(come up with|ideas for|variations of)\b", 1),
    ),
    TaskClass.CONVERSATIONAL: (
        (r"\b(hi|hello|hey|thanks|thank you|how are you)\b", 1),
        (r"\b(chat|talk|discuss|opinion|what do you think)\b", 1),
    ),
}


@dataclass
class _ClassFeedback:
    """EMA feedback state for one task class."""

    alpha: float
    ema: float = 0.5  # neutral start: neither loved nor rejected
    samples: int = 0


class SamplingAdvisor:
    """Classify → propose bounded sampling params → learn from feedback.

    All methods are deterministic given the same feedback history; nothing
    here touches the network, the filesystem, or the clock.
    """

    BLEND_THRESHOLD: ClassVar[float] = 0.6  # below this, blend toward BALANCED
    EMA_ALPHA: ClassVar[float] = 0.3
    MIN_FEEDBACK_SAMPLES: ClassVar[int] = 3  # feedback ignored before this
    MAX_LEARNED_PULL: ClassVar[float] = 0.5  # at most half-way toward BALANCED
    FULL_PULL_SAMPLES: ClassVar[int] = 20  # samples at which pull is fully trusted

    def __init__(self) -> None:
        self._feedback: dict[TaskClass, _ClassFeedback] = {
            tc: _ClassFeedback(alpha=self.EMA_ALPHA)
            for tc in BASE_PROFILES
            if tc is not TaskClass.BALANCED
        }

    # -- classification -----------------------------------------------------
    def classify(self, text: str) -> tuple[TaskClass, float, dict[str, int]]:
        """Score each class against ``text``; return (winner, confidence, hits).

        Confidence is the winner's share of total hits, softened toward 0.5
        when few patterns fire at all (weak evidence ≠ strong opinion).
        """
        hits: dict[str, int] = {}
        scores: dict[TaskClass, int] = {}
        lowered = text.lower()
        for tc, patterns in _CLASS_PATTERNS.items():
            total = 0
            count = 0
            for pattern, weight in patterns:
                n = len(re.findall(pattern, lowered))
                if n:
                    count += n
                    total += n * weight
            if count:
                hits[tc.value] = count
                scores[tc] = total
        if not scores:
            return TaskClass.BALANCED, 0.0, hits
        winner = max(scores, key=lambda tc: (scores[tc], -list(_CLASS_PATTERNS).index(tc)))
        total_score = sum(scores.values())
        share = scores[winner] / total_score if total_score else 0.0
        # Evidence-strength softening: 1 hit is noise, 4+ hits is signal.
        evidence = min(1.0, sum(hits.values()) / 4.0)
        confidence = share * (0.5 + 0.5 * evidence)
        return winner, confidence, hits

    # -- advice ---------------------------------------------------------------
    def advise(
        self,
        text: str,
        *,
        overrides: dict[str, Any] | None = None,
        history_len: int = 0,
    ) -> SamplingDecision:
        """Produce a bounded sampling decision for one request.

        Args:
            text: The user prompt (classification input — never modified).
            overrides: Caller-pinned parameters; these win unconditionally.
            history_len: Length of the conversation so far — long sessions
                get a small presence-penalty nudge against repetition loops.
        """
        overrides = overrides or {}
        task_class, confidence, hits = self.classify(text)

        base = BASE_PROFILES.get(task_class, BASE_PROFILES[TaskClass.BALANCED])
        profile = base
        blended = False
        if confidence < self.BLEND_THRESHOLD and task_class is not TaskClass.BALANCED:
            profile = base.blend(BASE_PROFILES[TaskClass.BALANCED], 1.0 - confidence)
            blended = True

        # Learned feedback pull: classes with a poor EMA drift toward
        # BALANCED temperature, capped at MAX_LEARNED_PULL of the gap.
        pull = self._learned_pull(task_class)

        profile = self._apply_feedback_pull(profile, task_class, pull)

        # Long conversations: mild repetition guard (bounded, monotonic).
        if history_len >= 20:
            bump = min(0.3, 0.02 * (history_len - 18))
            profile = SamplingProfile(
                temperature=profile.temperature,
                top_p=profile.top_p,
                top_k=profile.top_k,
                frequency_penalty=profile.frequency_penalty,
                presence_penalty=profile.presence_penalty + bump,
            )

        profile = profile.clamped()
        final, overridden_keys = self._apply_overrides(profile, overrides)
        deltas = self._deltas(BASE_PROFILES[TaskClass.BALANCED], final)
        return SamplingDecision(
            params=final,
            task_class=task_class,
            confidence=confidence,
            pattern_matches=hits,
            param_deltas=deltas,
            overridden_keys=tuple(overridden_keys),
            learned_pull=pull,
            blended_to_balanced=blended,
        )

    # -- feedback loop --------------------------------------------------------
    def record_feedback(self, task_class: TaskClass, positive: bool) -> None:
        """Update the EMA for one class (thumbs up/down translated to 1/0)."""
        if task_class not in self._feedback:
            return
        fb = self._feedback[task_class]
        fb.ema = fb.ema + fb.alpha * ((1.0 if positive else 0.0) - fb.ema)
        fb.samples += 1

    def feedback_state(self) -> dict[str, dict[str, float]]:
        """Snapshot of the learning state — serializable for persistence."""
        return {
            tc.value: {"ema": round(fb.ema, 4), "samples": fb.samples}
            for tc, fb in self._feedback.items()
        }

    def load_feedback_state(self, state: dict[str, dict[str, float]]) -> None:
        """Restore a previously persisted feedback snapshot (lenient)."""
        for name, data in state.items():
            try:
                tc = TaskClass(name)
            except ValueError:
                continue
            if tc in self._feedback:
                self._feedback[tc].ema = min(1.0, max(0.0, float(data.get("ema", 0.5))))
                self._feedback[tc].samples = max(0, int(data.get("samples", 0)))

    # -- internals --------------------------------------------------------------
    def _learned_pull(self, task_class: TaskClass) -> float:
        """How strongly feedback pulls this class toward BALANCED (0..MAX)."""
        fb = self._feedback.get(task_class)
        if fb is None or fb.samples < self.MIN_FEEDBACK_SAMPLES:
            return 0.0
        # Low EMA (users keep rejecting) → strong pull. High EMA → none.
        dissatisfaction = 1.0 - fb.ema
        trust = min(1.0, fb.samples / self.FULL_PULL_SAMPLES)
        return self.MAX_LEARNED_PULL * dissatisfaction * trust

    @staticmethod
    def _apply_feedback_pull(
        profile: SamplingProfile, task_class: TaskClass, pull: float
    ) -> SamplingProfile:
        if pull <= 0.0 or task_class is TaskClass.BALANCED:
            return profile
        anchor = BASE_PROFILES[TaskClass.BALANCED].temperature
        return SamplingProfile(
            temperature=profile.temperature + (anchor - profile.temperature) * pull,
            top_p=profile.top_p,
            top_k=profile.top_k,
            frequency_penalty=profile.frequency_penalty,
            presence_penalty=profile.presence_penalty,
        ).clamped()

    @staticmethod
    def _apply_overrides(
        profile: SamplingProfile, overrides: dict[str, Any]
    ) -> tuple[SamplingProfile, list[str]]:
        if not overrides:
            return profile, []
        data = profile.to_dict()
        applied: list[str] = []
        for key in ("temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty"):
            if key in overrides and overrides[key] is not None:
                data[key] = overrides[key]
                applied.append(key)
        pinned = SamplingProfile(
            temperature=float(data["temperature"]),
            top_p=float(data["top_p"]),
            top_k=int(data["top_k"]),
            frequency_penalty=float(data["frequency_penalty"]),
            presence_penalty=float(data["presence_penalty"]),
        )
        # Overrides are user authority — clamped only to provider-safe ranges,
        # never blended or learned away.
        return pinned.clamped(), applied

    @staticmethod
    def _deltas(anchor: SamplingProfile, final: SamplingProfile) -> dict[str, float]:
        out: dict[str, float] = {}
        for key in ("temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty"):
            diff = float(getattr(final, key)) - float(getattr(anchor, key))
            if abs(diff) > 1e-9:
                out[key] = round(diff, 4)
        return out
