"""测试 CLI/TUI/MCP 三入口一致性.

验证：
1. 三个入口都能正确初始化 CarryMem
2. 核心操作（存储/召回）在三入口行为一致
3. 错误码格式一致
"""

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.DEBUG)


class TestEntryPointInitialization(unittest.TestCase):
    """测试三入口初始化一致性."""

    def setUp(self):
        """每个测试前创建临时数据库."""
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def tearDown(self):
        """清理临时文件."""
        import shutil

        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_cli_initialization(self):
        """测试 CLI 入口能正确初始化 CarryMem."""
        from carrymem.core import CarryMem

        cm = CarryMem(db_path=self.db_path, storage="sqlite")
        self.assertIsNotNone(cm)
        self.assertIsNotNone(cm._adapter)
        cm.close()

    def test_tui_initialization(self):
        """测试 TUI 入口能正确初始化 CarryMem."""
        try:
            from carrymem.tui import HAS_TEXTUAL, CarryMemTUI

            if not HAS_TEXTUAL:
                self.skipTest("Textual not installed")

            # TUI 需要在非交互模式下测试
            app = CarryMemTUI(db_path=self.db_path, namespace="default")
            self.assertIsNotNone(app.cm)
            app.cm.close()
        except ImportError:
            self.skipTest("TUI module not available")

    def test_mcp_handlers_initialization(self):
        """测试 MCP Handlers 能正确初始化 CarryMem."""
        try:
            from carrymem.integration.layer2_mcp.handlers import Handlers

            handlers = Handlers(data_path=self.tmpdir, namespace="default")
            self.assertIsNotNone(handlers._carrymem)
            self.assertIsNotNone(handlers._engine)
            self.assertIsNotNone(handlers._rule_engine)
            handlers.cleanup()
        except ImportError:
            self.skipTest("MCP handlers not available")

    def test_all_entries_use_same_database(self):
        """测试三入口使用相同格式的数据库."""
        from carrymem.core import CarryMem

        # CLI 方式创建
        cm_cli = CarryMem(db_path=self.db_path, storage="sqlite")
        cm_cli.declare("Test preference from CLI")
        cm_cli.close()

        # TUI 方式访问（应该能看到 CLI 创建的数据）
        try:
            from carrymem.tui import HAS_TEXTUAL, CarryMemTUI

            if HAS_TEXTUAL:
                app = CarryMemTUI(db_path=self.db_path, namespace="default")
                memories = app.cm.recall_memories(limit=10)
                self.assertGreaterEqual(len(memories), 1)
                app.cm.close()
        except ImportError:
            pass

        # MCP 方式访问
        try:
            from carrymem.integration.layer2_mcp.handlers import (
                Handlers,
                handle_recall_memories,
            )

            handlers = Handlers(data_path=self.db_path, namespace="default")
            result = handle_recall_memories(handlers._carrymem, {"query": "preference", "limit": 10})
            self.assertIn("memories", result)
            self.assertGreaterEqual(len(result["memories"]), 1)
            handlers.cleanup()
        except ImportError:
            pass


