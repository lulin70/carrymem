"""CarryMem 入口点错误处理工具.

提供统一的错误处理和输出格式约定，确保 CLI/TUI/MCP 三入口行为一致。

使用方式:
    from carrymem.utils.entry_point_helpers import (
        format_cli_error,
        format_mcp_error,
        format_tui_error,
        success_response,
        error_response,
        EntryPointError,
    )
"""

from typing import Any, Dict, Optional

from carrymem.errors import CarryMemError


class EntryPointError(Exception):
    """入口点统一错误基类.

    所有入口点（CLI/TUI/MCP）应该使用此类或其子类来报告错误，
    确保错误码格式一致（CM-xxx）。
    """

    def __init__(
        self,
        code: str = "CM-600",
        message: str = "Entry point error occurred.",
        entry_type: str = "unknown",  # cli, tui, mcp
        hint: str = "",
        original_error: Optional[Exception] = None,
    ):
        self.code = code
        self.message = message
        self.entry_type = entry_type
        self.hint = hint
        self.original_error = original_error
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.hint:
            parts.append(f"💡 {self.hint}")
        return "\n  ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 MCP/JSON 输出）."""
        result = {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "entry_type": self.entry_type,
            },
        }
        if self.hint:
            result["error"]["hint"] = self.hint
        return result


# ── 错误码常量（CM-600~699 用于入口点）─────────────────────────

# CLI 错误 (CM-600~619)
ERR_CLI_UNKNOWN_COMMAND = "CM-600"
ERR_CLI_INVALID_ARGS = "CM-601"
ERR_CLI_MISSING_CONFIG = "CM-602"

# TUI 错误 (CM-620~639)
ERR_TUI_DEPENDENCY_MISSING = "CM-620"
ERR_TUI_INIT_FAILED = "CM-621"
ERR_TUI_RENDER_ERROR = "CM-622"

# MCP 错误 (CM-640~659)
ERR_MCP_UNKNOWN_TOOL = "CM-640"
ERR_MCP_INVALID_PARAMS = "CM-641"
ERR_MCP_AUTH_FAILED = "CM-642"
ERR_MCP_INTERNAL = "CM-649"


def format_cli_error(error: Exception) -> tuple:
    """格式化 CLI 错误输出.

    Args:
        error: 异常对象（CarryMemError 或其他 Exception）

    Returns:
        (exit_code: int, output_lines: list[str])
    """
    if isinstance(error, CarryMemError):
        lines = [
            f"  [ERROR] {error.code}",
            f"  {error.message}",
        ]
        if error.hint:
            lines.append(f"  💡 {error.hint}")
        return (1, lines)

    # 转换为 CarryMemError
    friendly = CarryMemError.from_cause(error)
    return format_cli_error(friendly)


def format_mcp_error(error: Exception) -> Dict[str, Any]:
    """格式化 MCP 错误响应.

    Args:
        error: 异常对象

    Returns:
        标准化的 MCP 错误响应字典
    """
    if isinstance(error, CarryMemError):
        return {
            "success": False,
            "error": {
                "code": error.code,
                "type": _map_cm_code_to_mcp_type(error.code),
                "message": error.message,
            },
        }

    # 转换通用异常
    friendly = CarryMemError.from_cause(error)
    return format_mcp_error(friendly)


def format_tui_error(error: Exception) -> Dict[str, str]:
    """格式化 TUI 错误显示数据.

    Args:
        error: 异常对象

    Returns:
        TUI ErrorDisplay 组件所需的数据字典
    """
    if isinstance(error, CarryMemError):
        data = {
            "code": error.code,
            "message": error.message,
            "hint": error.hint or "",
        }
        return data

    # 转换通用异常
    friendly = CarryMemError.from_cause(error)
    return format_tui_error(friendly)


def success_response(data: Any = None, message: str = "Operation successful") -> Dict[str, Any]:
    """创建标准成功响应.

    Args:
        data: 响应数据（可选）
        message: 成功消息

    Returns:
        标准化成功响应字典
    """
    response = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    return response


def error_response(
    code: str,
    message: str,
    error_type: str = "internal_error",
    hint: str = "",
) -> Dict[str, Any]:
    """创建标准错误响应.

    Args:
        code: CM-xxx 格式的错误码
        message: 用户友好的错误消息
        error_type: MCP 风格的错误类型标识
        hint: 可选的解决提示

    Returns:
        标准化错误响应字典
    """
    response = {
        "success": False,
        "error": {
            "code": code,
            "type": error_type,
            "message": message,
        },
    }
    if hint:
        response["error"]["hint"] = hint
    return response


def _map_cm_code_to_mcp_type(cm_code: str) -> str:
    """将 CM-xxx 错误码映射到 MCP 错误类型.

    Args:
        cm_code: CM-xxx 格式的错误码

    Returns:
        MCP 风格的错误类型字符串
    """
    # 配置与初始化错误
    if cm_code.startswith("CM-00") or cm_code.startswith("CM-01"):
        return "configuration_error"

    # 存储适配器错误
    if cm_code.startswith("CM-10") or cm_code.startswith("CM-11"):
        return "storage_error"

    # 记忆操作错误
    if cm_code.startswith("CM-20"):
        return "memory_operation_error"

    # 分类/规则引擎错误
    if cm_code.startswith("CM-30"):
        return "classification_error"

    # 安全/加密错误
    if cm_code.startswith("CM-40"):
        return "security_error"

    # 导入/导出错误
    if cm_code.startswith("CM-50"):
        return "import_export_error"

    # 入口点错误
    if cm_code.startswith("CM-60"):
        return "entry_point_error"

    # 默认
    return "internal_error"


# 模块级便捷导出
__all__ = [
    # 类
    "EntryPointError",
    # 错误码常量
    "ERR_CLI_UNKNOWN_COMMAND",
    "ERR_CLI_INVALID_ARGS",
    "ERR_CLI_MISSING_CONFIG",
    "ERR_TUI_DEPENDENCY_MISSING",
    "ERR_TUI_INIT_FAILED",
    "ERR_TUI_RENDER_ERROR",
    "ERR_MCP_UNKNOWN_TOOL",
    "ERR_MCP_INVALID_PARAMS",
    "ERR_MCP_AUTH_FAILED",
    "ERR_MCP_INTERNAL",
    # 格式化函数
    "format_cli_error",
    "format_mcp_error",
    "format_tui_error",
    "success_response",
    "error_response",
]
