"""Provenance wiring tests (Phase 1): derive_facts + aggregation + retain.

Covers contract invariants:
  - INV-F1: every derived object traces to >=1 original source via links
  - INV-R2: derived memories never carry user-statement source markers
  - INV-R1/R2 (retain side): user retains are annotated user_statement /
    user_correction at the row level
  - Snapshot hashes recorded for sources (staleness detection basis)

Uses real SQLiteAdapter / real CarryMem (in-memory) — no mocks.
"""

from __future__ import annotations

import pytest

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.carrymem import CarryMem
from carrymem.layers.memify import MemifyEngine


@pytest.fixture
def adapter() -> SQLiteAdapter:
    return SQLiteAdapter(":memory:", namespace="default", enable_vector_search=False)


@pytest.fixture
def adapter_with_co_occurring_entities(adapter: SQLiteAdapter) -> SQLiteAdapter:
    entries = [
        MemoryEntry(
            id="m1",
            type="fact_declaration",
            content="Python and PostgreSQL work well together",
            raw_text="Python and PostgreSQL work well together",
            confidence=0.9,
        ),
        MemoryEntry(
            id="m2",
            type="fact_declaration",
            content="Python and PostgreSQL for web apps",
            raw_text="Python and PostgreSQL for web apps",
            confidence=0.85,
        ),
        MemoryEntry(
            id="m3",
            type="fact_declaration",
            content="Python and PostgreSQL scaling strategies",
            raw_text="Python and PostgreSQL scaling strategies",
            confidence=0.8,
        ),
    ]
    for entry in entries:
        stored = adapter.store_entry(entry)
        # store_entry does not auto-extract entities at the adapter layer;
        # graph population happens via the real EntityNormalizer path.
        adapter.store_graph_entities(stored.storage_key, entry.content, "default")
    return adapter


class TestDeriveFactsProvenance:
    """INV-F1 + INV-R2 on the Memify derivation path."""

    def test_derived_memory_has_evidence_links(self, adapter_with_co_occurring_entities):
        memify = MemifyEngine(adapter=adapter_with_co_occurring_entities)
        derived = memify.derive_facts(namespace="default", min_co_occurrence=2)

        assert derived, "expected at least one derived fact"
        for fact in derived:
            links = adapter_with_co_occurring_entities.list_evidence_links(
                "default",
                target_kind="memory",
                target_id=fact["storage_key"],
                relation_type="derived_from",
            )
            assert links, f"derived fact {fact['storage_key']} has no evidence links (INV-F1)"
            for link in links:
                assert link["source_kind"] == "memory"
                assert link["source_snapshot_hash"], "source snapshot hash must be recorded"

    def test_link_sources_still_exist(self, adapter_with_co_occurring_entities):
        memify = MemifyEngine(adapter=adapter_with_co_occurring_entities)
        derived = memify.derive_facts(namespace="default", min_co_occurrence=2)

        for fact in derived:
            valid = adapter_with_co_occurring_entities.list_evidence_links(
                "default",
                target_id=fact["storage_key"],
                include_stale=False,
            )
            assert valid, f"all links for {fact['storage_key']} should point to live sources"

    def test_derived_source_layer_marks_inference(self, adapter_with_co_occurring_entities):
        """INV-R2: derivations must not look like user statements."""
        memify = MemifyEngine(adapter=adapter_with_co_occurring_entities)
        derived = memify.derive_facts(namespace="default", min_co_occurrence=2)

        assert derived
        for fact in derived:
            assert fact["source_layer"] == "memify_derived"
            assert fact["source_layer"] not in ("user_statement", "user_correction", "declaration")

    def test_rerun_derive_does_not_duplicate_links(self, adapter_with_co_occurring_entities):
        memify = MemifyEngine(adapter=adapter_with_co_occurring_entities)
        first = memify.derive_facts(namespace="default", min_co_occurrence=2)
        memify.derive_facts(namespace="default", min_co_occurrence=2)  # re-run

        for fact in first:
            links = adapter_with_co_occurring_entities.list_evidence_links(
                "default",
                target_id=fact["storage_key"],
                relation_type="derived_from",
            )
            # (source, target, relation) uniqueness caps growth even across runs.
            assert len(links) <= 3  # m1+m2+m3 co-occurrence basis


