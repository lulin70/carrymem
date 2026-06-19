"""CarryMem Error Code System.

Error code ranges:
  CM-001 ~ CM-099: Configuration & Initialization
  CM-100 ~ CM-199: Storage Adapter
  CM-200 ~ CM-299: Memory Operations
  CM-300 ~ CM-399: Classification & Rule Engine
  CM-400 ~ CM-499: Security & Encryption
  CM-500 ~ CM-599: Import / Export
  CM-600 ~ CM-699: CLI / TUI / MCP Entry Points
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from carrymem.error_messages import ERROR_MESSAGES, ErrorTemplate
from carrymem.exceptions import CarryMemError as _BaseCarryMemError


class CarryMemError(_BaseCarryMemError):
    """Base error class with error code, user-friendly message, hint, and cause chain."""

    def __init__(
        self,
        code: str = "CM-000",
        message: str = "An unknown error occurred.",
        hint: str = "",
        cause: Optional[Exception] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        self.cause = cause
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.hint:
            parts.append(f"💡 {self.hint}")
        return "\n  ".join(parts)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"

    # ── Factory: convert low-level exceptions → CarryMemError ──────

    @classmethod
    def from_cause(cls, exc: Exception) -> CarryMemError:
        """Map a low-level exception to a friendly CarryMemError."""
        exc_type = type(exc)
        exc_msg = str(exc)
        exc_module = exc_type.__module__

        # sqlite3 errors
        if "sqlite3" in exc_module or "IntegrityError" in exc_type.__name__:
            return _map_sqlite_error(exc, exc_msg)

        # OSError / IO errors
        if isinstance(exc, (OSError, IOError)):
            return _map_os_error(exc, exc_msg)

        # ValueError / TypeError from our code
        if isinstance(exc, ValueError):
            return _map_value_error(exc, exc_msg)

        # Encryption errors
        if "EncryptionError" in exc_type.__name__ or "encryption" in exc_module:
            return CarryMemError(
                code="CM-401",
                message=ERROR_MESSAGES.get("CM-401", {}).get("zh", "Encryption failed."),
                hint=ERROR_MESSAGES.get("CM-401", {}).get("hint_zh", "Check your encryption key configuration."),
                cause=exc,
            )

        # Known CarryMem exceptions
        for err_cls, template in _EXCEPTION_MAP.items():
            if isinstance(exc, err_cls):
                return CarryMemError(
                    code=template.code,
                    message=template.zh,
                    hint=template.hint_zh,
                    cause=exc,
                )

        # Fallback
        return CarryMemError(
            code="CM-999",
            message=f"Unexpected error: {exc_msg[:200]}",
            hint="Please report this error with the error code CM-999.",
            cause=exc,
        )


# ── Concrete error classes (optional, for programmatic handling) ──


class ConfigError(CarryMemError):
    """Configuration or initialization error (CM-001~099)."""


class StorageAdapterError(CarryMemError):
    """Storage adapter error (CM-100~199)."""


class MemoryOperationError(CarryMemError):
    """Memory operation error (CM-200~299)."""


class ClassificationError(CarryMemError):
    """Classification / rule engine error (CM-300~399)."""


class SecurityError(CarryMemError):
    """Security / encryption error (CM-400~499)."""


class ImportExportError(CarryMemError):
    """Import / export error (CM-500~599)."""


class CLIEntryError(CarryMemError):
    """CLI / TUI / MCP entry point error (CM-600~699)."""


# ── Internal mapping helpers ───────────────────────────────────────


def _map_sqlite_error(exc: Exception, msg: str) -> CarryMemError:
    msg_lower = msg.lower()
    if "unique constraint failed" in msg_lower or "unique" in msg_lower and "constraint" in msg_lower:
        return CarryMemError(
            code="CM-102",
            message=ERROR_MESSAGES.get("CM-102", {}).get("zh", "Duplicate data detected."),
            hint=ERROR_MESSAGES.get("CM-102", {}).get(
                "hint_zh", "This record may already exist. Try updating instead of creating."
            ),
            cause=exc,
        )
    if "no such table" in msg_lower:
        return CarryMemError(
            code="CM-103",
            message=ERROR_MESSAGES.get("CM-103", {}).get("zh", "Database table missing."),
            hint=ERROR_MESSAGES.get("CM-103", {}).get("hint_zh", "Run 'carrymem init' to initialize the database."),
            cause=exc,
        )
    if "database is locked" in msg_lower:
        return CarryMemError(
            code="CM-104",
            message=ERROR_MESSAGES.get("CM-104", {}).get("zh", "Database is locked by another process."),
            hint=ERROR_MESSAGES.get("CM-104", {}).get(
                "hint_zh", "Close other CarryMem instances or wait a moment and retry."
            ),
            cause=exc,
        )
    if "unable to open database" in msg_lower or "disk i/o" in msg_lower:
        return CarryMemError(
            code="CM-105",
            message=ERROR_MESSAGES.get("CM-105", {}).get("zh", "Cannot open database file."),
            hint=ERROR_MESSAGES.get("CM-105", {}).get(
                "hint_zh", "Check file permissions and disk space. Run 'carrymem doctor --fix'."
            ),
            cause=exc,
        )
    # Generic SQLite error
    return CarryMemError(
        code="CM-101",
        message=ERROR_MESSAGES.get("CM-101", {}).get("zh", "Database operation failed."),
        hint=ERROR_MESSAGES.get("CM-101", {}).get(
            "hint_zh", f"Details: {msg[:150]}. Run 'carrymem doctor' for diagnostics."
        ),
        cause=exc,
    )


def _map_os_error(exc: Exception, msg: str) -> CarryMemError:
    msg_lower = msg.lower()
    if "permission denied" in msg_lower or "permission" in msg_lower:
        return CarryMemError(
            code="CM-106",
            message=ERROR_MESSAGES.get("CM-106", {}).get("zh", "Permission denied."),
            hint=ERROR_MESSAGES.get("CM-106", {}).get(
                "hint_zh", "Check file/directory permissions. Try running with appropriate access rights."
            ),
            cause=exc,
        )
    if "no space left" in msg_lower or "disk full" in msg_lower:
        return CarryMemError(
            code="CM-107",
            message=ERROR_MESSAGES.get("CM-107", {}).get("zh", "Disk space insufficient."),
            hint=ERROR_MESSAGES.get("CM-107", {}).get("hint_zh", "Free up disk space before retrying."),
            cause=exc,
        )
    if "file not found" in msg_lower or "no such file" in msg_lower:
        return CarryMemError(
            code="CM-108",
            message=ERROR_MESSAGES.get("CM-108", {}).get("zh", "File not found."),
            hint=ERROR_MESSAGES.get("CM-108", {}).get(
                "hint_zh", "Verify the file path exists. Run 'carrymem init' if needed."
            ),
            cause=exc,
        )
    return CarryMemError(
        code="CM-109",
        message=ERROR_MESSAGES.get("CM-109", {}).get("zh", "File system operation failed."),
        hint=ERROR_MESSAGES.get("CM-109", {}).get("hint_zh", f"Details: {msg[:150]}."),
        cause=exc,
    )


def _map_value_error(exc: Exception, msg: str) -> CarryMemError:
    msg_lower = msg.lower()
    if "knowledge" in msg_lower and "not configured" in msg_lower:
        return CarryMemError(
            code="CM-110",
            message=ERROR_MESSAGES.get("CM-110", {}).get("zh", "Knowledge base adapter not configured."),
            hint=ERROR_MESSAGES.get("CM-110", {}).get(
                "hint_zh", "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path')) to enable knowledge features."
            ),
            cause=exc,
        )
    if "adapter" in msg_lower and ("not configured" in msg_lower or "unknown" in msg_lower):
        return CarryMemError(
            code="CM-100",
            message=ERROR_MESSAGES.get("CM-100", {}).get("zh", "Storage adapter not configured or unknown."),
            hint=ERROR_MESSAGES.get("CM-100", {}).get(
                "hint_zh", "Use CarryMem(storage='sqlite') or provide a valid StorageAdapter instance."
            ),
            cause=exc,
        )
    if "validation" in msg_lower or "invalid" in msg_lower:
        return CarryMemError(
            code="CM-201",
            message=ERROR_MESSAGES.get("CM-201", {}).get("zh", "Input validation failed."),
            hint=ERROR_MESSAGES.get("CM-201", {}).get("hint_zh", "Check your input format and required fields."),
            cause=exc,
        )
    if "path" in msg_lower and ("escape" in msg_lower or "traversal" in msg_lower or "dangerous" in msg_lower):
        return CarryMemError(
            code="CM-402",
            message=ERROR_MESSAGES.get("CM-402", {}).get("zh", "Path security check failed."),
            hint=ERROR_MESSAGES.get("CM-402", {}).get(
                "hint_zh", "The specified path is not allowed for security reasons."
            ),
            cause=exc,
        )
    return CarryMemError(
        code="CM-202",
        message=ERROR_MESSAGES.get("CM-202", {}).get("zh", "Invalid input or parameter."),
        hint=ERROR_MESSAGES.get("CM-202", {}).get("hint_zh", f"Details: {msg[:150]}"),
        cause=exc,
    )


# ── Known exception → error-code mapping ──────────────────────────

_EXCEPTION_MAP: Dict[Type[Exception], ErrorTemplate] = {}

try:
    from carrymem.exceptions import ClassificationError as _ClassificationError
    from carrymem.exceptions import DatabaseError as _DatabaseError
    from carrymem.exceptions import DBConnectionError as _DBConnectionError
    from carrymem.exceptions import KnowledgeNotConfiguredError as _KnowledgeNotConfiguredError
    from carrymem.exceptions import QueryError as _QueryError
    from carrymem.exceptions import StorageError as _StorageError
    from carrymem.exceptions import StorageNotConfiguredError as _StorageNotConfiguredError
    from carrymem.exceptions import ValidationError as _ValidationError

    _EXCEPTION_MAP.update(
        {
            _StorageNotConfiguredError: ErrorTemplate(
                code="CM-100",
                zh="存储适配器未配置。",
                en="Storage adapter is not configured.",
                hint_zh="使用 CarryMem(storage='sqlite') 或传入 StorageAdapter 实例来启用存储功能。",
                hint_en="Use CarryMem(storage='sqlite') or pass a StorageAdapter instance.",
            ),
            _KnowledgeNotConfiguredError: ErrorTemplate(
                code="CM-110",
                zh="知识库适配器未配置。",
                en="Knowledge base adapter is not configured.",
                hint_zh="使用 CarryMem(knowledge_adapter=ObsidianAdapter('/path')) 来启用知识库功能。",
                hint_en="Use CarryMem(knowledge_adapter=ObsidianAdapter('/path')).",
            ),
            _DatabaseError: ErrorTemplate(
                code="CM-101",
                zh="数据库操作失败。",
                en="Database operation failed.",
                hint_zh="运行 'carrymem doctor' 进行诊断检查。",
                hint_en="Run 'carrymem doctor' for diagnostics.",
            ),
            _DBConnectionError: ErrorTemplate(
                code="CM-111",
                zh="无法连接到数据库。",
                en="Unable to connect to the database.",
                hint_zh="检查数据库路径和文件权限。运行 'carrymem init' 初始化数据库。",
                hint_en="Check DB path and permissions. Run 'carrymem init'.",
            ),
            _QueryError: ErrorTemplate(
                code="CM-112",
                zh="数据库查询执行失败。",
                en="Database query execution failed.",
                hint_zh="检查查询参数是否正确。运行 'carrymem doctor' 排查问题。",
                hint_en="Check query parameters. Run 'carrymem doctor'.",
            ),
            _ClassificationError: ErrorTemplate(
                code="CM-301",
                zh="记忆分类失败。",
                en="Memory classification failed.",
                hint_zh="请检查记忆内容格式，确保文本不为空且长度合理。",
                hint_en="Ensure memory content is non-empty and reasonably sized.",
            ),
            _ValidationError: ErrorTemplate(
                code="CM-201",
                zh="输入验证未通过。",
                en="Input validation failed.",
                hint_zh="请检查必填字段和数据格式是否符合要求。",
                hint_en="Check required fields and data format.",
            ),
            _StorageError: ErrorTemplate(
                code="CM-120",
                zh="存储操作发生错误。",
                en="A storage operation error occurred.",
                hint_zh="检查存储配置和可用空间。运行 'carrymem doctor' 获取详细诊断。",
                hint_en="Check storage config and available space. Run 'carrymem doctor'.",
            ),
        }
    )
except ImportError:
    pass


__all__ = [
    # Base error class
    "CarryMemError",
    # Concrete error classes (by category)
    "ConfigError",  # CM-001~099: Configuration
    "StorageAdapterError",  # CM-100~199: Storage
    "MemoryOperationError",  # CM-200~299: Memory ops
    "ClassificationError",  # CM-300~399: Classification
    "SecurityError",  # CM-400~499: Security
    "ImportExportError",  # CM-500~599: Import/Export
    "CLIEntryError",  # CM-600~699: CLI/TUI/MCP
    # Internal mappers (exposed for testing)
    "_map_sqlite_error",
    "_map_os_error",
    "_map_value_error",
]
