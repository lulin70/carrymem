"""Evidence link API tests (Phase 1 Provenance, ADR-015).

Covers contract invariants:
  - INV-E1: namespace consistency + namespace-scoped queries
  - INV-E2: links are immutable (no update path; supersedes via new link)
  - INV-E3: (source, target, relation) uniqueness — idempotent writes
  - INV-E4: unsupported-target detection when sources vanish

Uses real SQLiteAdapter (in-memory) per testing philosophy — no mocks.
"""

from __future__ import annotations

import pytest

from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.adapters.sqlite.evidence import VALID_RELATION_TYPES
from carrymem.monitoring import get_metrics_collector


@pytest.fixture
def adapter() -> SQLiteAdapter:
    return SQLiteAdapter(":memory:", namespace="default", enable_vector_search=False)


@pytest.fixture
def clean_metrics():
    collector = get_metrics_collector()
    collector.reset()
    yield collector
    collector.reset()


def _store_memory(adapter: SQLiteAdapter, id_: str, content: str, namespace: str = "default") -> str:
    from carrymem.adapters.base import MemoryEntry

    stored = adapter.store_entry(MemoryEntry(id=id_, type="fact_declaration", content=content, raw_text=content))
    return stored.storage_key


class TestAddEvidenceLinkValidation:
    """Enum and argument validation (closed enums per contract §2.2)."""

    def test_invalid_relation_type_raises(self, adapter):
        with pytest.raises(ValueError, match="relation_type"):
            adapter.add_evidence_link(
                namespace="default",
                source_kind="memory",
                source_id="s1",
                source_snapshot_hash="h",
                target_kind="memory",
                target_id="t1",
                relation_type="made_up",
            )

    def test_invalid_source_kind_raises(self, adapter):
        with pytest.raises(ValueError, match="source_kind"):
            adapter.add_evidence_link(
                namespace="default",
                source_kind="ghost",
                source_id="s1",
                source_snapshot_hash="h",
                target_kind="memory",
                target_id="t1",
                relation_type="supports",
            )

    def test_invalid_target_kind_raises(self, adapter):
        with pytest.raises(ValueError, match="target_kind"):
            adapter.add_evidence_link(
                namespace="default",
                source_kind="memory",
                source_id="s1",
                source_snapshot_hash="h",
                target_kind="ghost",
                target_id="t1",
                relation_type="supports",
            )

    def test_empty_ids_raise(self, adapter):
        with pytest.raises(ValueError, match="non-empty"):
            adapter.add_evidence_link(
                namespace="default",
                source_kind="memory",
                source_id="",
                source_snapshot_hash="h",
                target_kind="memory",
                target_id="t1",
                relation_type="supports",
            )

    def test_relation_type_enum_is_closed(self):
        assert VALID_RELATION_TYPES == frozenset(
            {"supports", "contradicts", "derived_from", "observed_in", "confirmed_by", "supersedes"}
        )


class TestEvidenceLinkIdempotency:
    """INV-E3: duplicate writes do not create a second row."""

    def test_duplicate_write_returns_none(self, adapter, clean_metrics):
        link_id = adapter.add_evidence_link(
            namespace="default",
            source_kind="memory",
            source_id="s1",
            source_snapshot_hash="h1",
            target_kind="memory",
            target_id="t1",
            relation_type="derived_from",
        )
        assert link_id is not None

        duplicate = adapter.add_evidence_link(
            namespace="default",
            source_kind="memory",
            source_id="s1",
            source_snapshot_hash="h1",
            target_kind="memory",
            target_id="t1",
            relation_type="derived_from",
        )
        assert duplicate is None

        links = adapter.list_evidence_links("default", target_id="t1")
        assert len(links) == 1

    def test_only_successful_insert_increments_metric(self, adapter, clean_metrics):
        args = dict(
            namespace="default",
            source_kind="memory",
            source_id="s1",
            target_kind="memory",
            target_id="t1",
            relation_type="derived_from",
        )
        adapter.add_evidence_link(source_snapshot_hash="h1", **args)
        adapter.add_evidence_link(source_snapshot_hash="h1", **args)  # duplicate

        snapshot = clean_metrics.get_snapshot()
        assert snapshot["counters"].get("evidence_link_derived_from", 0) == 1

    def test_different_relation_creates_separate_link(self, adapter):
        args = dict(
            namespace="default",
            source_kind="memory",
            source_id="s1",
            source_snapshot_hash="h1",
            target_kind="memory",
            target_id="t1",
        )
        first = adapter.add_evidence_link(relation_type="supports", **args)
        second = adapter.add_evidence_link(relation_type="contradicts", **args)
        assert first is not None and second is not None
        assert len(adapter.list_evidence_links("default", target_id="t1")) == 2