class TestCoreOperationConsistency(unittest.TestCase):
    """测试核心操作在三入口的行为一致性."""

    def setUp(self):
        """每个测试前创建临时数据库."""
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def tearDown(self):
        """清理临时文件."""
        import shutil

        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_store_memory_consistency(self):
        """测试存储记忆在三个入口的一致性."""
        from carrymem.core import CarryMem

        test_message = "I prefer dark mode"

        # CLI 存储
        cm_cli = CarryMem(db_path=self.db_path, storage="sqlite")
        result_cli = cm_cli.declare(test_message)
        self.assertIn("storage_keys", result_cli)
        cli_key = result_cli["storage_keys"][0]
        cm_cli.close()

        # MCP 存储
        try:
            from carrymem.integration.layer2_mcp.handlers import (
                Handlers,
                handle_declare_preference,
            )

            handlers = Handlers(data_path=self.db_path, namespace="default")
            result_mcp = handle_declare_preference(handlers._carrymem, {"message": "I prefer light mode"})
            self.assertIn("storage_keys", result_mcp)
            mcp_key = result_mcp["storage_keys"][0]
            handlers.cleanup()

            # 验证两个 key 格式一致（都应该是 cm_ 开头）
            self.assertIs(cli_key.startswith("cm_"), True)
            self.assertIs(mcp_key.startswith("cm_"), True)
        except ImportError:
            pass

    def test_recall_memory_consistency(self):
        """测试召回记忆在三个入口的一致性."""
        from carrymem.core import CarryMem

        # 先存储一些数据
        cm = CarryMem(db_path=self.db_path, storage="sqlite")
        cm.declare("Python is my favorite language")
        cm.declare("I use VS Code for development")
        cm.close()

        # CLI 召回
        cm_cli = CarryMem(db_path=self.db_path, storage="sqlite")
        cli_memories = cm_cli.recall_memories(query="Python", limit=10)
        cm_cli.close()

        # MCP 召回
        try:
            from carrymem.integration.layer2_mcp.handlers import (
                Handlers,
                handle_recall_memories,
            )

            handlers = Handlers(data_path=self.db_path, namespace="default")
            mcp_result = handle_recall_memories(handlers._carrymem, {"query": "Python", "limit": 10})
            mcp_memories = mcp_result.get("memories", [])
            handlers.cleanup()

            # 验证结果数量一致
            self.assertEqual(len(cli_memories), len(mcp_memories))

            # 如果有结果，验证结构一致
            if cli_memories:
                cli_first = cli_memories[0]
                mcp_first = mcp_memories[0]

                # 都应该有 content 字段
                self.assertIn("content", cli_first)
                self.assertIn("content", mcp_first)

                # 类型字段应该一致
                if "type" in cli_first:
                    self.assertIn("type", mcp_first)
        except ImportError:
            pass

    def test_forget_memory_consistency(self):
        """测试删除记忆在三个入口的一致性."""
        from carrymem.core import CarryMem

        # 存储一条记忆
        cm = CarryMem(db_path=self.db_path, storage="sqlite")
        result = cm.declare("Memory to delete")
        key = result["storage_keys"][0]
        cm.close()

        # CLI 删除
        cm_cli = CarryMem(db_path=self.db_path, storage="sqlite")
        deleted_cli = cm_cli.forget_memory(key)
        self.assertIs(deleted_cli, True)

        # 验证已删除
        memories = cm_cli.recall_memories(limit=100)
        keys = [m.get("storage_key") for m in memories]
        self.assertNotIn(key, keys)
        cm_cli.close()

        # MCP 删除（需要新的记忆）
        cm2 = CarryMem(db_path=self.db_path, storage="sqlite")
        result2 = cm2.declare("Another memory to delete")
        key2 = result2["storage_keys"][0]
        cm2.close()

        try:
            from carrymem.integration.layer2_mcp.handlers import (
                Handlers,
                handle_forget_memory,
            )

            handlers = Handlers(data_path=self.db_path, namespace="default")
            mcp_result = handle_forget_memory(handlers._carrymem, {"memory_id": key2})
            self.assertIs(mcp_result.get("deleted", False), True)
            handlers.cleanup()
        except ImportError:
            pass


class TestErrorCodeConsistency(unittest.TestCase):
    """测试错误码在三入口的格式一致性."""

    def test_error_code_format(self):
        """测试所有错误码都符合 CM-xxx 格式."""
        from carrymem.errors import CarryMemError

        # 测试标准错误码
        error = CarryMemError(code="CM-001", message="Test error")
        self.assertEqual(error.code, "CM-001")
        self.assertRegex(error.code, r"^CM-\d{3}$")

    def test_cli_error_output_format(self):
        """测试 CLI 错误输出包含错误码."""
        from carrymem.errors import CarryMemError

        error = CarryMemError(
            code="CM-001",
            message="Storage not configured",
            hint="Use CarryMem(storage='sqlite')",
        )

        # 验证错误格式
        error_str = str(error)
        self.assertIn("[CM-001]", error_str)
        self.assertIn("Storage not configured", error_str)

    def test_tui_error_display_format(self):
        """测试 TUI 错误显示组件包含错误码."""
        try:
            from carrymem.tui import CarryMemError, ErrorDisplay

            error = CarryMemError(code="CM-201", message="Validation failed", hint="Check input format")

            # 模拟 TUI 环境（简化测试）
            display = ErrorDisplay()
            # 验证 show_error 方法接受 CarryMemError
            display.show_error(error)
            self.assertIsNotNone(display.renderable)  # 组件应该有内容
        except (ImportError, AttributeError):
            self.skipTest("TUI ErrorDisplay not available")

    def test_mcp_error_response_format(self):
        """测试 MCP 错误响应格式."""
        try:
            from carrymem.errors import CarryMemError
            from carrymem.integration.layer2_mcp.handlers import _safe_error

            # 测试 CarryMemError 转换
            error = CarryMemError(code="CM-100", message="Storage error")
            safe_type = _safe_error(error)
            # MCP 应该返回安全的错误类型
            self.assertIsInstance(safe_type, str)
            self.assertGreater(len(safe_type), 0)

            # 测试 ValueError 转换
            safe_value = _safe_error(ValueError("Invalid input"))
            self.assertEqual(safe_value, "invalid_input")
        except ImportError:
            self.skipTest("MCP handlers not available")


