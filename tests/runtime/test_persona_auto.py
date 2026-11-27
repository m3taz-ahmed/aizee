"""Detection tests for the AUTO persona (spec AIZEE-PERSONA-PROMPT §8.1).

Positive cases must route to AUTO (with specified secondary personas);
negative cases must not. Regression guard: existing persona detections
must keep working.
"""

from __future__ import annotations

from runtime.persona import PersonaDetector


class TestAutoPersonaRegistration:
    def test_auto_registered_with_expected_shape(self):
        d = PersonaDetector()
        personas = d.list_personas()
        assert "AUTO" in personas
        entry = d.PERSONAS["AUTO"]
        assert entry["skill"] == "automotive-diagnostics-engineer"
        assert entry["weight"] == 1.4
        assert d.tier_for("AUTO") == "specialist"
        for lord in (
            "embedded-firmware-lord",
            "can-bus-lord",
            "diagnostic-protocols-lord",
            "gm-opel-lord",
            "automotive-hardware-safety-lord",
            "diagnostic-safety-lord",
            "reverse-engineering-lord",
        ):
            assert lord in entry["lords"]

    def test_persona_count_at_least_30(self):
        d = PersonaDetector()
        assert len(d.list_personas()) >= 30

    def test_no_bare_car_keywords(self):
        """Collision guard: AUTO must not own bare 'car'/'عربية' — those
        produce false positives on rental-site and generic-Arabic prompts."""
        d = PersonaDetector()
        kws = [k.strip().lower() for k in d.PERSONAS["AUTO"]["keywords"]]
        assert "car" not in kws
        assert "عربية" not in kws


class TestAutoPositiveDetection:
    def test_esp32_can_bridge_opel(self):
        d = PersonaDetector()
        result = d.detect_multiple("ESP32 CAN bridge to read Opel Vectra fault codes")
        assert result["persona"] == "AUTO"

    def test_arabic_elm327_faults(self):
        d = PersonaDetector()
        result = d.detect_multiple("عايز أقرا أعطال كمبيوتر العربية بـ ELM327")
        assert result["persona"] == "AUTO"
        assert result["low_confidence"] is False

    def test_kwp_security_access_gm(self):
        d = PersonaDetector()
        result = d.detect_multiple("KWP2000 security access seed key on GM ECU")
        assert result["persona"] == "AUTO"
        assert "SEC" in result["personas"]

    def test_flet_obd_dashboard_auto_primary_ux_secondary(self):
        d = PersonaDetector()
        result = d.detect_multiple("Flet dashboard for live OBD gauges")
        assert result["persona"] == "AUTO"
        assert "UX" in result["personas"]

    def test_auto_not_low_confidence_on_domain_prompts(self):
        d = PersonaDetector()
        result = d.detect_multiple("ESP32 embedded firmware CAN bus automotive diagnostics")
        assert result["low_confidence"] is False
        assert result["persona"] == "AUTO"


class TestAutoNegativeDetection:
    def test_car_rental_website_not_auto(self):
        d = PersonaDetector()
        result = d.detect_multiple("car rental booking website in Laravel")
        assert result["persona"] != "AUTO"
        assert "AUTO" not in result["personas"]

    def test_canvas_drawing_app_not_auto(self):
        d = PersonaDetector()
        result = d.detect_multiple("CANVAS drawing app")
        assert result["persona"] != "AUTO"

    def test_generic_arabic_website_not_auto(self):
        d = PersonaDetector()
        result = d.detect_multiple("عايز موقع لبيع العربيات المستعملة")
        assert result["persona"] != "AUTO"


class TestExistingPersonasNotRegressed:
    """Regression guard: adding AUTO must not steal existing detections."""

    def test_security_still_sec(self):
        d = PersonaDetector()
        assert d.detect("audit the firewall and fix zero trust auth")["persona"] == "SEC"

    def test_qa_still_qa(self):
        d = PersonaDetector()
        assert d.detect("increase test coverage and write edge case tests")["persona"] == "QA"

    def test_game_still_game(self):
        d = PersonaDetector()
        assert d.detect("optimize the babylon.js game loop for 60 fps")["persona"] == "GAME"

    def test_dev_backend_still_dev(self):
        d = PersonaDetector()
        assert d.detect("backend api server")["persona"] == "DEV"
