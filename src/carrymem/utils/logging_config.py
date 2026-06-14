"""CarryMem 统一日志配置模块.

提供标准化的日志配置，支持：
- 统一格式: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- JSON 格式输出 (通过环境变量 CARRYMEM_LOG_JSON=1)
- 日志级别控制 (通过环境变量 CARRYMEM_LOG_LEVEL)
- 文件日志轮转 (当启用文件日志时)

使用方式:
    from carrymem.utils.logging_config import setup_logging, get_logger

    # 在模块顶部初始化
    setup_logging()

    # 获取 logger
    logger = get_logger(__name__)
"""

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# ── 环境变量常量 ────────────────────────────────────────────────

ENV_LOG_JSON = "CARRYMEM_LOG_JSON"
ENV_LOG_LEVEL = "CARRYMEM_LOG_LEVEL"
ENV_LOG_FILE = "CARRYMEM_LOG_FILE"
ENV_LOG_MAX_BYTES = "CARRYMEM_LOG_MAX_BYTES"
ENV_LOG_BACKUP_COUNT = "CARRYMEM_LOG_BACKUP_COUNT"

# 默认值
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_LOG_DIR = "logs"


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器.

    输出格式:
        {
            "timestamp": "2026-06-11T10:30:00",
            "level": "INFO",
            "logger": "carrymem.core._lifecycle",
            "message": "Initializing CarryMem...",
            "extra": {}
        }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if record.args:
            log_data["extra"] = record.args

        return json.dumps(log_data, ensure_ascii=False)


def _get_log_level() -> int:
    """从环境变量获取日志级别.

    Returns:
        logging level 常量 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level_str = os.environ.get(ENV_LOG_LEVEL, "").upper()

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,
    }

    return level_map.get(level_str, DEFAULT_LOG_LEVEL)


def _should_use_json() -> bool:
    """检查是否启用 JSON 日志格式.

    Returns:
        True 如果 CARRYMEM_LOG_JSON=1 或 true
    """
    json_env = os.environ.get(ENV_LOG_JSON, "").lower()
    return json_env in ("1", "true", "yes", "on")


def _get_log_file_path() -> Optional[Path]:
    """获取日志文件路径.

    Returns:
        Path 对象或 None（如果不启用文件日志）
    """
    log_file = os.environ.get(ENV_LOG_FILE)
    if log_file:
        return Path(log_file)

    # 默认不自动创建文件日志，除非显式指定
    return None


def _get_max_bytes() -> int:
    """获取文件轮转最大字节数.

    Returns:
        最大字节数（默认 10MB）
    """
    try:
        max_bytes = int(os.environ.get(ENV_LOG_MAX_BYTES, DEFAULT_MAX_BYTES))
        return max(1024 * 1024, max_bytes)  # 最小 1 MB
    except ValueError:
        return DEFAULT_MAX_BYTES


def _get_backup_count() -> int:
    """获取备份文件数量.

    Returns:
        备份文件数（默认 5）
    """
    try:
        count = int(os.environ.get(ENV_LOG_BACKUP_COUNT, DEFAULT_BACKUP_COUNT))
        return max(1, min(count, 20))  # 限制在 1-20 范围
    except ValueError:
        return DEFAULT_BACKUP_COUNT


def setup_logging(
    level: Optional[int] = None,
    use_json: Optional[bool] = None,
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> None:
    """配置 CarryMem 统一日志系统.

    Args:
        level: 日志级别（覆盖环境变量）
        use_json: 是否使用 JSON 格式（覆盖环境变量）
        log_file: 日志文件路径（覆盖环境变量）
        console_output: 是否输出到控制台（默认 True）

    Example:
        >>> # 使用默认配置
        >>> setup_logging()

        >>> # 自定义配置
        >>> setup_logging(level=logging.DEBUG, use_json=True)

        >>> # 仅输出到文件
        >>> setup_logging(log_file="app.log", console_output=False)
    """
    # 获取配置（参数 > 环境变量 > 默认值）
    log_level = level or _get_log_level()
    json_mode = _should_use_json() if use_json is None else use_json

    file_path = Path(log_file) if log_file else _get_log_file_path()

    # 根式器选择
    formatter = JSONFormatter() if json_mode else logging.Formatter(
        fmt=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
    )

    # 配置 root logger
    root_logger = logging.getLogger("carrymem")
    root_logger.setLevel(log_level)

    # 避免重复添加 handler
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 控制台输出
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 文件输出（带轮转）
    if file_path:
        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                filename=str(file_path),
                maxBytes=_get_max_bytes(),
                backupCount=_get_backup_count(),
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError as e:
            root_logger.warning("无法创建日志文件 %s: %s", file_path, e)

    # 防止 propagate 到 Python root logger（避免重复输出）
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """获取标准化的 logger 实例.

    Args:
        name: 通常传入 __name__

    Returns:
        logging.Logger 实例

    Example:
        >>> from carrymem.utils.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Hello from %s", name)
    """
    return logging.getLogger(name)


def reset_logging() -> None:
    """重置日志配置（主要用于测试）."""
    root_logger = logging.getLogger("carrymem")
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)


# 模块级便捷导出
__all__ = [
    "setup_logging",
    "get_logger",
    "reset_logging",
    "JSONFormatter",
    "ENV_LOG_JSON",
    "ENV_LOG_LEVEL",
    "ENV_LOG_FILE",
]
