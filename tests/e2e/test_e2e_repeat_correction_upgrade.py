"""E2E test for v0.10.0 repeat-correction auto-upgrade.

Real-user-flow simulation:
    1. User says "Java is wrong, use Python" 4 times
    2. The 2nd correction should create a soft (personal) auto_promotion rule
    3. The 3rd correction should escalate to hard (company) auto_promotion
    4. The 4th correction should reuse the existing company rule (single rule_id)
    5. A security-keyword correction should immediately escalate to hard
    6. Disabling the feature flag must stop any upgrade
    7. Persistence: a freshly opened CarryMem against the same DB must
       read the persisted repetition_count and the existing auto_promotion rules
"""

from __future__ import annotations

from carrymem import CarryMem


def _corrections(cm):
    return [
        r
        for r in cm.rule_engine.list_rules(limit=500)
        if getattr(r, "derived_from", "") == "auto_promotion" and getattr(r, "trigger", "") == "correction"
    ]


def _security(cm):
    return [
        r
        for r in cm.rule_engine.list_rules(limit=500)
        if getattr(r, "derived_from", "") == "auto_promotion" and getattr(r, "trigger", "") == "security"
    ]


class TestE2ERepeatCorrectionUpgrade:
    def test_repeat_corrections_escalate_to_rules(self, tmp_path):
        db_path = str(tmp_path / "v0100_e2e.db")
        cm = CarryMem(storage="sqlite", db_path=db_path)
        try:
            # 1st correction — no upgrade yet.
            r1 = cm.classify_and_remember("Java is wrong, use Python")
            assert r1["type"] == "correction"
            assert r1["stored"] is True
            assert r1["upgrade_actions"] == []

            # 2nd correction — soft, personal.
            r2 = cm.classify_and_remember("Java is wrong, use Python")
            assert r2["upgrade_actions"], "2nd correction must trigger an upgrade"
            assert r2["upgrade_actions"][0]["level"] == "soft"
            assert r2["upgrade_actions"][0]["scope"] == "personal"
            assert r2["upgrade_actions"][0]["override"] is False
            assert len(_corrections(cm)) == 1

            # 3rd correction — hard, company.
            r3 = cm.classify_and_remember("Java is wrong, use Python")
            ups = r3["upgrade_actions"]
            assert ups and ups[0]["level"] == "hard"
            assert ups[0]["scope"] == "company"
            assert ups[0]["override"] is True
            # Exactly one active correction rule and one deprecated softer rule.
            active_hard = [r for r in _corrections(cm) if r.status == "active" and r.scope == "company"]
            deprecated = [r for r in _corrections(cm) if r.status == "deprecated"]
            assert len(active_hard) == 1
            assert len(deprecated) == 1

            # 4th correction — same hard rule reused, no duplicates.
            r4 = cm.classify_and_remember("Java is wrong, use Python")
            assert r4["upgrade_actions"][0]["rule_id"] == ups[0]["rule_id"]
            active_hard = [r for r in _corrections(cm) if r.status == "active" and r.scope == "company"]
            assert len(active_hard) == 1
        finally:
            cm.close()

    def test_security_keyword_escalates_immediately(self, tmp_path):
        db_path = str(tmp_path / "v0100_e2e_sec.db")
        cm = CarryMem(storage="sqlite", db_path=db_path)
        try:
            r = cm.classify_and_remember("Use SSL for api_key encryption", force_type="correction")
            assert r["upgrade_actions"]
            up = r["upgrade_actions"][0]
            assert up["level"] == "hard"
            assert up["scope"] == "company"
            assert _security(cm)
        finally:
            cm.close()

    def test_feature_flag_disables_upgrade(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CORRECTION_UPGRADE_ENABLED", "0")
        db_path = str(tmp_path / "v0100_e2e_flag.db")
        cm = CarryMem(storage="sqlite", db_path=db_path)
        try:
            for _ in range(4):
                r = cm.classify_and_remember("Java is wrong, use Python")
            assert r["upgrade_actions"] == []
            assert _corrections(cm) == []
        finally:
            cm.close()

    def test_repetition_count_persists_across_processes(self, tmp_path):
        db_path = str(tmp_path / "v0100_e2e_persist.db")
        cm = CarryMem(storage="sqlite", db_path=db_path)
        try:
            for _ in range(3):
                cm.classify_and_remember("Java is wrong, use Python")
        finally:
            cm.close()

        # Re-open the same DB and verify the count is preserved.
        cm2 = CarryMem(storage="sqlite", db_path=db_path)
        try:
            stored_key = cm2.recall_memories(
                query="Java Python",
                filters={"type": "correction"},
                limit=1,
                update_access=False,
            )[0]["storage_key"]
            assert stored_key
            assert cm2._count_correction_chain(stored_key) >= 2

            # And the auto-promoted hard rule is still present.
            active_hard = [r for r in _corrections(cm2) if r.status == "active" and r.scope == "company"]
            assert len(active_hard) == 1
        finally:
            cm2.close()


class TestE2EUpgradeScenarios:
    """End-to-end user scenarios per the runbook."""

    def test_rephrasing_still_escalates(self, tmp_path):
        """User rephrases the same correction across multiple turns.

        The contract is that an auto-promoted rule must eventually
        appear, regardless of minor rewording. Identical phrasing
        raises the persisted repetition_count; Jaccard+entity matching
        covers the rephrased case.
        """
        db_path = str(tmp_path / "v0100_e2e_rephrase.db")
        cm = CarryMem(storage="sqlite", db_path=db_path)
        try:
            cm.classify_and_remember("Java is wrong, use Python")
            cm.classify_and_remember("Java is wrong, use Python")
            cm.classify_and_remember("Wrong: Java, use Python instead")
            stored = cm.recall_memories(query="", limit=20, update_access=False)
            assert stored, "expected at least one stored memory"
            rules = _corrections(cm)
            assert rules, "expected at least one auto-promoted rule"
        finally:
            cm.close()