class TestRetainSourceAnnotation:
    """INV-R2 retain side: user retains carry explicit source markers."""

    @pytest.fixture
    def cm(self) -> CarryMem:
        return CarryMem(storage="sqlite", db_path=":memory:", namespace="default")

    def test_user_retain_annotated_user_statement(self, cm):
        result = cm.classify_and_remember("I prefer Python for backend work")
        assert result["stored"], f"expected store, got: {result.get('error')}"
        key = result["storage_keys"][0]

        stored = cm._adapter.get_by_key(key)
        assert stored.source_layer == "user_statement"

    def test_correction_retain_annotated_user_correction(self, cm):
        result = cm.classify_and_remember("Actually I now prefer Rust for backend work, ignore what I said before")
        assert result["stored"] or result.get("type") == "correction", result
        keys = result.get("storage_keys") or []
        if keys:
            stored = cm._adapter.get_by_key(keys[0])
            assert stored.source_layer == "user_correction"


class TestAggregationProvenance:
    """INV-F1 on the aggregation provenance path (rule backend)."""

    def test_aggregator_records_source_snapshot_hashes(self):
        """SemanticAggregator output carries per-source snapshot hashes."""
        from carrymem.layers.semantic_aggregator import SemanticAggregator

        def embedding_fn(_text):
            return [1.0, 0.0, 0.0]  # identical vectors → one cluster

        memories = [
            {
                "storage_key": f"sk{i}",
                "type": "user_preference",
                "content": f"pref variant {i}",
                "raw_text": f"pref variant {i}",
                "confidence": 0.9,
                "tier": 2,
                "created_at": f"2026-01-0{i}",
            }
            for i in range(1, 4)
        ]
        results = SemanticAggregator(llm_client=None, embedding_fn=embedding_fn).aggregate(memories=memories)

        assert results, "expected one aggregated result"
        meta = results[0]["metadata"]
        assert sorted(meta["aggregated_from"]) == ["sk1", "sk2", "sk3"]
        assert len(meta["aggregated_from_hashes"]) == 3
        by_key = {m["storage_key"]: m for m in memories}
        import hashlib

        for source_id, digest in zip(meta["aggregated_from"], meta["aggregated_from_hashes"]):
            expected = hashlib.sha256(by_key[source_id]["content"].encode("utf-8")).hexdigest()
            assert digest == expected

    def test_link_aggregation_evidence_writes_links(self, adapter):
        """_link_aggregation_evidence links every aggregated_from source."""
        from types import SimpleNamespace

        from carrymem.core._prompt_delegate import PromptDelegateMixin

        source_keys = []
        for i in range(2):
            entry = MemoryEntry(
                id=f"agg-src-{i}",
                type="user_preference",
                content=f"source preference {i}",
                raw_text=f"source preference {i}",
            )
            source_keys.append(adapter.store_entry(entry).storage_key)

        target = MemoryEntry(
            id="agg-target", type="user_preference", content="merged preference", raw_text="merged preference"
        )
        target_key = adapter.store_entry(target).storage_key

        aggregated = {
            "metadata": {
                "aggregated_from": source_keys,
                "aggregated_from_hashes": ["a" * 64, "b" * 64],
            }
        }
        host = SimpleNamespace(_adapter=adapter)
        PromptDelegateMixin._link_aggregation_evidence(host, aggregated, target_key)

        links = adapter.list_evidence_links("default", target_id=target_key, relation_type="derived_from")
        assert {link["source_id"] for link in links} == set(source_keys)

    def test_link_aggregation_evidence_tolerates_bad_hash(self, adapter):
        """Empty hashes are rejected by validation, never fatal (honest degradation)."""
        from types import SimpleNamespace

        from carrymem.core._prompt_delegate import PromptDelegateMixin

        aggregated = {"metadata": {"aggregated_from": ["sk-x"], "aggregated_from_hashes": [""]}}
        host = SimpleNamespace(_adapter=adapter)
        # Must not raise.
        PromptDelegateMixin._link_aggregation_evidence(host, aggregated, "some-target")
        assert adapter.list_evidence_links("default", target_id="some-target") == []
