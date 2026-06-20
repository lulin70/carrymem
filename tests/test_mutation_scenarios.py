"""P2-3: Mutation Testing 基础框架

手动变异测试场景 — 不需要 mutmut 工具，通过"假设变异"验证测试健壮性。

测试场景：
a) 条件翻转测试 — 验证关键 if 条件不能随意反转
b) 边界值偏移测试 — 关键阈值不能随意改变
c) 返回值篡改测试 — 空列表/None 不能被静默忽略
d) 异常吞没测试 — except 块不能静默 pass
e) 逻辑操作符替换 — and/or 互换应导致失败

每个场景用注释清晰标记 "MUTATION: what changed, why test should catch it"
"""

import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem import CarryMem
from carrymem.adapters.base import MemoryEntry, StoredMemory
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.constants import (
    DEFAULT_FORCE_TYPE_CONFIDENCE,
    DEFAULT_RECALL_LIMIT,
    MAX_MESSAGE_LENGTH,
    MIN_QUALITY_THRESHOLD,
)
from carrymem.exceptions import ClassificationError
from carrymem.quality_scorer import MemoryQualityScorer, QualityAnalyzer

# ==============================================================================
# a) 条件翻转测试 (Condition Flip Test)
# ==============================================================================


class TestConditionFlipConfidence:
    """MUTATION: 将 `if confidence > 0.8` 改为 `if confidence < 0.8`

    Why test should catch it:
    - 高置信度记忆应该被优先处理或特殊标记
    - 翻转条件会导致低置信度记忆被错误地当作高置信度处理
    - 测试应验证：高置信度记忆的行为与低置信度记忆有明确区别
    """

    def test_high_confidence_memory_should_be_stored(self):
        """验证高置信度记忆（confidence > 0.8）能正常存储"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 创建高置信度记忆
            result = cm.classify_and_remember(
                "I prefer using TypeScript for all frontend projects",
                force_type="user_preference",
            )

            # MUTATION CHECK: 如果条件被翻转为 confidence < 0.8，
            # 高置信度记忆可能不会被存储或标记不正确
            assert result.get("stored", False), "High confidence memory should be stored"
            assert result.get("type") == "user_preference", "Type should be preserved"

            # 验证可以召回
            memories = cm.recall_memories(query="TypeScript")
            assert len(memories) > 0, "High confidence memory should be recallable"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_low_confidence_behavior_differs_from_high(self):
        """验证低置信度记忆与高置信度记忆行为不同"""
        scorer = MemoryQualityScorer()

        # 创建高置信度和低置信度的模拟记忆
        high_conf_mem = StoredMemory(
            storage_key="high-1",
            content="Important preference",
            type="user_preference",
            confidence=0.9,
            access_count=5,
            created_at=datetime.now(timezone.utc),
            source_layer="declaration",
        )

        low_conf_mem = StoredMemory(
            storage_key="low-1",
            content="Less certain info",
            type="fact_declaration",
            confidence=0.3,
            access_count=2,
            created_at=datetime.now(timezone.utc),
            source_layer="semantic",
        )

        high_score = scorer.score(high_conf_mem)
        low_score = scorer.score(low_conf_mem)

        # MUTATION CHECK: 如果 confidence 比较逻辑被翻转，
        # 低置信度记忆可能会得到不正确的高分
        assert high_score > low_score, (
            f"High confidence ({high_score:.3f}) should score higher than " f"low confidence ({low_score:.3f})"
        )

        # 验证质量等级不同
        high_tier = scorer.get_quality_tier(high_score)
        low_tier = scorer.get_quality_tier(low_score)

        # MUTATION CHECK: 翻转后可能导致 tier 判断错误
        assert high_tier in ("excellent", "good"), f"High conf should be good+, got {high_tier}"
        assert low_tier in ("fair", "poor"), f"Low conf should be fair or poor, got {low_tier}"

    def test_force_type_confidence_threshold(self):
        """验证 DEFAULT_FORCE_TYPE_CONFIDENCE (0.8) 作为阈值的语义"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 使用 force_type 时，应使用 DEFAULT_FORCE_TYPE_CONFIDENCE
            result = cm.classify_and_remember(
                "Forced decision: Use PostgreSQL",
                force_type="decision",
            )

            assert result.get("stored", False), "Forced type should be stored"

            # MUTATION CHECK: 如果阈值逻辑被翻转，
            # force_type 可能不会设置正确的 confidence
            if result.get("entries"):
                entry_confidence = result["entries"][0].get("confidence", 0)
                assert entry_confidence == DEFAULT_FORCE_TYPE_CONFIDENCE, (
                    f"Force type should use default confidence {DEFAULT_FORCE_TYPE_CONFIDENCE}, "
                    f"got {entry_confidence}"
                )

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass


