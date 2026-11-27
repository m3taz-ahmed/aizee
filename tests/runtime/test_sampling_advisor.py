"""Tests for runtime/sampling_advisor.py — adaptive sampling parameters."""

from __future__ import annotations

from runtime.sampling_advisor import (
    BASE_PROFILES,
    PENALTY_MAX,
    TEMP_MAX,
    SamplingAdvisor,
    SamplingDecision,
    SamplingProfile,
    TaskClass,
)


class TestProfileClamping:
    def test_clamp_temperature_high(self):
        p = SamplingProfile(temperature=99.0).clamped()
        assert p.temperature == TEMP_MAX

    def test_clamp_temperature_low(self):
        assert SamplingProfile(temperature=-5.0).clamped().temperature == 0.0

    def test_clamp_top_p_bounds(self):
        assert SamplingProfile(temperature=0.5, top_p=2.0).clamped().top_p == 1.0
        assert SamplingProfile(temperature=0.5, top_p=-1.0).clamped().top_p == 0.0

    def test_clamp_top_k(self):
        assert SamplingProfile(temperature=0.5, top_k=9999).clamped().top_k == 512
        assert SamplingProfile(temperature=0.5, top_k=-3).clamped().top_k == 1

    def test_top_k_zero_stays_unset(self):
        assert SamplingProfile(temperature=0.5, top_k=0).clamped().top_k == 0

    def test_clamp_penalties(self):
        p = SamplingProfile(
            temperature=0.5, frequency_penalty=99.0, presence_penalty=-99.0
        ).clamped()
        assert p.frequency_penalty == PENALTY_MAX
        assert p.presence_penalty == -PENALTY_MAX

    def test_in_range_unchanged(self):
        p = SamplingProfile(temperature=0.5, top_p=0.9, top_k=40, presence_penalty=0.1)
        assert p.clamped() == p


class TestBlend:
    def test_blend_midpoint(self):
        a = SamplingProfile(temperature=0.0, top_p=0.8)
        b = SamplingProfile(temperature=1.0, top_p=1.0)
        mixed = a.blend(b, 0.5)
        assert abs(mixed.temperature - 0.5) < 1e-6
        assert abs(mixed.top_p - 0.9) < 1e-6

    def test_blend_weight_clamped(self):
        a = SamplingProfile(temperature=0.2)
        b = SamplingProfile(temperature=1.0)
        assert a.blend(b, 5.0).temperature == 1.0
        assert a.blend(b, -5.0).temperature == 0.2

    def test_blend_top_k_both_set(self):
        a = SamplingProfile(temperature=0.5, top_k=10)
        b = SamplingProfile(temperature=0.5, top_k=50)
        assert a.blend(b, 0.5).top_k == 30

    def test_blend_top_k_one_set(self):
        a = SamplingProfile(temperature=0.5, top_k=0)
        b = SamplingProfile(temperature=0.5, top_k=40)
        mixed = a.blend(b, 0.5)
        assert mixed.top_k in (20, 40)  # scaled or carried

    def test_blend_top_k_neither_set(self):
        a = SamplingProfile(temperature=0.5, top_k=0)
        b = SamplingProfile(temperature=0.5, top_k=0)
        assert a.blend(b, 0.5).top_k == 0

    def test_to_dict_rounds(self):
        d = SamplingProfile(temperature=0.123456).to_dict()
        assert d["temperature"] == round(0.123456, 4)
        assert set(d) == {"temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty"}


