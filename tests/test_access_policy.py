"""Tests for AccessPolicy integration into the MCP tool invocation chain (TD-035).

Verifies that:
- Single-user mode (default namespace + no ``default_user_id``) preserves the
  existing behavior — writes are allowed without a user_id (characterization
  testing principle: do not break existing single-user callers).
- When ``default_user_id`` is provided, an ``AccessPolicy`` is configured with
  that owner_id, and write/delete operations are subject to permission checks.
- Multi-namespace mode (``namespace != "default"``) with no explicit owner
  auto-enforces access policy using the namespace as the fallback owner_id.
- ``handle_tool`` reports ``SecurityError`` as
  ``{"success": False, "error": "access_denied"}`` so MCP clients can
  distinguish authorization failures from successful operations.
- Read operations remain unaffected by the access policy (MVP scope, per the
  ``security/permissions.py`` module docstring).

Companion to ``tests/test_permissions_mvp.py`` which covers the
``AccessPolicy`` class and the CarryMem facade directly; this module focuses
on the MCP ``Handlers`` integration layer.
"""

import pytest

from carrymem.integration.layer2_mcp.handlers import Handlers
from carrymem.security.permissions import AccessPolicy, Permission

# ══════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_db(tmp_path):
    """Per-test sqlite db path under pytest's tmp_path."""
    return str(tmp_path / "test_access_policy.db")


# ══════════════════════════════════════════════════════════════════
#  Single-user mode — preserves existing behavior (NO policy set)
# ══════════════════════════════════════════════════════════════════


class TestSingleUserModeNoPolicy:
    """Default namespace + no ``default_user_id`` → no AccessPolicy configured.

    This preserves the existing single-user behavior: writes/deletes without
    a user_id succeed.  Adding a policy unconditionally here would break
    existing MCP callers that never pass ``user_id``.
    """

    def test_no_policy_set_in_single_user_mode(self, temp_db):
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="default")
        try:
            assert handlers._carrymem.access_policy is None
        finally:
            handlers.cleanup()

    async def test_write_succeeds_without_user_id(self, temp_db):
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="default")
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()

    async def test_declare_succeeds_without_user_id(self, temp_db):
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="default")
        try:
            result = await handlers.handle_tool(
                "declare_preference",
                {"message": "I prefer tea over coffee"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()


# ══════════════════════════════════════════════════════════════════
#  Explicit default_user_id — AccessPolicy enforced with that owner
# ══════════════════════════════════════════════════════════════════


class TestExplicitUserIdEnforced:
    """When ``default_user_id`` is provided, an ``AccessPolicy`` is attached to
    the CarryMem instance with that owner_id, and write/delete operations are
    subject to permission checks via the existing ``_check_write_permission``
    / ``_check_delete_permission`` hooks.
    """

    def test_policy_set_with_default_user_id(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            policy = handlers._carrymem.access_policy
            assert policy is not None
            assert isinstance(policy, AccessPolicy)
            assert policy.owner_id == "alice"
            assert policy.check("alice", Permission.WRITE) is True
            assert policy.check("bob", Permission.WRITE) is False
        finally:
            handlers.cleanup()

    async def test_owner_write_succeeds_via_auto_injection(self, temp_db):
        """Anonymous call (no user_id) gets ``user_id=alice`` auto-injected
        by the P0-1 injection logic, matching the owner → write succeeds.
        """
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()

    async def test_non_owner_write_rejected(self, temp_db):
        """Explicit ``user_id`` that does NOT match the owner → access_denied."""
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode", "user_id": "bob"},
            )
            assert result.get("success") is False
            assert result.get("error") == "access_denied"
        finally:
            handlers.cleanup()

    async def test_non_owner_declare_rejected(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            result = await handlers.handle_tool(
                "declare_preference",
                {"message": "I prefer tea", "user_id": "eve"},
            )
            assert result.get("success") is False
            assert result.get("error") == "access_denied"
        finally:
            handlers.cleanup()


# ══════════════════════════════════════════════════════════════════
#  Multi-namespace mode — namespace used as fallback owner
# ══════════════════════════════════════════════════════════════════


class TestMultiNamespaceFallbackOwner:
    """When ``namespace != "default"`` and no ``default_user_id`` is provided,
    AccessPolicy is configured with the namespace as the fallback owner_id.
    This guarantees a non-default namespace cannot be mutated anonymously —
    a client must either pass ``user_id=<namespace>`` explicitly, or rely on
    the auto-injection (which mirrors ``_default_user_id = namespace``).
    """

    def test_policy_set_with_namespace_as_owner(self, temp_db):
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="tenant_42")
        try:
            policy = handlers._carrymem.access_policy
            assert policy is not None
            assert policy.owner_id == "tenant_42"
            # _default_user_id is mirrored so the P0-1 injection logic
            # auto-supplies user_id=namespace for anonymous write/delete calls.
            assert handlers._default_user_id == "tenant_42"
        finally:
            handlers.cleanup()

    async def test_anonymous_write_succeeds_in_multi_namespace(self, temp_db):
        """Anonymous call gets ``user_id=tenant_42`` injected → matches owner → OK.

        This preserves ergonomics for the namespace owner while still blocking
        cross-user writes (see next test).
        """
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="tenant_42")
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()

    async def test_cross_user_write_rejected_in_multi_namespace(self, temp_db):
        """Client claiming to be a different user → access_denied."""
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="tenant_42")
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode", "user_id": "intruder"},
            )
            assert result.get("success") is False
            assert result.get("error") == "access_denied"
        finally:
            handlers.cleanup()

    async def test_explicit_namespace_user_id_succeeds(self, temp_db):
        """Client passing ``user_id=tenant_42`` explicitly → matches owner → OK."""
        handlers = Handlers(storage="sqlite", data_path=temp_db, namespace="tenant_42")
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode", "user_id": "tenant_42"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()


