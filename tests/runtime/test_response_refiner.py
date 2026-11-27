"""Tests for runtime/response_refiner.py — versioned refinement loop."""

from __future__ import annotations

from runtime.response_refiner import (
    RefineConfig,
    RefinementResult,
    StopReason,
    Version,
    heuristic_score,
    refine,
)

RICH_TEXT = (
    "# Title\n\n"
    "First paragraph with enough words to count as substance in the length metric.\n\n"
    "- bullet one\n- bullet two\n\n"
    "Second paragraph with a variety of different words scattered throughout it."
)


class TestHeuristicScore:
    def test_empty_is_zero(self):
        assert heuristic_score("") == 0.0
        assert heuristic_score("   ") == 0.0

    def test_short_caps_low(self):
        assert heuristic_score("hi") < 0.3

    def test_structured_text_scores_higher(self):
        plain = "word " * 120  # long but unstructured
        assert heuristic_score(RICH_TEXT) > heuristic_score(plain)

    def test_repetition_penalized(self):
        repetitive = ("same line\n" * 30) + "\n\n"
        diverse = "\n".join(f"unique line number {i} with content" for i in range(30))
        assert heuristic_score(diverse) > heuristic_score(repetitive)

    def test_punctuation_only_no_words(self):
        # non-empty but zero word tokens — diversity guard path
        assert heuristic_score("!!! --- ***") >= 0.0

    def test_score_bounds(self):
        assert 0.0 <= heuristic_score(RICH_TEXT) <= 1.0

    def test_heading_only_structure(self):
        text = "## Just a heading with some text but no bullets or paragraphs " * 5
        assert heuristic_score(text) > 0.0

    def test_bullet_only_structure(self):
        text = "- item one of many\n- item two of many\n- item three of many " * 3
        assert heuristic_score(text) > 0.0


class TestVersion:
    def test_to_dict(self):
        v = Version(text="hello", score=0.5, iteration=1, accepted=True)
        d = v.to_dict()
        assert d == {"iteration": 1, "score": 0.5, "accepted": True, "chars": 5}


class TestRefineLoop:
    def test_zero_iterations_returns_initial(self):
        result = refine("draft", lambda t, i: t + " more", config=RefineConfig(max_iterations=0))
        assert result.final_text == "draft"
        assert result.iterations_run == 0
        assert result.stop_reason is StopReason.MAX_ITERATIONS
        assert len(result.versions) == 1

    def test_improvement_until_cap(self):
        # strictly increasing scores → hits the iteration cap
        def improver(text: str, iteration: int) -> str:
            return text + f"\n\nNew unique paragraph {iteration} " + "varied " * iteration * 5

        def increasing_score(text: str) -> float:
            return float(len(text))  # monotone in length — always improving

        result = refine(
            "start", improver,
            score_fn=increasing_score,
            config=RefineConfig(max_iterations=3, min_improvement=0.02),
        )
        assert result.iterations_run == 3
        assert result.stop_reason is StopReason.MAX_ITERATIONS
        assert len(result.versions) == 4
        assert all(v.accepted for v in result.versions)
        assert result.improved is True

    def test_converged_on_tiny_gain(self):
        calls = iter(["v1-better-tiny", "v2-should-not-happen"])
        scores = {"initial draft": 0.5, "v1-better-tiny": 0.505}

        result = refine(
            "initial draft",
            lambda t, i: next(calls),
            score_fn=lambda t: scores.get(t, 0.0),
            config=RefineConfig(max_iterations=5, min_improvement=0.02),
        )
        assert result.stop_reason is StopReason.CONVERGED
        assert result.final_text == "v1-better-tiny"  # tiny gain still accepted
        assert result.iterations_run == 1

    def test_regressed_candidate_rejected(self):
        scores = {"good draft": 0.8, "bad candidate": 0.3}

        result = refine(
            "good draft",
            lambda t, i: "bad candidate",
            score_fn=lambda t: scores[t],
            config=RefineConfig(max_iterations=3),
        )
        assert result.stop_reason is StopReason.REGRESSED
        assert result.final_text == "good draft"  # incumbent survives
        rejected = result.versions[-1]
        assert rejected.accepted is False
        assert result.improved is False

    def test_flat_candidate_is_regression(self):
        result = refine(
            "same",
            lambda t, i: "same",
            score_fn=lambda t: 0.5,
            config=RefineConfig(max_iterations=2),
        )
        assert result.stop_reason is StopReason.REGRESSED
        assert result.final_text == "same"

    def test_refiner_error_keeps_best(self):
        def boom(text: str, iteration: int) -> str:
            raise RuntimeError("provider exploded")

        result = refine("solid draft", boom, config=RefineConfig(max_iterations=3))
        assert result.stop_reason is StopReason.REFINER_ERROR
        assert result.final_text == "solid draft"
        assert result.iterations_run == 0  # failed round does not count

    def test_error_after_success_keeps_improved(self):
        state = {"calls": 0}

        def flaky(text: str, iteration: int) -> str:
            state["calls"] += 1
            if state["calls"] == 1:
                return text + "\n\n- improved structure bullet\n- another one"
            raise RuntimeError("second round exploded")

        result = refine(
            RICH_TEXT, flaky,
            config=RefineConfig(max_iterations=3, min_improvement=0.0),
        )
        assert result.stop_reason is StopReason.REFINER_ERROR
        assert "improved structure" in result.final_text

    def test_exact_threshold_gain_continues(self):
        scores = {"a": 0.50, "b": 0.52, "c": 0.54}
        seq = iter(["b", "c"])

        result = refine(
            "a",
            lambda t, i: next(seq),
            score_fn=lambda t: scores[t],
            config=RefineConfig(max_iterations=2, min_improvement=0.02),
        )
        assert result.stop_reason is StopReason.MAX_ITERATIONS
        assert result.final_text == "c"

    def test_improved_false_for_initial_only(self):
        result = refine("x", lambda t, i: t, config=RefineConfig(max_iterations=0))
        assert result.improved is False

    def test_to_dict_shape(self):
        result = refine("draft", lambda t, i: t, config=RefineConfig(max_iterations=1))
        d = result.to_dict()
        for key in ("final_score", "iterations_run", "stop_reason", "improved", "versions"):
            assert key in d
        assert d["stop_reason"] == StopReason.REGRESSED.value

    def test_default_heuristic_end_to_end(self):
        # no score_fn injected — the crude default drives the loop
        def pad(text: str, iteration: int) -> str:
            return text + "\n\nmore padding " * 50

        result = refine("short", pad, config=RefineConfig(max_iterations=2))
        assert isinstance(result, RefinementResult)
        assert len(result.versions) >= 2