class TestClassify:
    def test_code_prompt(self):
        advisor = SamplingAdvisor()
        tc, conf, hits = advisor.classify(
            "write a python function that parses yaml and import json cleanly"
        )
        assert tc is TaskClass.CODE
        assert conf > 0.0
        assert hits.get("code", 0) > 0

    def test_creative_prompt(self):
        advisor = SamplingAdvisor()
        tc, _, _ = advisor.classify("write me a poem and a short story, be creative")
        assert tc is TaskClass.CREATIVE

    def test_analytical_prompt(self):
        advisor = SamplingAdvisor()
        tc, _, _ = advisor.classify(
            "analyze and compare the trade-offs, evaluate pros and cons of this architecture"
        )
        assert tc is TaskClass.ANALYTICAL

    def test_factual_prompt(self):
        advisor = SamplingAdvisor()
        tc, _, _ = advisor.classify("what is the exact correct answer? cite a verifiable source")
        assert tc is TaskClass.FACTUAL

    def test_conversational_prompt(self):
        advisor = SamplingAdvisor()
        tc, _, _ = advisor.classify("hello! what do you think, want to chat?")
        assert tc is TaskClass.CONVERSATIONAL

    def test_empty_no_match_returns_balanced(self):
        advisor = SamplingAdvisor()
        tc, conf, hits = advisor.classify("zzz qqq xwxw")
        assert tc is TaskClass.BALANCED
        assert conf == 0.0
        assert hits == {}

    def test_evidence_softening(self):
        advisor = SamplingAdvisor()
        _, conf_weak, _ = advisor.classify("python")
        strong_text = "python function class import debug refactor typescript javascript ```"
        _, conf_strong, _ = advisor.classify(strong_text)
        assert conf_strong > conf_weak