# ══════════════════════════════════════════════════════════════════
#  default_user_id takes precedence over namespace fallback
# ══════════════════════════════════════════════════════════════════


class TestDefaultUserIdPrecedence:
    """When BOTH ``default_user_id`` and a non-default namespace are provided,
    ``default_user_id`` wins — it's the explicit owner the operator chose.
    """

    def test_default_user_id_wins_over_namespace(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="tenant_42",
            default_user_id="alice",
        )
        try:
            policy = handlers._carrymem.access_policy
            assert policy is not None
            assert policy.owner_id == "alice"  # NOT "tenant_42"
        finally:
            handlers.cleanup()

    async def test_namespace_user_id_rejected_when_owner_overridden(self, temp_db):
        """Owner is alice, so passing user_id=tenant_42 fails (not the owner)."""
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="tenant_42",
            default_user_id="alice",
        )
        try:
            result = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode", "user_id": "tenant_42"},
            )
            assert result.get("success") is False
            assert result.get("error") == "access_denied"
        finally:
            handlers.cleanup()


# ══════════════════════════════════════════════════════════════════
#  Read operations are NOT blocked by access policy (MVP scope)
# ══════════════════════════════════════════════════════════════════


class TestReadsNotBlocked:
    """The MVP access policy only enforces WRITE/DELETE; reads remain open
    (per the ``security/permissions.py`` module docstring). This test ensures
    the integration does not accidentally restrict reads.
    """

    async def test_recall_memories_unaffected_by_policy(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            # Seed a memory as the owner
            seed = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode"},
            )
            assert seed.get("success") is True

            # Recall — recall_memories is not in _WRITE_DELETE_TOOLS, so
            # user_id is irrelevant and the policy is never consulted.
            result = await handlers.handle_tool(
                "recall_memories",
                {"query": "dark mode"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()

    async def test_get_system_prompt_unaffected_by_policy(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            result = await handlers.handle_tool(
                "get_system_prompt",
                {"context": "general chat"},
            )
            assert result.get("success") is True
        finally:
            handlers.cleanup()


# ══════════════════════════════════════════════════════════════════
#  Smoke: forget_memory also enforces DELETE permission
# ══════════════════════════════════════════════════════════════════


class TestDeleteEnforced:
    """``forget_memory`` is in ``_WRITE_DELETE_TOOLS`` and must enforce
    DELETE permission once a policy is configured.
    """

    async def test_non_owner_forget_rejected(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
            default_user_id="alice",
        )
        try:
            # Seed as the owner first
            seed = await handlers.handle_tool(
                "classify_and_remember",
                {"message": "I prefer dark mode"},
            )
            assert seed.get("success") is True

            # Try to forget as bob → access_denied
            # The memory_id check happens AFTER the permission check, so even
            # an invalid id will surface as access_denied first (fail-closed).
            result = await handlers.handle_tool(
                "forget_memory",
                {"memory_id": "any_id", "user_id": "bob"},
            )
            assert result.get("success") is False
            assert result.get("error") == "access_denied"
        finally:
            handlers.cleanup()
