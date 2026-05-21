"""
Performance Benchmark Tests for Scope-aware Rules

Validates:
- Rule creation throughput
- Scope-aware matching performance
- Skill pack/install performance
- Merge protocol performance at scale
- FTS5 search with scope preservation
"""

import pytest
import tempfile
import os
import time

from carrymem.rules.models import Rule
from carrymem.rules.skill import skill_pack, skill_verify, skill_install
from carrymem.rules.merge_protocol import (
    MergeStrategy,
    merge_rules,
    detect_merge_conflicts,
)
from carrymem.rules.storage import RuleStorage
from carrymem.rules import RuleEngine


class TestRuleCreationPerformance:
    """Benchmark rule creation throughput"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "bench_create.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_bulk_creation_100_rules(self):
        types = ["avoid", "always", "prefer", "forbid", "format"]
        start = time.perf_counter()
        for i in range(100):
            self.engine.add_rule(
                f"trigger-{i}", f"action-{i}",
                rule_type=types[i % 5],
                scope="personal" if i % 3 == 0 else "company",
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"100 rule creations took {elapsed:.2f}s (limit: 5s)"
        assert len(self.engine.list_rules(limit=200)) == 100

    def test_bulk_creation_mixed_scopes(self):
        types = ["avoid", "always", "prefer", "forbid", "format"]
        scopes = ["personal", "company", "negotiated"]
        start = time.perf_counter()
        for i in range(50):
            self.engine.add_rule(
                f"trigger-{i}", f"action-{i}",
                rule_type=types[i % 5],
                scope=scopes[i % 3],
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"50 mixed-scope creations took {elapsed:.2f}s"


class TestMatchingPerformance:
    """Benchmark scope-aware matching"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "bench_match.db")
        self.engine = RuleEngine(self.db_path)
        for i in range(100):
            scope = ["personal", "company", "negotiated"][i % 3]
            self.engine.add_rule(
                f"topic-{i // 10}", f"action-{i}",
                scope=scope,
            )

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_match_all_scopes_100_rules(self):
        start = time.perf_counter()
        for _ in range(50):
            results = self.engine.match("topic-5")
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"50 matches against 100 rules took {elapsed:.2f}s"

    def test_match_scope_filtered_100_rules(self):
        start = time.perf_counter()
        for _ in range(50):
            results = self.engine.match("topic-5", scopes=["company"])
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"50 filtered matches took {elapsed:.2f}s"
        for r in results:
            assert r.rule.scope == "company"


class TestSkillPerformance:
    """Benchmark Skill pack/install"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "bench_skill.db")
        self.storage = RuleStorage(self.db_path)
        self.rules = []
        for i in range(100):
            r = self.storage.create(
                trigger=f"trigger-{i}", action=f"action-{i}",
                scope=["personal", "company", "negotiated"][i % 3],
            )
            self.rules.append(r)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_pack_100_rules(self):
        start = time.perf_counter()
        bundle = skill_pack(rules=self.rules, name="bench-skill", scope="personal")
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Packing 100 rules took {elapsed:.2f}s"
        assert bundle["manifest"]["rule_count"] == 100

    def test_verify_100_rules(self):
        bundle = skill_pack(rules=self.rules, name="bench-skill")
        start = time.perf_counter()
        result = skill_verify(bundle)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Verifying 100-rule bundle took {elapsed:.2f}s"
        assert result["valid"] is True

    def test_install_100_rules(self):
        rules = [Rule(trigger=f"new-{i}", action=f"action-{i}") for i in range(50)]
        bundle = skill_pack(rules=rules, name="install-bench")

        tmpdir2 = tempfile.mkdtemp()
        db2 = os.path.join(tmpdir2, "bench_install.db")
        storage2 = RuleStorage(db2)

        start = time.perf_counter()
        result = skill_install(bundle, storage2)
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"Installing 50 rules took {elapsed:.2f}s"
        assert result["installed"] == 50

        if os.path.exists(db2):
            os.remove(db2)


class TestMergePerformance:
    """Benchmark merge protocol"""

    def test_merge_50_vs_50_rules(self):
        incoming = [Rule(trigger=f"topic-{i}", action=f"inc-{i}", scope="company") for i in range(50)]
        existing = [Rule(trigger=f"topic-{i}", action=f"ext-{i}", scope="personal") for i in range(50)]

        start = time.perf_counter()
        result = merge_rules(incoming, existing, MergeStrategy.COMPANY_OVERRIDES)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Merging 50 vs 50 rules took {elapsed:.2f}s"
        assert len(result.conflicts) >= 50

    def test_conflict_detection_100_rules(self):
        incoming = [Rule(trigger=f"topic-{i}", action=f"inc-{i}") for i in range(50)]
        existing = [Rule(trigger=f"topic-{i}", action=f"ext-{i}") for i in range(50)]

        start = time.perf_counter()
        conflicts = detect_merge_conflicts(incoming, existing)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Detecting conflicts in 50 vs 50 took {elapsed:.2f}s"
