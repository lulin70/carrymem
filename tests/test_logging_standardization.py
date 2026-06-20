"""测试日志规范统一.

验证：
1. JSON 日志格式正确
2. 日志级别过滤有效
3. 无残留 print()（在非测试代码中）
4. 所有 core 模块都有 logger
5. 日志配置环境变量支持
"""

import json
import logging
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from carrymem.utils.logging_config import (
    ENV_LOG_JSON,
    ENV_LOG_LEVEL,
    JSONFormatter,
    get_logger,
    reset_logging,
    setup_logging,
)


class TestJSONLogFormat(unittest.TestCase):
    """测试 JSON 日志格式."""

    def setUp(self):
        """每个测试前重置日志配置."""
        reset_logging()

    def tearDown(self):
        """每个测试后清理."""
        reset_logging()

    def test_json_formatter_output_is_valid_json(self):
        """测试 JSON 格式化器输出有效的 JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=None,
            exc_info=None,
        )

        output = formatter.format(record)
        # 验证可以解析为 JSON
        data = json.loads(output)
        self.assertIsInstance(data, dict)

    def test_json_formatter_contains_required_fields(self):
        """测试 JSON 格式化器包含必需字段."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="carrymem.core._lifecycle",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Initializing CarryMem",
            args=None,
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # 必需字段
        self.assertIn("timestamp", data)
        self.assertIn("level", data)
        self.assertIn("logger", data)
        self.assertIn("message", data)

        # 字段值
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "carrymem.core._lifecycle")
        self.assertEqual(data["message"], "Initializing CarryMem")

    def test_json_formatter_handles_exception(self):
        """测试 JSON 格式化器处理异常信息."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=None,
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        self.assertIn("exception", data)
        self.assertIn("ValueError", data["exception"])
        self.assertIn("Test error", data["exception"])

    def test_json_formatter_iso_timestamp(self):
        """测试时间戳是 ISO 格式."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=None,
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # ISO 格式应该包含 T
        self.assertIn("T", data["timestamp"])