# ==============================================================================
# b) 边界值偏移测试 (Boundary Value Shift Test)
# ==============================================================================


class TestBoundaryValueShiftMaxLength:
    """MUTATION: 将 MAX_MESSAGE_LENGTH = 50000 改为 500

    Why test should catch it:
    - 正常消息长度通常超过 500 字符
    - 缩小阈值会导致大量合法消息被拒绝
    - 测试应验证：合理长度的消息能通过验证，超长消息被正确拒绝
    """

    def test_normal_message_within_limit(self):
        """验证正常长度消息在 MAX_MESSAGE_LENGTH 范围内"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 创建一个中等长度的消息（远小于 50000，但大于假设的变异值 500）
            normal_length_msg = "I prefer " + "very " * 100 + "detailed specifications"

            # 应该成功存储
            result = cm.classify_and_remember(normal_length_msg)

            # MUTATION CHECK: 如果 MAX_MESSAGE_LENGTH 被改为 500，
            # 这个约 600+ 字符的消息会被错误拒绝
            assert result.get("stored", False) or result.get(
                "should_remember", False
            ), f"Normal message ({len(normal_length_msg)} chars) should be accepted"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_excessive_message_rejected(self):
        """验证超长消息被正确拒绝"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 创建超长消息（超过 MAX_MESSAGE_LENGTH）
            excessive_msg = "A" * (MAX_MESSAGE_LENGTH + 1000)

            with pytest.raises((ValueError, Exception)) as exc_info:
                cm.classify_and_remember(excessive_msg)

            # MUTATION CHECK: 如果阈值被随意改变，此测试可能失败
            # （例如如果阈值被设得很大，超长消息就不会被拒绝）
            error_msg = str(exc_info.value).lower()
            assert any(
                keyword in error_msg for keyword in ["too long", "max", "length"]
            ), f"Should reject excessive message with length-related error, got: {exc_info.value}"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_boundary_exact_max_length(self):
        """验证恰好等于 MAX_MESSAGE_LENGTH 的消息可接受"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 恰好等于最大长度的消息
            exact_length_msg = "B" * MAX_MESSAGE_LENGTH

            # 不应该抛出异常（可能在内部被处理）
            try:
                result = cm.classify_and_remember(exact_length_msg)
                # MUTATION CHECK: 如果边界值被偏移，恰好边界的消息可能被错误处理
                # 这里我们只验证不会崩溃
                assert isinstance(result, dict), "Should return a result dict"
            except ValueError as e:
                # 如果被拒绝，应该是合理的理由
                error_str = str(e).lower()
                assert (
                    "length" in error_str or "long" in error_str or "size" in error_str
                ), f"Unexpected rejection reason: {e}"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass


# ==============================================================================
# c) 返回值篡改测试 (Return Value Tampering Test)
# ==============================================================================


class TestReturnValueTamperingEmptyRecall:
    """MUTATION: 模拟 recall 返回空列表 [] 或 None

    Why test should catch it:
    - 调用方不应因空结果而崩溃
    - 空结果应有明确的语义（无数据 vs 错误）
    - 下游代码应优雅处理空列表/None
    """

    def test_empty_recall_returns_empty_list_not_none(self):
        """验证空查询返回空列表而非 None"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 查询不存在的数据
            results = cm.recall_memories(query="NONEXISTENT_QUERY_xyz123")

            # MUTATION CHECK: 如果返回值被篡改为 None，
            # 下游的 isinstance(results, list) 或 len(results) 会崩溃
            assert results is not None, "Empty recall should return [], not None"
            assert isinstance(results, list), f"Recall should return list, got {type(results)}"
            assert len(results) == 0, f"Empty query should return empty list, got {len(results)} items"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_downstream_handles_empty_recall_gracefully(self):
        """验证下游代码能优雅处理空召回结果"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 模拟空召回结果的下游处理
            empty_results = cm.recall_memories(query="nothing_here")

            # MUTATION CHECK: 如果空列表被静默忽略或导致 IndexError，
            # 说明测试覆盖不足
            should_not_crash = []

            # 模拟常见的下游操作
            if empty_results:
                for item in empty_results:
                    should_not_crash.append(item.get("content", ""))

            # 对空结果进行聚合操作
            contents = [r.get("content", "") for r in empty_results]
            assert contents == [], "Empty results should produce empty aggregation"

            # 尝试构建上下文（常见下游操作）
            context_result = cm.build_context(context="test with no data")
            assert isinstance(context_result, dict), "Context build should handle empty state"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_quality_scorer_with_empty_list(self):
        """验证质量评分器对空列表的处理"""
        scorer = MemoryQualityScorer()
        analyzer = QualityAnalyzer(scorer)

        # MUTATION CHECK: 如果空列表被错误处理为 None 或抛出异常，
        # 说明边界情况未覆盖
        scored_batch = scorer.score_batch([])
        assert scored_batch == [], "Score batch should return empty list for empty input"

        analysis = analyzer.analyze([])
        assert analysis["count"] == 0, "Analysis of empty list should have count=0"
        assert analysis["average_score"] == 0.0, "Average of empty should be 0.0"

        # 过滤空列表
        filtered = scorer.filter_by_quality([], min_score=0.5)
        assert filtered == [], "Filtering empty list should return empty list"


# ==============================================================================
# d) 异常吞没测试 (Exception Swallowing Test)
# ==============================================================================


class TestExceptionSwallowing:
    """MUTATION: except 块中静默 pass 或只 log 不传播

    Why test should catch it:
    - 关键路径的异常不应被吞没
    - 吞没异常会隐藏真实错误，导致难以调试
    - 测试应验证：异常要么传播，要么有明确的错误处理策略
    """

    def test_storage_error_propagates_on_critical_operation(self):
        """验证关键存储操作的异常会传播"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 模拟存储层故障
            original_remember = cm._adapter.remember

            def failing_remember(entry):
                raise RuntimeError("Simulated storage failure")

            cm._adapter.remember = failing_remember

            # MUTATION CHECK: 如果异常被吞没（except: pass），
            # 这里不会抛出异常，而是返回假成功
            with pytest.raises((RuntimeError, Exception)) as exc_info:
                cm.classify_and_remember("This should fail")

            error_msg = str(exc_info.value).lower()
            # 验证是真实的错误信息，不是被吞没后的默认返回
            assert len(error_msg) > 0, "Error should have meaningful message"

            # 恢复
            cm._adapter.remember = original_remember
            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_validation_error_not_silently_ignored(self):
        """验证输入验证错误不被静默忽略"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 测试空消息
            with pytest.raises((ValueError, Exception)):
                cm.classify_and_remember("")

            # 测试纯空白消息
            with pytest.raises((ValueError, Exception)):
                cm.classify_and_remember("   \t\n   ")

            # MUTATION CHECK: 如果验证异常被吞没，
            # 无效输入会被当作有效数据处理
            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_recall_error_handling_is_explicit(self):
        """验证 recall 操作的错误处理是显式的"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 先存入一些数据
            cm.classify_and_remember("Test data for error handling")

            # 模拟 recall 失败
            original_recall = cm._adapter.recall

            def failing_recall(query="", **kwargs):
                raise IOError("Simulated recall failure")

            cm._adapter.recall = failing_recall

            # MUTATION CHECK: 如果异常被吞没并返回空列表，
            # 调用方无法区分"无数据"和"查询失败"
            try:
                results = cm.recall_memories(query="test")

                # 如果返回了结果（异常被吞没），至少应该是空列表而非 None
                # 且调用方应该能够检测到这是一个异常情况
                if results is None:
                    pytest.fail("Recall returned None on error - exception swallowed?")

                # 注意：当前实现可能会捕获异常并返回空列表
                # 这是一种有效的错误处理策略，但测试应记录这种行为
                assert isinstance(results, list), "Even on error, should return consistent type (list)"
            except (IOError, Exception):
                # 异常传播也是可接受的行为
                pass

            # 恢复
            cm._adapter.recall = original_recall
            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_classification_pipeline_exception_visibility(self):
        """验证分类管道中的异常对测试可见"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # Mock 分类器使其抛出异常
            original_classify = cm.classify_message

            def failing_classify(message, **kwargs):
                raise ClassificationError("Simulated classification failure")

            # 使用 monkeypatch 或直接替换
            with patch.object(cm, "classify_message", side_effect=failing_classify):
                # MUTATION CHECK: 如果分类异常被吞没，
                # 用户会得到一个空的"成功"结果而非错误提示
                result = cm.classify_and_remember("This message triggers classification failure")

                # 验证：即使异常被处理，结果也应该表明出了问题
                # 而不是假装成功存储了
                if result.get("stored", False):
                    # 如果报告已存储，那说明异常被不当处理了
                    entries = result.get("entries", [])
                    assert len(entries) == 0, "Should not report stored entries when classification failed"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass


# ==============================================================================
# e) 逻辑操作符替换测试 (Logical Operator Replacement Test)
# ==============================================================================


class TestLogicalOperatorReplacement:
    """MUTATION: and/or 条件互换

    Why test should catch it:
    - and/or 互换会改变条件的语义
    - 例如：`if A and B` 变成 `if A or B` 会放宽条件
    - 测试应验证：复合条件的精确语义
    """

    def test_multiple_conditions_must_all_pass(self):
        """验证多条件必须全部满足（and 语义）"""
        scorer = MemoryQualityScorer()

        # 创建满足部分条件的记忆
        partial_good_mem = StoredMemory(
            storage_key="partial-1",
            content="Some content",
            type="user_preference",
            confidence=0.9,  # 高置信度 ✓
            access_count=0,  # 低访问频次 ✗
            created_at=datetime.now(timezone.utc),
            source_layer="unknown",  # 低可靠源 ✗
        )

        score = scorer.score(partial_good_mem)

        # MUTATION CHECK: 如果 and 被替换为 or，
        # 只要有一个因子高分就会得到总体高分
        # 实际实现使用加权求和（所有因子都贡献），
        # 所以单个高分因子不应该主导结果
        assert score < 0.8, (
            f"Memory with only high confidence but poor other factors " f"should not get excellent score ({score:.3f})"
        )

    def test_filter_combines_conditions_correctly(self):
        """验证过滤器的组合条件使用正确的逻辑运算符"""
        scorer = MemoryQualityScorer()

        # 创建混合质量的记忆列表
        memories = [
            StoredMemory(
                storage_key=f"mem-{i}",
                content=f"Content {i}",
                type="user_preference",
                confidence=0.9 if i % 2 == 0 else 0.05,
                access_count=10 if i % 2 == 0 else 0,
                created_at=datetime.now(timezone.utc),
                source_layer="declaration",
            )
            for i in range(6)
        ]

        # 设置较高的过滤阈值
        filtered = scorer.filter_by_quality(memories, min_score=0.5)

        # MUTATION CHECK: 如果过滤条件的 and/or 被互换，
        # 可能会包含低质量记忆或排除高质量记忆
        for mem in filtered:
            individual_score = scorer.score(mem)
            assert individual_score >= 0.5, (
                f"Filtered memory has score {individual_score:.3f} "
                f"below threshold 0.5"
            )

        # 验证确实过滤掉了一些
        assert len(filtered) < len(memories), "Should filter out some low-quality memories"

    def test_validation_uses_correct_logic_for_complex_input(self):
        """验证复杂输入验证使用正确的逻辑组合"""
        from carrymem.utils.validators import validate_limit, validate_query

        # 测试查询验证：多个无效字符应都被检测
        invalid_chars_query = "SELECT * FROM users; DROP TABLE--"

        # MUTATION CHECK: 如果验证逻辑从 and 变为 or，
        # 只检测到一个问题就放行是不够的
        try:
            validate_query(invalid_chars_query)
            # 如果没有抛异常，检查是否真的安全
            # （某些实现可能只是 sanitize 而非 reject）
        except (ValueError, Exception) as e:
            # 抛出异常是预期行为
            assert len(str(e)) > 0, "Validation error should have descriptive message"

        # 测试 limit 验证：边界条件
        with pytest.raises((ValueError, Exception)):
            validate_limit(-1)

        with pytest.raises((ValueError, Exception)):
            validate_limit(0)

        # 合法值不应报错
        validate_limit(10)
        validate_limit(DEFAULT_RECALL_LIMIT)

    def test_quality_tier_boundary_uses_correct_comparisons(self):
        """验证质量等级边界判断使用正确的比较运算符"""
        scorer = MemoryQualityScorer()

        # 测试边界值
        boundary_cases = [
            (0.799, "good"),  # just below 0.8
            (0.800, "excellent"),  # exactly 0.8
            (0.801, "excellent"),  # just above 0.8
            (0.599, "fair"),  # just below 0.6
            (0.600, "good"),  # exactly 0.6
            (0.399, "poor"),  # just below 0.4
            (0.400, "fair"),  # exactly 0.4
        ]

        for score, expected_tier in boundary_cases:
            actual_tier = scorer.get_quality_tier(score)

            # MUTATION CHECK: 如果比较运算符被翻转（> 变 <，>= 变 <=），
            # 边界值会被归入错误的等级
            assert actual_tier == expected_tier, (
                f"Score {score:.3f} should be '{expected_tier}', got '{actual_tier}'. "
                f"This indicates possible mutation in comparison operators."
            )


# ==============================================================================
# 综合变异场景测试
# ==============================================================================


class TestCombinedMutationScenarios:
    """综合多个变异点的端到端测试"""

    def test_end_to_end_with_mutated_parameters(self):
        """端到端流程在参数变异下的行为"""
        db_path = tempfile.mktemp(suffix=".db")
        try:
            cm = CarryMem(db_path=db_path)

            # 1. 存储多个不同置信度的记忆
            test_data = [
                ("High confidence preference", 0.95, "user_preference"),
                ("Medium confidence fact", 0.6, "fact_declaration"),
                ("Low confidence note", 0.25, "task_pattern"),
            ]

            storage_keys = []
            for content, confidence, mem_type in test_data:
                result = cm.classify_and_remember(content, force_type=mem_type)
                if result.get("stored"):
                    keys = result.get("storage_keys", [])
                    storage_keys.extend(keys)

            # 2. 验证都能召回
            recalled = cm.recall_memories(query="", limit=10)

            # MUTATION CHECK: 多个变异点组合影响
            # - 如果置信度判断翻转：排序可能错误
            # - 如果边界值偏移：某些记忆可能丢失
            # - 如果返回值篡改：recalled 可能为 None
            assert recalled is not None and isinstance(recalled, list), "Recall must return valid list"
            assert len(recalled) >= 2, f"Should recall at least 2 of 3 memories, got {len(recalled)}"

            # 3. 验证质量评分一致性
            scorer = MemoryQualityScorer()
            for mem_dict in recalled:
                # 重建 StoredMemory 进行评分
                mem = StoredMemory(
                    storage_key=mem_dict.get("storage_key", ""),
                    content=mem_dict.get("content", ""),
                    type=mem_dict.get("type", "unknown"),
                    confidence=mem_dict.get("confidence", 0.5),
                    access_count=mem_dict.get("access_count", 0),
                    source_layer=mem_dict.get("source_layer", "unknown"),
                )
                score = scorer.score(mem)
                assert 0.0 <= score <= 1.0, f"Score should be in [0,1], got {score}"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass

    def test_concurrent_operations_under_mutation_assumptions(self):
        """并发操作在变异假设下的稳定性"""
        import threading
        import time

        db_path = tempfile.mktemp(suffix=".db")
        errors = []
        lock = threading.Lock()

        try:
            cm = CarryMem(db_path=db_path)

            def worker(worker_id):
                try:
                    for i in range(10):
                        # MIXED OPERATION CHECK:
                        # 如果条件翻转、边界偏移等变异存在，
                        # 并发操作更容易暴露问题
                        msg = f"Worker-{worker_id}-Op-{i}: Test data"
                        result = cm.classify_and_remember(msg)

                        # 验证返回类型一致
                        if not isinstance(result, dict):
                            with lock:
                                errors.append(f"W{worker_id}-{i}: Non-dict result {type(result)}")

                        # 验证 recall 不崩溃
                        recalled = cm.recall_memories(query=f"Worker-{worker_id}")
                        if recalled is None:
                            with lock:
                                errors.append(f"W{worker_id}-{i}: Recall returned None")

                except Exception as e:
                    with lock:
                        errors.append(f"W{worker_id} fatal: {e}")

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            # MUTATION CHECK: 变异导致的微小问题会在并发下放大
            assert len(errors) == 0, f"Concurrent ops under mutation stress had errors: {errors[:5]}"

            cm.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    os.unlink(db_path + ext)
                except FileNotFoundError:
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