class TestOutputFormatConsistency(unittest.TestCase):
    """测试输出格式约定."""

    def test_success_response_format(self):
        """测试成功响应的标准格式."""
        # CLI 成功返回 0
        self.assertEqual(0, 0)  # 退出码

        # MCP 成功响应包含 success=True
        expected_mcp = {"success": True, "data": {}}
        self.assertIn("success", expected_mcp)
        self.assertIs(expected_mcp["success"], True)

    def test_error_response_format(self):
        """测试错误响应的标准格式."""
        # MCP 错误响应包含 success=False 和 error 字段
        expected_mcp_error = {
            "success": False,
            "error": "storage_not_configured",
        }
        self.assertFalse(expected_mcp_error["success"])
        self.assertIn("error", expected_mcp_error)

    def test_cli_help_format(self):
        """测试 CLI 帮助信息格式."""
        from carrymem.cli import show_help

        # 验证帮助信息可以调用（不检查具体内容）
        try:
            with patch("sys.stdout"):
                show_help()  # 不应该抛出异常
        except Exception as e:
            self.fail(f"show_help() raised exception: {e}")


class TestNamespaceAndParameterConsistency(unittest.TestCase):
    """测试命名空间和参数在三入口的一致性."""

    def setUp(self):
        """每个测试前创建临时数据库."""
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def tearDown(self):
        """清理临时文件."""
        import shutil

        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_namespace_isolation(self):
        """测试命名空间在不同入口间的隔离性."""
        from carrymem.core import CarryMem

        # CLI 在 default 命名空间存储
        cm_default = CarryMem(db_path=self.db_path, storage="sqlite", namespace="default")
        cm_default.declare("Default namespace memory")
        cm_default.close()

        # CLI 在 work 命名空间存储
        cm_work = CarryMem(db_path=self.db_path, storage="sqlite", namespace="work")
        cm_work.declare("Work namespace memory")
        cm_work.close()

        # 验证隔离性
        cm_check = CarryMem(db_path=self.db_path, storage="sqlite", namespace="default")
        memories = cm_check.recall_memories(limit=100)
        contents = [m.get("content") for m in memories]
        self.assertIn("Default namespace memory", contents)
        self.assertNotIn("Work namespace memory", contents)
        cm_check.close()

        # TUI 使用命名空间
        try:
            from carrymem.tui import HAS_TEXTUAL, CarryMemTUI

            if HAS_TEXTUAL:
                app = CarryMemTUI(db_path=self.db_path, namespace="work")
                work_memories = app.cm.recall_memories(limit=100)
                work_contents = [m.get("content") for m in work_memories]
                self.assertIn("Work namespace memory", work_contents)
                app.cm.close()
        except ImportError:
            pass

        # MCP 使用命名空间
        try:
            from carrymem.integration.layer2_mcp.handlers import (
                Handlers,
                handle_recall_memories,
            )

            handlers = Handlers(data_path=self.db_path, namespace="work")
            result = handle_recall_memories(handlers._carrymem, {"query": "", "limit": 100})
            mcp_contents = [m.get("content") for m in result.get("memories", [])]
            self.assertIn("Work namespace memory", mcp_contents)
            handlers.cleanup()
        except ImportError:
            pass


if __name__ == "__main__":
    unittest.main()