class TestLogLevelFiltering(unittest.TestCase):
    """测试日志级别过滤."""

    def setUp(self):
        """每个测试前重置日志配置."""
        reset_logging()

    def tearDown(self):
        """每个测试后清理."""
        reset_logging()

    def test_debug_level_shows_all(self):
        """测试 DEBUG 级别显示所有日志."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            setup_logging(level=logging.DEBUG, console_output=True)
            logger = get_logger("carrymem.test.debug")

            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            output = mock_stderr.getvalue()
            self.assertIn("Debug message", output)
            self.assertIn("Info message", output)
            self.assertIn("Warning message", output)
            self.assertIn("Error message", output)

    def test_info_level_filters_debug(self):
        """测试 INFO 级别过滤 DEBUG 日志."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            setup_logging(level=logging.INFO, console_output=True)
            logger = get_logger("carrymem.test.info")

            logger.debug("Debug message")  # 不应该出现
            logger.info("Info message")  # 应该出现

            output = mock_stderr.getvalue()
            self.assertNotIn("Debug message", output)
            self.assertIn("Info message", output)

    def test_warning_level_filters_info_and_debug(self):
        """测试 WARNING 级别过滤 INFO 和 DEBUG 日志."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            setup_logging(level=logging.WARNING, console_output=True)
            logger = get_logger("carrymem.test.warning")

            logger.debug("Debug message")  # 不应该出现
            logger.info("Info message")  # 不应该出现
            logger.warning("Warning message")  # 应该出现

            output = mock_stderr.getvalue()
            self.assertNotIn("Debug message", output)
            self.assertNotIn("Info message", output)
            self.assertIn("Warning message", output)

    def test_error_level_only_errors(self):
        """测试 ERROR 级别只显示错误及以上."""
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            setup_logging(level=logging.ERROR, console_output=True)
            logger = get_logger("carrymem.test.error")

            logger.debug("Debug")  # 不应该出现
            logger.info("Info")  # 不应该出现
            logger.warning("Warning")  # 不应该出现
            logger.error("Error")  # 应该出现

            output = mock_stderr.getvalue()
            self.assertNotIn("Debug", output)
            self.assertNotIn("Info", output)
            self.assertNotIn("Warning", output)
            self.assertIn("Error", output)


class TestEnvironmentVariableSupport(unittest.TestCase):
    """测试环境变量支持."""

    def setUp(self):
        """保存原始环境变量."""
        self.original_env = {}
        for env_key in [ENV_LOG_JSON, ENV_LOG_LEVEL]:
            self.original_env[env_key] = os.environ.get(env_key)
            if env_key in os.environ:
                del os.environ[env_key]

    def tearDown(self):
        """恢复原始环境变量."""
        for env_key, value in self.original_env.items():
            if value is not None:
                os.environ[env_key] = value
            elif env_key in os.environ:
                del os.environ[env_key]
        reset_logging()

    def test_log_level_env_var(self):
        """测试 CARRYMEM_LOG_LEVEL 环境变量."""
        os.environ[ENV_LOG_LEVEL] = "WARNING"

        # 重新导入以获取新的环境变量值
        from carrymem.utils.logging_config import _get_log_level

        level = _get_log_level()
        self.assertEqual(level, logging.WARNING)

    def test_log_json_env_var_true(self):
        """测试 CARRYMEM_LOG_JSON=1 启用 JSON 模式."""
        os.environ[ENV_LOG_JSON] = "1"

        from carrymem.utils.logging_config import _should_use_json

        self.assertTrue(_should_use_json())

    def test_log_json_env_var_false(self):
        """测试未设置 CARRYMEM_LOG_JSON 时不启用 JSON 模式."""
        # 确保没有设置
        if ENV_LOG_JSON in os.environ:
            del os.environ[ENV_LOG_JSON]

        from carrymem.utils.logging_config import _should_use_json

        self.assertFalse(_should_use_json())


class TestCoreModuleLoggers(unittest.TestCase):
    """测试所有 core 模块都有 logger."""

    def test_lifecycle_module_has_logger(self):
        """测试 _lifecycle 模块有 logger."""
        from carrymem.core import _lifecycle

        self.assertTrue(hasattr(_lifecycle, "logger"))
        self.assertIsInstance(_lifecycle.logger, logging.Logger)

    def test_memory_crud_module_has_logger(self):
        """测试 _memory_crud 模块有 logger."""
        from carrymem.core import _memory_crud

        self.assertTrue(hasattr(_memory_crud, "logger"))
        self.assertIsInstance(_memory_crud.logger, logging.Logger)

    def test_classification_module_has_logger(self):
        """测试 _classification 模块有 logger."""
        from carrymem.core import _classification

        self.assertTrue(hasattr(_classification, "logger"))
        self.assertIsInstance(_classification.logger, logging.Logger)

    def test_recall_module_has_logger(self):
        """测试 _recall 模块有 logger."""
        from carrymem.core import _recall

        self.assertTrue(hasattr(_recall, "logger"))
        self.assertIsInstance(_recall.logger, logging.Logger)

    def test_backup_module_has_logger(self):
        """测试 _backup 模块有 logger."""
        from carrymem.core import _backup

        self.assertTrue(hasattr(_backup, "logger"))
        self.assertIsInstance(_backup.logger, logging.Logger)

    def test_maintenance_module_has_logger(self):
        """测试 _maintenance 模块有 logger."""
        from carrymem.core import _maintenance

        self.assertTrue(hasattr(_maintenance, "logger"))
        self.assertIsInstance(_maintenance.logger, logging.Logger)

    def test_profile_export_module_has_logger(self):
        """测试 _profile_export 模块有 logger."""
        from carrymem.core import _profile_export

        self.assertTrue(hasattr(_profile_export, "logger"))
        self.assertIsInstance(_profile_export.logger, logging.Logger)

    def test_prompt_delegate_module_has_logger(self):
        """测试 _prompt_delegate 模块有 logger."""
        from carrymem.core import _prompt_delegate

        self.assertTrue(hasattr(_prompt_delegate, "logger"))
        self.assertIsInstance(_prompt_delegate.logger, logging.Logger)


class TestNoResidualPrintStatements(unittest.TestCase):
    """测试非测试代码中无残留的 print() 调用."""

    def test_no_print_in_core_modules(self):
        """测试 core/ 目录下没有 print() 调用."""
        import ast

        core_dir = Path(__file__).parent.parent / "src" / "carrymem" / "core"
        violations = []

        for py_file in core_dir.glob("_*.py"):
            if py_file.name.startswith("test_"):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id == "print":
                            violations.append(f"{py_file}:{node.lineno}")
            except SyntaxError:
                pass  # 跳过语法错误的文件

        self.assertEqual(
            len(violations),
            0,
            f"Found print() statements in core modules: {violations}",
        )

    def test_no_print_in_rules_matcher(self):
        """测试 rules/matcher.py 没有 print() 调用（文档示例除外）."""
        matcher_file = Path(__file__).parent.parent / "src" / "carrymem" / "rules" / "matcher.py"

        if matcher_file.exists():
            source = matcher_file.read_text(encoding="utf-8")
            # 排除注释和文档字符串中的 print
            lines = source.split("\n")
            violations = []
            in_docstring = False

            for i, line in enumerate(lines, 1):
                # 跳过文档字符串
                if '"""' in line or "'''" in line:
                    in_docstring = not in_docstring
                    continue

                if in_docstring or line.strip().startswith("#"):
                    continue

                # 检查实际的 print 调用
                if "print(" in line and not line.strip().startswith("#"):
                    violations.append(f"Line {i}: {line.strip()}")

            self.assertEqual(
                len(violations),
                0,
                f"Found print() in rules/matcher.py: {violations}",
            )

    def test_no_print_in_http_server(self):
        """测试 http_server.py 没有 print() 调用."""
        http_file = Path(__file__).parent.parent / "src" / "carrymem" / "integration" / "layer2_mcp" / "http_server.py"

        if http_file.exists():
            source = http_file.read_text(encoding="utf-8")
            lines = source.split("\n")
            violations = []

            for i, line in enumerate(lines, 1):
                if "print(" in line and not line.strip().startswith("#"):
                    violations.append(f"Line {i}: {line.strip()}")

            self.assertEqual(
                len(violations),
                0,
                f"Found print() in http_server.py: {violations}",
            )


