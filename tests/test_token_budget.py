"""Focused tests for unified token estimation and output budgeting."""

import pytest

from carrymem.token_budget import PromptBlock, enforce_output_budget, estimate_tokens


def test_estimate_tokens_empty_english_cjk_and_mixed():
    assert estimate_tokens("") >= 1
    assert estimate_tokens("Hello world this is a test") > 0
    assert estimate_tokens("你好世界这是一个测试") > 0
    assert estimate_tokens("Hello 你好 world 世界") > 0


def test_estimate_tokens_is_shared_with_legacy_selection_alias():
    from carrymem.selection import _estimate_tokens

    for text in ("", "English", "中文", "mixed 混合"):
        assert _estimate_tokens(text) == estimate_tokens(text)


def test_drops_normal_blocks_by_priority_then_original_order():
    blocks = (
        PromptBlock("first " + "a" * 20, drop_priority=1, key="first"),
        PromptBlock("second " + "b" * 20, drop_priority=2, key="second"),
        PromptBlock("third " + "c" * 20, drop_priority=2, key="third"),
    )
    result = enforce_output_budget("prefix", blocks, max_tokens=8)

    assert result.token_count <= 8
    assert result.retained_blocks == (blocks[0],)
    assert [truncation.dropped_count for truncation in result.truncations] == [1, 1]


def test_protected_block_is_retained_when_normal_blocks_are_dropped():
    protected = PromptBlock("protected content", protected=True, key="protected")
    normal = PromptBlock("normal content " + "x" * 30, drop_priority=10, key="normal")

    result = enforce_output_budget("prefix", (normal, protected), max_tokens=6)

    assert result.token_count <= 6
    assert protected in result.retained_blocks
    assert normal not in result.retained_blocks
    assert result.degradation is None


def test_protected_content_degrades_explicitly_without_exceeding_budget():
    protected = PromptBlock("protected " + "中文" * 100, protected=True)

    result = enforce_output_budget("prefix", (protected,), max_tokens=5)

    assert result.degradation is not None
    assert result.token_count <= 5
    assert result.truncations[-1].protected is True


def test_same_input_produces_same_result():
    blocks = (
        PromptBlock("alpha " + "a" * 20, drop_priority=1),
        PromptBlock("beta " + "b" * 20, drop_priority=2),
        PromptBlock("gamma " + "c" * 20, drop_priority=1),
    )

    first = enforce_output_budget("prefix", blocks, max_tokens=8)
    second = enforce_output_budget("prefix", blocks, max_tokens=8)

    assert first == second


@pytest.mark.parametrize("max_tokens", [0, -1, True, 1.5, None])
def test_invalid_budget_fails_closed(max_tokens):
    with pytest.raises(ValueError):
        enforce_output_budget("prefix", (), max_tokens=max_tokens)


def test_invalid_block_input_fails_closed():
    with pytest.raises(TypeError):
        enforce_output_budget("prefix", ("not a block",), max_tokens=10)
