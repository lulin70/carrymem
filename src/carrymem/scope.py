"""Preference scope inference — map preference content to domain scopes.

Extracted from context.py for modularity. Aligned with PrefEval 20 topics
for benchmark consistency.
"""

import re
from typing import Any, Dict, List

SCOPE_VOCABULARY = {
    "education": {
        "en": [
            "learn",
            "study",
            "school",
            "university",
            "course",
            "education",
            "textbook",
            "exam",
            "homework",
            "lecture",
            "teach",
            "student",
            "academic",
            "reading",
            "writing",
            "math",
            "science",
            "project-based",
            "tutorial",
            "resource",
            "practice",
            "skill",
            "training",
            "workshop",
            "lesson",
            "curriculum",
            "subscription",
            "free",
            "paid",
            "online",
        ],
        "zh": [
            "学习",
            "学校",
            "课程",
            "教育",
            "考试",
            "读书",
            "大学",
            "培训",
            "教程",
            "资源",
            "练习",
            "技能",
            "课程表",
            "订阅",
            "免费",
            "付费",
            "在线",
        ],
    },
    "entertainment": {
        "en": [
            "game",
            "gaming",
            "movie",
            "film",
            "show",
            "tv",
            "music",
            "book",
            "novel",
            "sport",
            "football",
            "basketball",
            "soccer",
            "hobby",
            "play",
            "watch",
            "stream",
            "concert",
            "band",
        ],
        "zh": ["游戏", "电影", "音乐", "书", "运动", "足球", "篮球", "娱乐"],
    },
    "lifestyle": {
        "en": [
            "diet",
            "food",
            "cooking",
            "recipe",
            "exercise",
            "fitness",
            "gym",
            "health",
            "medical",
            "doctor",
            "beauty",
            "skincare",
            "wellness",
            "yoga",
            "meditation",
            "sleep",
            "nutrition",
            "vegetarian",
            "vegan",
            "organic",
            "allergy",
            "allergic",
            "meal",
            "dinner",
            "lunch",
            "breakfast",
            "snack",
            "dessert",
        ],
        "zh": [
            "饮食",
            "食物",
            "烹饪",
            "健身",
            "运动",
            "健康",
            "美容",
            "护肤",
            "素食",
            "过敏",
            "蔬菜",
            "水果",
            "早餐",
            "午餐",
            "晚餐",
        ],
    },
    "shopping": {
        "en": [
            "buy",
            "shop",
            "purchase",
            "brand",
            "fashion",
            "clothing",
            "car",
            "vehicle",
            "motor",
            "home",
            "furniture",
            "appliance",
            "deal",
            "price",
            "discount",
            "product",
            "technology",
            "gadget",
            "device",
            "subscription",
            "free",
            "paid",
            "premium",
            "afford",
            "budget",
        ],
        "zh": [
            "购物",
            "买",
            "品牌",
            "时尚",
            "服装",
            "汽车",
            "家居",
            "电子产品",
            "订阅",
            "免费",
            "付费",
            "预算",
        ],
    },
    "travel": {
        "en": [
            "travel",
            "trip",
            "vacation",
            "hotel",
            "flight",
            "restaurant",
            "dining",
            "transport",
            "airline",
            "destination",
            "tour",
            "visit",
            "abroad",
            "luggage",
            "booking",
            "resort",
            "boutique",
            "inn",
            "hostel",
            "airbnb",
            "cruise",
            "sightseeing",
            "backpack",
        ],
        "zh": ["旅行", "旅游", "酒店", "餐厅", "航班", "出行", "度假", "旅馆", "民宿"],
    },
    "work": {
        "en": [
            "work",
            "job",
            "career",
            "office",
            "remote",
            "meeting",
            "project",
            "team",
            "manager",
            "company",
            "professional",
            "business",
            "email",
            "deadline",
            "productivity",
            "commute",
            "project-based",
            "collaboration",
            "task",
            "schedule",
        ],
        "zh": [
            "工作",
            "职业",
            "办公室",
            "远程",
            "项目",
            "团队",
            "公司",
            "上班",
            "协作",
            "任务",
            "排期",
        ],
    },
    "pet": {
        "en": [
            "pet",
            "dog",
            "cat",
            "animal",
            "veterinary",
            "breed",
            "puppy",
            "kitten",
            "fish",
            "bird",
            "rabbit",
            "hamster",
        ],
        "zh": ["宠物", "狗", "猫", "动物", "养宠"],
    },
    "programming": {
        "en": [
            "python",
            "java",
            "javascript",
            "code",
            "coding",
            "programming",
            "software",
            "developer",
            "database",
            "api",
            "framework",
            "library",
            "debug",
            "deploy",
            "algorithm",
            "react",
            "typescript",
            "rust",
            "golang",
            "sql",
            "postgresql",
            "mysql",
            "redis",
            "docker",
            "server",
            "web server",
            "backend",
            "frontend",
            "compiler",
            "function",
            "class",
            "method",
            "variable",
            "loop",
            "array",
            "language",
            "ide",
            "editor",
            "terminal",
            "command",
        ],
        "zh": ["编程", "代码", "开发", "程序", "软件", "数据库", "框架"],
    },
}


def infer_scopes(text: str) -> List[str]:
    """Infer scope domains from text content using keyword matching.

    Returns a list of matching scope names (e.g., ["education", "programming"]).
    Returns empty list if no scope matches (meaning the preference is general/unscoped).
    """
    if not text or not isinstance(text, str):
        return []

    text_lower = text.lower()
    matched_scopes = []

    for scope, lang_keywords in SCOPE_VOCABULARY.items():
        for lang, keywords in lang_keywords.items():
            for kw in keywords:
                if lang == "en":
                    if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                        matched_scopes.append(scope)
                        break
                else:
                    if kw in text_lower:
                        matched_scopes.append(scope)
                        break
            else:
                continue
            break

    return matched_scopes


def preference_matches_scope(preference: Dict[str, Any], question: str, core_confidence_threshold: float = 0.9) -> bool:
    """Check if a preference should be injected for the given question.

    Rules:
    1. Core preferences (confidence >= threshold) always match (safety net).
    2. If preference has explicit scope in metadata, check overlap with question scopes.
    3. If no explicit scope, infer from preference content and check overlap.
    4. If neither scope nor content inference yields a match, allow injection.
    5. If preference has scope but question doesn't, check if question content
       is ambiguous (could belong to preference's scope).
    """
    if preference.get("confidence", 0) >= core_confidence_threshold:
        return True

    metadata = preference.get("metadata", {})
    if isinstance(metadata, str):
        try:
            import json

            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            metadata = {}

    pref_scopes = metadata.get("scopes", [])
    if not pref_scopes:
        pref_scopes = infer_scopes(preference.get("raw_text", "") or preference.get("content", ""))

    if not pref_scopes:
        return True

    question_scopes = infer_scopes(question or "")
    if not question_scopes or not question:
        return True

    if set(pref_scopes) & set(question_scopes):
        return True

    for scope in pref_scopes:
        if scope in SCOPE_VOCABULARY:
            for lang, keywords in SCOPE_VOCABULARY[scope].items():
                for kw in keywords:
                    if lang == "en":
                        if re.search(r"\b" + re.escape(kw) + r"\b", question.lower()):
                            return True
                    else:
                        if kw in question.lower():
                            return True

    return False