class TestEvidenceNamespaceIsolation:
    """INV-E1: queries are namespace-scoped; cross-namespace never leaks."""

    def test_links_do_not_leak_across_namespaces(self, adapter):
        common_args = dict(
            source_kind="memory",
            source_id="s1",
            source_snapshot_hash="h1",
            target_kind="memory",
            target_id="t1",
            relation_type="derived_from",
        )
        adapter.add_evidence_link(namespace="ns_a", **common_args)

        assert len(adapter.list_evidence_links("ns_a", target_id="t1")) == 1
        assert adapter.list_evidence_links("ns_b", target_id="t1") == []

    def test_same_pair_in_two_namespaces_is_two_links(self, adapter):
        common_args = dict(
            source_kind="memory",
            source_id="s1",
            source_snapshot_hash="h1",
            target_kind="memory",
            target_id="t1",
            relation_type="derived_from",
        )
        adapter.add_evidence_link(namespace="ns_a", **common_args)
        adapter.add_evidence_link(namespace="ns_b", **common_args)

        assert len(adapter.list_evidence_links("ns_a")) == 1
        assert len(adapter.list_evidence_links("ns_b")) == 1


class TestEvidenceStaleness:
    """INV-E4/E5: validity is source-existence based."""

    def test_include_stale_false_hides_vanished_sources(self, adapter):
        target_key = _store_memory(adapter, "t1", "target memory")
        source_key = _store_memory(adapter, "s1", "source memory")

        adapter.add_evidence_link(
            namespace="default",
            source_kind="memory",
            source_id=source_key,
            source_snapshot_hash="h1",
            target_kind="memory",
            target_id=target_key,
            relation_type="derived_from",
        )

        assert len(adapter.list_evidence_links("default", target_id=target_key, include_stale=True)) == 1
        assert len(adapter.list_evidence_links("default", target_id=target_key, include_stale=False)) == 1

        adapter.delete(source_key)  # source vanishes — link becomes stale

        assert len(adapter.list_evidence_links("default", target_id=target_key, include_stale=True)) == 1
        assert adapter.list_evidence_links("default", target_id=target_key, include_stale=False) == []

    def test_get_unsupported_targets_flags_only_evidenceless(self, adapter):
        t_supported = _store_memory(adapter, "t1", "supported derived")
        t_orphan = _store_memory(adapter, "t2", "orphan derived")
        s_live = _store_memory(adapter, "s1", "live source")
        s_dying = _store_memory(adapter, "s2", "dying source")

        def link(source_id, target_id):
            adapter.add_evidence_link(
                namespace="default",
                source_kind="memory",
                source_id=source_id,
                source_snapshot_hash="h",
                target_kind="memory",
                target_id=target_id,
                relation_type="derived_from",
            )

        link(s_live, t_supported)
        link(s_dying, t_orphan)

        # Before deletion: nothing unsupported.
        assert adapter._get_evidence().get_unsupported_targets("default", [t_supported, t_orphan]) == []

        adapter.delete(s_dying)

        unsupported = adapter._get_evidence().get_unsupported_targets("default", [t_supported, t_orphan])
        assert unsupported == [t_orphan]

    def test_delete_cascade_flags_derived_metadata(self, adapter, clean_metrics):
        """INV-E4 materialization: forget() annotates provenance_unsupported."""
        source_key = _store_memory(adapter, "s1", "shared source")
        derived_key = _store_memory(adapter, "t1", "derived conclusion")

        adapter.add_evidence_link(
            namespace="default",
            source_kind="memory",
            source_id=source_key,
            source_snapshot_hash="h",
            target_kind="memory",
            target_id=derived_key,
            relation_type="derived_from",
        )

        adapter.delete(source_key)

        stored = adapter.get_by_key(derived_key)
        assert stored is not None
        meta = stored.metadata or {}
        assert meta.get("provenance_unsupported") == 1
        assert "provenance_unsupported_at" in meta
        assert clean_metrics.get_snapshot()["counters"].get("evidence_derived_unsupported", 0) == 1

    def test_delete_cascade_spares_multi_source_derivations(self, adapter):
        """A target with one surviving source stays supported."""
        s1 = _store_memory(adapter, "s1", "source one")
        s2 = _store_memory(adapter, "s2", "source two")
        derived_key = _store_memory(adapter, "t1", "derived conclusion")

        for sid in (s1, s2):
            adapter.add_evidence_link(
                namespace="default",
                source_kind="memory",
                source_id=sid,
                source_snapshot_hash="h",
                target_kind="memory",
                target_id=derived_key,
                relation_type="derived_from",
            )

        adapter.delete(s1)

        stored = adapter.get_by_key(derived_key)
        meta = stored.metadata or {}
        assert meta.get("provenance_unsupported") is None

    def test_delete_cascade_spares_plain_memories(self, adapter):
        """Memories without derivation links are never flagged."""
        plain = _store_memory(adapter, "p1", "a plain user memory")
        unrelated = _store_memory(adapter, "p2", "another plain memory")

        adapter.delete(unrelated)

        stored = adapter.get_by_key(plain)
        meta = stored.metadata or {}
        assert meta.get("provenance_unsupported") is None
