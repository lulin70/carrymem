"""Tests for permission & access-control framework (P1-8 MVP).

Covers:
- Permission constants and validation
- AccessPolicy construction, check(), require()
- Integration with CarryMem facade (access_policy property)
- Write/delete permission enforcement via MemoryCRUDMixin
"""

import pytest

from carrymem.errors import SecurityError
from carrymem.security.permissions import AccessPolicy, Permission

# ══════════════════════════════════════════════════════════════════
#  Permission constants
# ══════════════════════════════════════════════════════════════════


class TestPermission:
    """Tests for Permission constant class."""

    def test_read_constant(self):
        assert Permission.READ.value == "read"

    def test_write_constant(self):
        assert Permission.WRITE.value == "write"

    def test_delete_constant(self):
        assert Permission.DELETE.value == "delete"

    def test_admin_constant(self):
        assert Permission.ADMIN.value == "admin"

    def test_valid_permission_accepted(self):
        assert Permission.is_valid(Permission.READ) is True
        assert Permission.is_valid(Permission.ADMIN) is True
        assert Permission.is_valid("read") is True

    def test_invalid_permission_rejected(self):
        assert Permission.is_valid("execute") is False
        assert Permission.is_valid("") is False

    def test_all_permissions_covered(self):
        assert len(list(Permission)) == 4


# ══════════════════════════════════════════════════════════════════
#  AccessPolicy — construction
# ══════════════════════════════════════════════════════════════════


class TestAccessPolicyConstruction:
    """Tests for AccessPolicy initialization."""

    def test_create_with_owner_id(self):
        policy = AccessPolicy(owner_id="user_001")
        assert policy.owner_id == "user_001"

    def test_empty_owner_id_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            AccessPolicy(owner_id="")

    def test_none_owner_id_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            AccessPolicy(owner_id=None)  # type: ignore[arg-type]

    def test_repr_format(self):
        policy = AccessPolicy(owner_id="alice")
        assert "alice" in repr(policy)
        assert "AccessPolicy" in repr(policy)


# ══════════════════════════════════════════════════════════════════
#  AccessPolicy — check()
# ══════════════════════════════════════════════════════════════════


class TestAccessPolicyCheck:
    """Tests for AccessPolicy.check() method."""

    def setup_method(self):
        self.policy = AccessPolicy(owner_id="owner_123")

    def test_owner_has_read(self):
        assert self.policy.check("owner_123", Permission.READ) is True

    def test_owner_has_write(self):
        assert self.policy.check("owner_123", Permission.WRITE) is True

    def test_owner_has_delete(self):
        assert self.policy.check("owner_123", Permission.DELETE) is True

    def test_owner_has_admin(self):
        assert self.policy.check("owner_123", Permission.ADMIN) is True

    def test_other_user_has_no_permission(self):
        assert self.policy.check("other_user", Permission.READ) is False

    def test_other_user_cannot_write(self):
        assert self.policy.check("other_user", Permission.WRITE) is False

    def test_invalid_permission_raises(self):
        with pytest.raises(SecurityError, match="Invalid permission"):
            self.policy.check("owner_123", "fly")  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════
#  AccessPolicy — require()
# ══════════════════════════════════════════════════════════════════


class TestAccessPolicyRequire:
    """Tests for AccessPolicy.require() method."""

    def setup_method(self):
        self.policy = AccessPolicy(owner_id="alice")

    def test_owner_require_write_passes(self):
        # Should not raise
        self.policy.require("alice", Permission.WRITE)

    def test_owner_require_delete_passes(self):
        self.policy.require("alice", Permission.DELETE)

    def test_non_owner_require_write_raises(self):
        with pytest.raises(SecurityError, match="CM-403") as exc_info:
            self.policy.require("bob", Permission.WRITE)
        assert "bob" in exc_info.value.message
        assert "write" in exc_info.value.message.lower()

    def test_non_owner_require_delete_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            self.policy.require("eve", Permission.DELETE)

    def test_error_message_contains_owner_hint(self):
        with pytest.raises(SecurityError) as exc_info:
            self.policy.require("intruder", Permission.ADMIN)
        assert "alice" in exc_info.value.hint

    def test_custom_resource_in_error(self):
        with pytest.raises(SecurityError) as exc_info:
            self.policy.require("stranger", Permission.WRITE, resource="secret_data")
        assert "secret_data" in exc_info.value.message


# ══════════════════════════════════════════════════════════════════
#  Fail-closed integration: policy set + user_id=None (P0-1 fix)
# ══════════════════════════════════════════════════════════════════


class TestPermissionFailClosed:
    """P0-1 regression: when an access policy is configured, writes/deletes
    with user_id=None MUST raise SecurityError (fail-closed).

    Previously the check was skipped entirely when user_id was None,
    making AccessPolicy dead code in MCP context.
    """

    def setup_method(self):
        import tempfile

        from carrymem import CarryMem

        self._db = tempfile.mktemp(suffix=".db")
        self.cm = CarryMem(db_path=self._db)
        self.cm.access_policy = AccessPolicy(owner_id="alice")

    def teardown_method(self):
        self.cm.close()
        import os

        if os.path.exists(self._db):
            os.unlink(self._db)

    def test_write_without_user_id_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            self.cm.classify_and_remember("test message")

    def test_delete_without_user_id_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            self.cm.forget_memory("any_id")

    def test_declare_without_user_id_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            self.cm.declare("I prefer tea")

    def test_owner_write_passes(self):
        self.cm.classify_and_remember("test", user_id="alice")

    def test_non_owner_write_raises(self):
        with pytest.raises(SecurityError, match="CM-403"):
            self.cm.classify_and_remember("test", user_id="bob")

    def test_no_policy_allows_anonymous_write(self):
        """Single-user mode (no policy) should allow writes without user_id."""
        import tempfile

        from carrymem import CarryMem

        db = tempfile.mktemp(suffix=".db")
        cm = CarryMem(db_path=db)
        cm.access_policy = None  # explicitly no policy
        cm.classify_and_remember("test without policy")
        cm.close()
        import os

        os.unlink(db)
