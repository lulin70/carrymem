"""Tests for carrymem.i18n.I18nManager — 国际化管理器单元测试。

覆盖：翻译查找、语言切换、变量插值、回退机制、注册/注销、边界情况。
"""

import pytest

from carrymem.i18n import I18nManager, _, set_locale, get_locale, available_locales


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_i18n():
    """每个测试前后重置 I18nManager 状态，避免测试间污染。"""
    I18nManager._reset()
    from carrymem.i18n.zh_CN import ZH_CN_MESSAGES

    from carrymem.i18n.en import EN_MESSAGES

    I18nManager.register("zh-CN", ZH_CN_MESSAGES)
    I18nManager.register("en", EN_MESSAGES)
    yield
    I18nManager._reset()


# ── 1. 注册与语言列表 ─────────────────────────────────────────


class TestRegistration:
    """测试翻译表注册、注销和语言列表。"""

    def test_register_and_available_locales(self):
        """注册后 available_locales 返回已注册语言。"""
        locales = I18nManager.available_locales()
        assert "en" in locales
        assert "zh-CN" in locales

    def test_register_custom_locale(self):
        """可以注册自定义语言。"""
        I18nManager.register("ja", {"greeting": "こんにちは"})
        assert "ja" in I18nManager.available_locales()

    def test_unregister_removes_locale(self):
        """注销后语言不再可用。"""
        I18nManager.unregister("zh-CN")
        assert "zh-CN" not in I18nManager.available_locales()

    def test_available_locales_sorted(self):
        """available_locales 返回排序后的列表。"""
        locales = I18nManager.available_locales()
        assert locales == sorted(locales)


# ── 2. 语言切换 ────────────────────────────────────────────────


