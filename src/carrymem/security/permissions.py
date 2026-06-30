"""Lightweight permission & access-control framework (P1-8 MVP).

Provides a simple user-ID-based access policy model:

- ``Permission``: Enum-like constants for read/write/delete/admin.
- ``AccessPolicy``: Owner-based policy — owner has all permissions,
  other users have none.  Designed to be swapped out for RBAC/ABAC later.

Integration points:
- CarryMem facade stores an optional ``access_policy`` attribute.
- Write/delete operations call ``policy.require()`` before executing.
- Read operations are allowed for all users in MVP mode.
"""

from __future__ import annotations


from carrymem.errors import SecurityError


class Permission:
    """Permission level constants.

    Usage::

        Permission.READ   # read memories / knowledge
        Permission.WRITE  # create / update memories
        Permission.DELETE # forget / remove memories
        Permission.ADMIN  # administrative operations
    """

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

    _ALL = {READ, WRITE, DELETE, ADMIN}

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if ``value`` is a recognized permission."""
        return value in cls._ALL


class AccessPolicy:
    """Simple owner-based access policy (MVP).

    In this minimal model:

    * The **owner** (set at construction) holds all permissions.
    * Any **other user** holds no permissions.
    * This is intentionally strict — it can be loosened later (e.g.,
      public-read, team-scoped, etc.) without breaking the interface.

    Args:
        owner_id: The user ID that owns this policy instance.
    """

    def __init__(self, owner_id: str) -> None:
        if not owner_id or not isinstance(owner_id, str):
            raise SecurityError(
                code="CM-403",
                message="owner_id must be a non-empty string.",
                hint="Provide a valid user identifier string.",
            )
        self.owner_id = owner_id

    def check(self, user_id: str, permission: Permission) -> bool:
        """Check whether *user_id* has *permission*.

        Args:
            user_id: The user requesting access.
            permission: The :class:`Permission` level required.

        Returns:
            ``True`` if the user has the requested permission.
        """
        if not Permission.is_valid(permission):  # type: ignore[arg-type]
            raise SecurityError(
                code="CM-403",
                message=f"Invalid permission: {permission!r}",
                hint=f"Valid permissions: {Permission._ALL}",
            )
        return user_id == self.owner_id

    def require(
        self,
        user_id: str,
        permission: Permission,
        resource: str = "resource",
    ) -> None:
        """Require *user_id* to have *permission*; raise on denial.

        Args:
            user_id: The user requesting access.
            permission: The :class:`Permission` level required.
            resource: Human-readable description of the resource (for error messages).

        Raises:
            SecurityError(CM-403): If the user lacks the required permission.
        """
        if not self.check(user_id, permission):
            # Log denied access attempt
            try:
                from carrymem.security.audit import log_denied

                log_denied(
                    resource=resource,
                    user_id=user_id,
                    action=permission.upper(),  # type: ignore[attr-defined]
                    details={"required_permission": permission, "owner_id": self.owner_id},
                )
            except Exception:
                pass  # Audit logging should never break the main flow

            raise SecurityError(
                code="CM-403",
                message=(f"User '{user_id}' does not have '{permission}' " f"permission on {resource}."),
                hint=(f"Only the owner ('{self.owner_id}') can perform this action."),
            )

    def __repr__(self) -> str:
        return f"AccessPolicy(owner_id={self.owner_id!r})"


__all__ = [
    "Permission",
    "AccessPolicy",
]
