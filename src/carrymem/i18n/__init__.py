"""轻量级国际化（i18n）管理器 — 不依赖 gettext。

提供基于字典的翻译系统，支持运行时语言切换、变量插值和回退机制。

Usage::

    from carrymem.i18n import I18nManager

    I18nManager.set_locale("zh-CN")
    print(I18nManager.t("err.config_malformed"))
    # → "配置文件格式错误或缺少必要字段。"

    print(I18nManager.t("memory.stored", count=3))
    # → "已记住 3 条记忆"
"""

from __future__ import annotations

from typing import Dict


class I18nManager:
    """轻量级国际化管理器（不依赖 gettext）。

    使用类级别的翻译字典存储各语言的消息模板，
    通过 ``t()`` 方法进行翻译查找和变量插值。
    """

    _translations: Dict[str, Dict[str, str]] = {}
    _current_locale: str = "en"
    _default_locale: str = "en"

    # ── 注册翻译表 ──────────────────────────────────────────────

    @classmethod
    def register(cls, locale: str, messages: Dict[str, str]) -> None:
        """注册一个语言的翻译表。

        Args:
            locale: 语言代码，如 ``"zh-CN"``、``"en"``。
            messages: 消息键到翻译文本的映射字典。
        """
        cls._translations[locale] = messages

    @classmethod
    def unregister(cls, locale: str) -> None:
        """移除指定语言的翻译表。"""
        cls._translations.pop(locale, None)

    # ── 语言切换 ────────────────────────────────────────────────

    @classmethod
    def set_locale(cls, locale: str) -> None:
        """设置当前活动语言。

        Args:
            locale: 目标语言代码。必须在已注册的语言列表中。

        Raises:
            ValueError: 语言未注册时抛出。
        """
        if locale not in cls._translations:
            raise ValueError(f"Unsupported locale: '{locale}'. " f"Available: {sorted(cls._translations.keys())}")
        cls._current_locale = locale

    @classmethod
    def get_locale(cls) -> str:
        """获取当前活动语言代码。"""
        return cls._current_locale

    # ── 翻译 ────────────────────────────────────────────────────

    @classmethod
    def t(cls, msg_key: str, **kwargs: object) -> str:
        """翻译一条消息，支持变量插值。

        查找顺序：当前语言 → 默认语言(en) → 返回 key 本身。

        Args:
            msg_key: 消息键名。
            **kwargs: 插值变量，用于 ``str.format()``。

        Returns:
            翻译后的字符串。
        """
        template = cls._translations.get(cls._current_locale, {}).get(msg_key)
        if template is None and cls._current_locale != cls._default_locale:
            template = cls._translations.get(cls._default_locale, {}).get(msg_key)
        if template is None:
            template = msg_key
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, IndexError):
                return template
        return template

    # ── 查询 ────────────────────────────────────────────────────

    @classmethod
    def available_locales(cls) -> list[str]:
        """返回所有已注册的语言代码列表（排序后）。"""
        return sorted(cls._translations.keys())

    @classmethod
    def has_key(cls, key: str) -> bool:
        """检查任意语言中是否存在该消息键。"""
        return any(key in msgs for msgs in cls._translations.values())

    @classmethod
    def keys_for_locale(cls, locale: str) -> list[str]:
        """返回指定语言的所有消息键列表。"""
        return sorted(cls._translations.get(locale, {}).keys())

    # ── 重置（测试用） ──────────────────────────────────────────

    @classmethod
    def _reset(cls) -> None:
        """清空所有注册状态（仅用于测试）。"""
        cls._translations.clear()
        cls._current_locale = cls._default_locale


# ── 自动加载内置翻译表 ───────────────────────────────────────────

from carrymem.i18n.en import EN_MESSAGES  # noqa: E402
from carrymem.i18n.zh_CN import ZH_CN_MESSAGES  # noqa: E402

I18nManager.register("zh-CN", ZH_CN_MESSAGES)
I18nManager.register("en", EN_MESSAGES)

# 便捷别名
_ = I18nManager.t
set_locale = I18nManager.set_locale
get_locale = I18nManager.get_locale
available_locales = I18nManager.available_locales

__all__ = [
    # Main class
    "I18nManager",
    # Convenience aliases
    "_",
    "set_locale",
    "get_locale",
    "available_locales",
]
