"""Bilingual error message templates for CarryMem.

Each entry maps an error code to Chinese/English messages and hints.
Used by errors.py CarryMemError and by CLI/TUI for user-facing display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ErrorTemplate:
    """Immutable template for a single error code."""

    code: str
    zh: str
    en: str
    hint_zh: str = ""
    hint_en: str = ""


# ── Error message registry ────────────────────────────────────────

ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
    # ═══ CM-001 ~ CM-099: Configuration & Initialization ════════
    "CM-001": {
        "zh": "配置文件格式错误或缺少必要字段。",
        "en": "Configuration file is malformed or missing required fields.",
        "hint_zh": "检查配置文件 JSON/YAML 格式是否正确，确保所有必填字段存在。",
        "hint_en": "Verify config file format (JSON/YAML) and ensure all required fields are present.",
    },
    "CM-002": {
        "zh": "初始化失败：必要依赖缺失。",
        "en": "Initialization failed: required dependency missing.",
        "hint_zh": "运行 'pip install -e .' 安装所有依赖。",
        "hint_en": "Run 'pip install -e .' to install all dependencies.",
    },

    # ═══ CM-100 ~ CM-199: Storage Adapter ════════════════════════
    "CM-100": {
        "zh": "存储适配器未配置或类型未知。",
        "en": "Storage adapter not configured or unknown type.",
        "hint_zh": "使用 CarryMem(storage='sqlite') 或传入 StorageAdapter 实例。",
        "hint_en": "Use CarryMem(storage='sqlite') or pass a StorageAdapter instance.",
    },
    "CM-101": {
        "zh": "数据库操作执行失败。",
        "en": "Database operation execution failed.",
        "hint_zh": "运行 'carrymem doctor' 进行诊断检查。",
        "hint_en": "Run 'carrymem doctor' for diagnostics.",
    },
    "CM-102": {
        "zh": "检测到重复数据（唯一约束冲突）。",
        "en": "Duplicate data detected (unique constraint conflict).",
        "hint_zh": "该记录可能已存在。请尝试更新而非创建新记录。",
        "hint_en": "This record may already exist. Try updating instead of creating.",
    },
    "CM-103": {
        "zh": "数据库表不存在或未初始化。",
        "en": "Database table does not exist or is uninitialized.",
        "hint_zh": "运行 'carrymem init' 初始化数据库结构。",
        "hint_en": "Run 'carrymem init' to initialize database schema.",
    },
    "CM-104": {
        "zh": "数据库被其他进程锁定。",
        "en": "Database is locked by another process.",
        "hint_zh": "关闭其他 CarryMem 实例，稍后重试。",
        "hint_en": "Close other CarryMem instances or wait and retry.",
    },
    "CM-105": {
        "zh": "无法打开数据库文件。",
        "en": "Unable to open database file.",
        "hint_zh": "检查文件权限和磁盘空间。运行 'carrymem doctor --fix'。",
        "hint_en": "Check file permissions and disk space. Run 'carrymem doctor --fix'.",
    },
    "CM-106": {
        "zh": "文件权限不足，无法访问。",
        "en": "Permission denied: cannot access file or directory.",
        "hint_zh": "检查文件/目录权限，确保有读写权限。",
        "hint_en": "Check file/directory permissions. Ensure read/write access.",
    },
    "CM-107": {
        "zh": "磁盘空间不足。",
        "en": "Insufficient disk space.",
        "hint_zh": "释放磁盘空间后重试。",
        "hint_en": "Free up disk space before retrying.",
    },
    "CM-108": {
        "zh": "指定的文件不存在。",
        "en": "Specified file not found.",
        "hint_zh": "确认文件路径正确。如需初始化请运行 'carrymem init'。",
        "hint_en": "Verify the file path exists. Run 'carrymem init' if needed.",
    },
    "CM-109": {
        "zh": "文件系统操作失败。",
        "en": "File system operation failed.",
        "hint_zh": "检查磁盘状态和文件系统完整性。",
        "hint_en": "Check disk status and filesystem integrity.",
    },
    "CM-110": {
        "zh": "知识库适配器未配置。",
        "en": "Knowledge base adapter not configured.",
        "hint_zh": "使用 CarryMem(knowledge_adapter=ObsidianAdapter('/path')) 启用知识库功能。",
        "hint_en": "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path')).",
    },
    "CM-111": {
        "zh": "无法连接到数据库。",
        "en": "Unable to connect to the database.",
        "hint_zh": "检查数据库路径和文件权限。运行 'carrymem init' 初始化。",
        "hint_en": "Check DB path and permissions. Run 'carrymem init'.",
    },
    "CM-112": {
        "zh": "数据库查询执行失败。",
        "en": "Database query execution failed.",
        "hint_zh": "检查查询参数是否正确。运行 'carrymem doctor' 排查。",
        "hint_en": "Check query parameters. Run 'carrymem doctor'.",
    },
    "CM-120": {
        "zh": "存储操作发生错误。",
        "en": "A storage operation error occurred.",
        "hint_zh": "检查存储配置和可用空间。运行 'carrymem doctor' 获取详细诊断。",
        "hint_en": "Check storage config and available space. Run 'carrymem doctor'.",
    },

    # ═══ CM-200 ~ CM-299: Memory Operations ══════════════════════
    "CM-201": {
        "zh": "输入验证未通过。",
        "en": "Input validation failed.",
        "hint_zh": "请检查必填字段和数据格式是否符合要求。",
        "hint_en": "Check required fields and data format.",
    },
    "CM-202": {
        "zh": "输入参数无效或不合法。",
        "en": "Invalid input parameter.",
        "hint_zh": "检查参数类型、范围和格式。运行 'carrymem help' 查看用法。",
        "hint_en": "Check parameter type, range, and format. Run 'carrymem help' for usage.",
    },
    "CM-203": {
        "zh": "记忆内容为空或过短。",
        "en": "Memory content is empty or too short.",
        "hint_zh": "记忆内容至少需要包含几个字符的有效信息。",
        "hint_en": "Memory content must contain at least a few meaningful characters.",
    },
    "CM-204": {
        "zh": "指定的记忆条目不存在。",
        "en": "The specified memory entry does not exist.",
        "hint_zh": "使用 'carrymem list' 查看可用记忆，确认 key 正确。",
        "hint_en": "Use 'carrymem list' to view available memories and verify the key.",
    },
    "CM-205": {
        "zh": "记忆召回操作失败。",
        "en": "Memory recall operation failed.",
        "hint_zh": "检查搜索查询语法。尝试简化搜索关键词。",
        "hint_en": "Check search query syntax. Try simplifying search keywords.",
    },

    # ═══ CM-300 ~ CM-399: Classification & Rule Engine ════════════
    "CM-301": {
        "zh": "记忆分类失败。",
        "en": "Memory classification failed.",
        "hint_zh": "请检查记忆内容格式，确保文本不为空且长度合理。",
        "hint_en": "Ensure memory content is non-empty and reasonably sized.",
    },
    "CM-302": {
        "zh": "规则引擎执行出错。",
        "en": "Rule engine execution error.",
        "hint_zh": "检查规则定义格式是否正确。运行 'carrymem check-rules' 验证规则健康度。",
        "hint_en": "Check rule definition format. Run 'carrymem check-rules' to verify rule health.",
    },
    "CM-303": {
        "zh": "规则匹配失败：无匹配的规则。",
        "en": "Rule matching failed: no matching rules found.",
        "hint_zh": "使用 'carrymem suggest-rules' 分析记忆并生成规则建议。",
        "hint_en": "Use 'carrymem suggest-rules' to analyze memories and generate suggestions.",
    },
    "CM-304": {
        "zh": "规则冲突检测异常。",
        "en": "Rule conflict detection error.",
        "hint_zh": "运行 'carrymem check-rules' 查看冲突详情并手动解决。",
        "hint_en": "Run 'carrymem check-rules' to see conflict details and resolve manually.",
    },

    # ═══ CM-400 ~ CM-499: Security & Encryption ══════════════════
    "CM-401": {
        "zh": "加密操作失败。",
        "en": "Encryption operation failed.",
        "hint_zh": "检查加密密钥配置。密钥可能已损坏或过期。",
        "hint_en": "Check encryption key configuration. The key may be corrupted or expired.",
    },
    "CM-402": {
        "zh": "路径安全检查未通过（路径穿越检测）。",
        "en": "Path security check failed (path traversal detected).",
        "hint_zh": "出于安全原因，不允许访问该路径。请使用允许范围内的路径。",
        "hint_en": "Access to this path is blocked for security reasons. Use an allowed path.",
    },
    "CM-403": {
        "zh": "权限拒绝：用户没有执行此操作的权限。",
        "en": "Permission denied: user does not have permission for this operation.",
        "hint_zh": "检查用户ID是否正确，或联系管理员获取相应权限。",
        "hint_en": "Verify user ID or contact administrator for required permissions.",
    },
    "CM-404": {
        "zh": "输入内容触发了安全过滤规则。",
        "en": "Input content triggered security filter rules.",
        "hint_zh": "输入内容可能包含危险模式。如确信内容安全，请联系管理员。",
        "hint_en": "Input may contain dangerous patterns. If safe, contact administrator.",
    },
    "CM-408": {
        "zh": "解密失败：密钥不匹配或数据已损坏。",
        "en": "Decryption failed: key mismatch or data corruption.",
        "hint_zh": "确认使用的解密密钥与加密时一致。数据可能已被篡改。",
        "hint_en": "Ensure the decryption key matches the one used for encryption. Data may be tampered.",
    },

    # ═══ CM-500 ~ CM-599: Import / Export ════════════════════════
    "CM-501": {
        "zh": "导入文件格式不受支持或已损坏。",
        "en": "Import file format is unsupported or corrupted.",
        "hint_zh": "支持的格式：JSON (.json)、Carry 文件 (.carry)。确认文件完整无损。",
        "hint_en": "Supported formats: JSON (.json), Carry files (.carry). Verify file integrity.",
    },
    "CM-502": {
        "zh": "导出操作失败。",
        "en": "Export operation failed.",
        "hint_zh": "检查目标路径是否有写入权限和足够磁盘空间。",
        "hint_en": "Check target path has write permission and sufficient disk space.",
    },
    "CM-503": {
        "zh": "导入数据校验失败：存在无效记录。",
        "en": "Import data validation failed: invalid records found.",
        "hint_zh": "检查导入文件中的数据格式，修复无效记录后重试。",
        "hint_en": "Check data format in import file, fix invalid records and retry.",
    },
    "CM-504": {
        "zh": ".carry 文件校验和不匹配，文件可能已损坏。",
        "en": ".carry file checksum mismatch, file may be corrupted.",
        "hint_zh": "重新获取 .carry 文件，或从备份恢复。",
        "hint_en": "Re-obtain the .carry file or restore from backup.",
    },

    # ═══ CM-600 ~ CM-699: CLI / TUI / MCP Entry Points ═══════════
    "CM-601": {
        "zh": "未知命令或参数错误。",
        "en": "Unknown command or invalid arguments.",
        "hint_zh": "运行 'carrymem help' 查看所有可用命令和用法说明。",
        "hint_en": "Run 'carrymem help' for all available commands and usage.",
    },
    "CM-602": {
        "zh": "TUI 启动失败：终端不支持所需功能。",
        "en": "TUI launch failed: terminal lacks required capabilities.",
        "hint_zh": "安装 Textual 库：pip install textual",
        "hint_en": "Install Textual library: pip install textual",
    },
    "CM-603": {
        "zh": "MCP 服务器启动失败。",
        "en": "MCP server startup failed.",
        "hint_zh": "检查端口占用情况和 MCP 配置文件。运行 'carrymem setup-mcp' 重新配置。",
        "hint_en": "Check port usage and MCP config. Run 'carrymem setup-mcp' to reconfigure.",
    },
    "CM-604": {
        "zh": "CLI 命令执行超时。",
        "en": "CLI command execution timed out.",
        "hint_zh": "增加超时时间设置（CARRYMEM_REQUEST_TIMEOUT 环境变量）或减少数据量。",
        "hint_en": "Increase timeout (CARRYMEM_REQUEST_TIMEOUT env var) or reduce data volume.",
    },

    # ═══ Fallback ══════════════════════════════════════════════════
    "CM-999": {
        "zh": "发生未知错误。",
        "en": "An unknown error occurred.",
        "hint_zh": "请将此错误码报告给开发团队以便排查。",
        "hint_en": "Please report this error code to the development team for investigation.",
    },
}


def get_message(code: str, lang: str = "zh") -> str:
    """Get localized message for an error code.

    Args:
        code: Error code string like "CM-101".
        lang: Language code, "zh" (default) or "en".

    Returns:
        Localized message string, or fallback English message.
    """
    entry = ERROR_MESSAGES.get(code, {})
    return entry.get(lang, entry.get("en", f"[{code}] Unknown error"))


def get_hint(code: str, lang: str = "zh") -> str:
    """Get localized hint for an error code.

    Args:
        code: Error code string like "CM-101".
        lang: Language code, "zh" (default) or "en".

    Returns:
        Localized hint string, or empty string if not found.
    """
    entry = ERROR_MESSAGES.get(code, {})
    hint_key = f"hint_{lang}"
    return entry.get(hint_key, entry.get("hint_en", ""))


def all_error_codes() -> list:
    """Return sorted list of all registered error codes."""
    return sorted(ERROR_MESSAGES.keys())