class TestAdvise:
    def test_code_gets_low_temperature(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("write a python function using import and class, fix the code")
        assert d.params.temperature <= 0.6  # code base 0.2, possibly blended
        assert d.task_class is TaskClass.CODE

    def test_balanced_class_never_blended(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("xyzzy plugh nothing matches")
        assert d.task_class is TaskClass.BALANCED
        assert d.blended_to_balanced is False
        assert d.params.temperature == BASE_PROFILES[TaskClass.BALANCED].temperature

    def test_low_confidence_blends(self):
        advisor = SamplingAdvisor()
        # competing weak hits → confidence below threshold → blended toward balanced
        d = advisor.advise("python story")
        assert d.confidence < SamplingAdvisor.BLEND_THRESHOLD
        assert d.task_class is not TaskClass.BALANCED
        assert d.blended_to_balanced is True
        base = BASE_PROFILES[d.task_class].temperature
        anchor = BASE_PROFILES[TaskClass.BALANCED].temperature
        assert min(base, anchor) <= d.params.temperature <= max(base, anchor)

    def test_overrides_win(self):
        advisor = SamplingAdvisor()
        d = advisor.advise(
            "write a python function import class",
            overrides={"temperature": 1.7},
        )
        assert d.params.temperature == 1.7
        assert "temperature" in d.overridden_keys

    def test_override_none_skipped(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("write a python function import class", overrides={"temperature": None})
        assert "temperature" not in d.overridden_keys

    def test_override_clamped_to_provider_range(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("hello", overrides={"temperature": 99.0})
        assert d.params.temperature == TEMP_MAX

    def test_no_overrides_no_keys(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("hello there what do you think")
        assert d.overridden_keys == ()

    def test_history_repetition_nudge(self):
        advisor = SamplingAdvisor()
        short = advisor.advise("hello what do you think", history_len=0)
        long = advisor.advise("hello what do you think", history_len=30)
        assert long.params.presence_penalty > short.params.presence_penalty

    def test_history_nudge_capped(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("hello what do you think", history_len=10000)
        assert d.params.presence_penalty <= 0.3 + 1e-6

    def test_deltas_present_vs_balanced(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("write a python function import class def")
        if d.params.temperature != BASE_PROFILES[TaskClass.BALANCED].temperature:
            assert "temperature" in d.param_deltas

    def test_deltas_empty_when_matching_balanced(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("xyzzy no matches", overrides={
            "temperature": 0.5, "top_p": 0.95, "top_k": 0,
            "frequency_penalty": 0.0, "presence_penalty": 0.0,
        })
        assert d.param_deltas == {}

    def test_decision_to_dict_shape(self):
        advisor = SamplingAdvisor()
        d = advisor.advise("write a python function import class")
        out = d.to_dict()
        for key in ("task_class", "confidence", "params", "param_deltas",
                    "pattern_matches", "overridden_keys", "learned_pull", "blended_to_balanced"):
            assert key in out


class TestOpenAIExport:
    def test_minimal_export(self):
        d = SamplingDecision(
            params=SamplingProfile(temperature=0.5),
            task_class=TaskClass.BALANCED,
            confidence=1.0,
            pattern_matches={},
            param_deltas={},
        )
        out = d.to_openai_params()
        assert out == {"temperature": 0.5, "top_p": 1.0}

    def test_full_export(self):
        d = SamplingDecision(
            params=SamplingProfile(
                temperature=0.9, top_p=0.98, top_k=40,
                frequency_penalty=0.3, presence_penalty=0.2,
            ),
            task_class=TaskClass.CREATIVE,
            confidence=0.9,
            pattern_matches={},
            param_deltas={},
        )
        out = d.to_openai_params()
        assert out["top_k"] == 40
        assert out["frequency_penalty"] == 0.3
        assert out["presence_penalty"] == 0.2


class TestFeedbackLoop:
    def test_no_pull_before_min_samples(self):
        advisor = SamplingAdvisor()
        advisor.record_feedback(TaskClass.CODE, positive=False)
        assert advisor._learned_pull(TaskClass.CODE) == 0.0

    def test_negative_feedback_pulls_toward_balanced(self):
        advisor = SamplingAdvisor()
        for _ in range(20):
            advisor.record_feedback(TaskClass.CODE, positive=False)
        pull = advisor._learned_pull(TaskClass.CODE)
        assert pull > 0.0
        base = BASE_PROFILES[TaskClass.CODE].temperature
        d = advisor.advise("write a python function import class def", overrides={"top_k": 40})
        if pull >= 0.4 and d.confidence >= SamplingAdvisor.BLEND_THRESHOLD:
            assert d.params.temperature > base  # pulled up toward 0.5

    def test_positive_feedback_no_pull(self):
        advisor = SamplingAdvisor()
        for _ in range(20):
            advisor.record_feedback(TaskClass.CODE, positive=True)
        assert advisor._learned_pull(TaskClass.CODE) < 0.1

    def test_pull_capped(self):
        advisor = SamplingAdvisor()
        for _ in range(100):
            advisor.record_feedback(TaskClass.CREATIVE, positive=False)
        assert advisor._learned_pull(TaskClass.CREATIVE) <= SamplingAdvisor.MAX_LEARNED_PULL + 1e-9

    def test_pull_balanced_class_zero(self):
        advisor = SamplingAdvisor()
        assert advisor._learned_pull(TaskClass.BALANCED) == 0.0

    def test_record_unknown_class_ignored(self):
        advisor = SamplingAdvisor()
        advisor.record_feedback(TaskClass.BALANCED, positive=False)  # not tracked
        assert TaskClass.BALANCED.value not in advisor.feedback_state()

    def test_feedback_state_roundtrip(self):
        a1 = SamplingAdvisor()
        for _ in range(5):
            a1.record_feedback(TaskClass.ANALYTICAL, positive=False)
        state = a1.feedback_state()
        a2 = SamplingAdvisor()
        a2.load_feedback_state(state)
        assert a2.feedback_state()["analytical"]["samples"] == 5
        assert abs(
            a2.feedback_state()["analytical"]["ema"] - state["analytical"]["ema"]
        ) < 0.001

    def test_load_feedback_unknown_class_skipped(self):
        advisor = SamplingAdvisor()
        advisor.load_feedback_state({"not_a_class": {"ema": 0.1, "samples": 9}})
        assert "not_a_class" not in advisor.feedback_state()

    def test_load_feedback_balanced_skipped(self):
        advisor = SamplingAdvisor()
        advisor.load_feedback_state({"balanced": {"ema": 0.1, "samples": 9}})
        assert "balanced" not in advisor.feedback_state()

    def test_load_feedback_clamped(self):
        advisor = SamplingAdvisor()
        advisor.load_feedback_state({"code": {"ema": 99.0, "samples": -5}})
        state = advisor.feedback_state()["code"]
        assert state["ema"] == 1.0
        assert state["samples"] == 0

    def test_feedback_pull_noop_when_zero(self):
        # pull=0 → profile returned unchanged (identity branch)
        advisor = SamplingAdvisor()
        d1 = advisor.advise("write a poem story creative fiction imagine")
        assert d1.learned_pull == 0.0