class TestLogFileRotation(unittest.TestCase):
    """测试日志文件轮转功能."""

    def setUp(self):
        """创建临时目录."""
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        """清理临时目录."""
        import shutil

        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)
        reset_logging()

    def test_log_file_creation(self):
        """测试日志文件创建."""
        log_file = os.path.join(self.tmpdir, "test.log")

        setup_logging(log_file=log_file, console_output=False)
        logger = get_logger("carrymem.test.file")
        logger.info("Test log message")

        # 强制刷新 handler
        root = logging.getLogger("carrymem")
        for handler in root.handlers:
            handler.flush()

        self.assertTrue(os.path.exists(log_file))

        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Test log message", content)

    def test_log_format_in_file(self):
        """测试文件中的日志格式符合规范."""
        log_file = os.path.join(self.tmpdir, "format_test.log")

        setup_logging(level=logging.INFO, log_file=log_file, console_output=False)
        logger = get_logger("carrymem.test.format")
        logger.info("Formatted message")

        # 刷新
        root = logging.getLogger("carrymem")
        for handler in root.handlers:
            handler.flush()

        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 标准格式: timestamp [LEVEL] name: message
            self.assertIn("[INFO]", content)
            self.assertIn("test.format:", content)
            self.assertIn("Formatted message", content)


class TestGetLoggerFunction(unittest.TestCase):
    """测试 get_logger 函数."""

    def setUp(self):
        reset_logging()

    def tearDown(self):
        reset_logging()

    def test_get_logger_returns_logger_instance(self):
        """测试 get_logger 返回 Logger 实例."""
        logger = get_logger("test.module")
        self.assertIsInstance(logger, logging.Logger)

    def test_get_logger_name_matches(self):
        """测试 logger 名称匹配传入的名称."""
        logger = get_logger("my.custom.module")
        self.assertEqual(logger.name, "my.custom.module")

    def test_get_logger_with_dunder_name(self):
        """测试使用 __name__ 作为参数."""
        logger = get_logger(__name__)
        self.assertEqual(logger.name, __name__)

    def test_multiple_calls_return_same_logger(self):
        """测试多次调用返回相同的 logger 实例."""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        self.assertIs(logger1, logger2)


if __name__ == "__main__":
    unittest.main()