class TestLocaleSwitching:
    """测试 set_locale / get_locale 行为。"""

    def test_default_locale_is_en(self):
        """默认语言为 en。"""
        assert I18nManager.get_locale() == "en"

    def test_set_locale_to_zh_cn(self):
        """切换到中文成功。"""
        I18nManager.set_locale("zh-CN")
        assert I18nManager.get_locale() == "zh-CN"

    def test_set_locale_invalid_raises(self):
        """设置未注册的语言抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unsupported locale"):
            I18nManager.set_locale("ko")

    def test_set_locale_alias(self):
        """模块级 set_locale 别名工作正常。"""
        set_locale("zh-CN")
        assert get_locale() == "zh-CN"


# ── 3. 翻译查找（英文） ────────────────────────────────────────


class TestEnglishTranslation:
    """测试英文翻译的正确性。"""

    def test_translate_known_key(self):
        """已知键返回英文翻译。"""
        result = I18nManager.t("err.config_malformed")
        assert "malformed" in result.lower()

    def test_translate_status_message(self):
        """状态消息正确翻译。"""
        result = I18nManager.t("status.memory_stored", count=5)
        assert "5" in result
        assert "Remembered" in result

    def test_translate_ui_label(self):
        """UI 标签正确翻译。"""
        assert I18nManager.t("ui.type") == "Type"
        assert I18nManager.t("ui.memories") == "Memories"


# ── 4. 翻译查找（中文） ────────────────────────────────────────


class TestChineseTranslation:
    """测试中文翻译的正确性。"""

    def test_translate_known_key_zh(self):
        """中文环境下已知键返回中文翻译。"""
        I18nManager.set_locale("zh-CN")
        result = I18nManager.t("err.config_malformed")
        assert "配置文件" in result

    def test_translate_with_interpolation_zh(self):
        """中文插值消息正确替换变量。"""
        I18nManager.set_locale("zh-CN")
        result = I18nManager.t("status.memory_stored", count=3)
        assert "3" in result
        assert "记住" in result

    def test_translate_ui_label_zh(self):
        """中文 UI 标签正确翻译。"""
        I18nManager.set_locale("zh-CN")
        assert I18nManager.t("ui.type") == "类型"
        assert I18nManager.t("ui.memories") == "记忆"


# ── 5. 回退机制 ────────────────────────────────────────────────


class TestFallback:
    """测试翻译缺失时的回退行为。"""

    def test_fallback_to_en_when_missing_in_current_locale(self):
        """当前语言缺少某键时回退到英文。"""
        I18nManager.register("zh-CN", {})  # 清空中文
        I18nManager.set_locale("zh-CN")
        result = I18nManager.t("err.config_malformed")
        assert "malformed" in result.lower()

    def test_fallback_to_key_when_missing_everywhere(self):
        """所有语言都缺少该键时返回 key 本身。"""
        result = I18nManager.t("nonexistent.key.here")
        assert result == "nonexistent.key.here"

    def test_no_fallback_when_key_exists_in_current_locale(self):
        """当前语言有翻译时不回退。"""
        I18nManager.set_locale("zh-CN")
        result = I18nManager.t("err.config_malformed")
        assert "配置" in result
        assert "malformed" not in result.lower()


# ── 6. 变量插值 ────────────────────────────────────────────────


class TestInterpolation:
    """测试 str.format() 变量插值。"""

    def test_single_variable(self):
        """单变量插值正常工作。"""
        result = I18nManager.t("status.memory_updated", key="abc123")
        assert "abc123" in result

    def test_multiple_variables(self):
        """多变量插值正常工作。"""
        result = I18nManager.t("status.clean_completed", removed=10, errors=2)
        assert "10" in result
        assert "2" in result

    def test_no_interpolation_without_kwargs(self):
        """无 kwargs 时返回原始模板（含占位符）。"""
        result = I18nManager.t("status.memory_stored")
        assert "{count}" in result

    def test_interpolation_error_returns_template(self):
        """插值失败（缺少变量）时返回原始模板而非抛异常。"""
        result = I18nManager.t("status.memory_stored", wrong_var=1)
        assert "{count}" in result


# ── 7. 便捷别名 _() ──────────────────────────────────────────


class TestConvenienceAlias:
    """测试模块级 _ 别名。"""

    def test_underscore_alias_translates(self):
        """_() 是 I18nManager.t 的别名。"""
        assert _("err.unknown") == I18nManager.t("err.unknown")

    def test_underscore_respects_locale(self):
        """_() 尊当前语言设置。"""
        I18nManager.set_locale("zh-CN")
        assert "未知" in _("err.unknown")


# ── 8. 查询方法 ────────────────────────────────────────────────


class TestQueryMethods:
    """测试 has_key / keys_for_locale 等查询方法。"""

    def test_has_key_existing(self):
        """has_key 对存在的键返回 True。"""
        assert I18nManager.has_key("err.config_malformed") is True

    def test_has_key_nonexistent(self):
        """has_key 对不存在的键返回 False。"""
        assert I18nManager.has_key("totally.fake.key") is False

    def test_keys_for_locale_returns_sorted(self):
        """keys_for_locale 返回排序后的键列表。"""
        keys = I18nManager.keys_for_locale("en")
        assert keys == sorted(keys)
        assert len(keys) >= 30  # 至少 30 个翻译条目

    def test_keys_for_locale_nonexistent(self):
        """未注册语言返回空列表。"""
        assert I18nManager.keys_for_locale("xx") == []


# ── 9. 翻译数量验证 ──────────────────────────────────────────


class TestTranslationCoverage:
    """验证翻译表覆盖范围。"""

    def test_en_has_at_least_30_entries(self):
        """英文翻译表至少包含 30 条消息。"""
        assert len(I18nManager.keys_for_locale("en")) >= 30

    def test_zh_cn_has_at_least_30_entries(self):
        """中文翻译表至少包含 30 条消息。"""
        assert len(I18nManager.keys_for_locale("zh-CN")) >= 30

    def test_en_and_zh_have_same_keys(self):
        """中英文翻译表应包含相同的键集合（对齐检查）。"""
        en_keys = set(I18nManager.keys_for_locale("en"))
        zh_keys = set(I18nManager.keys_for_locale("zh-CN"))
        # 允许差异但不应太大
        missing_in_zh = en_keys - zh_keys
        missing_in_en = zh_keys - en_keys
        assert len(missing_in_zh) == 0, f"Keys missing in zh-CN: {missing_in_zh}"
        assert len(missing_in_en) == 0, f"Keys missing in en: {missing_in_en}"
