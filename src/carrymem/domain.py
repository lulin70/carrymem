"""Automatic domain sensing — infer user's domain from memory content.

CarryMem auto-detects the user's professional domain based on accumulated
memories, enabling domain-aware preference injection and scope matching.
"""

import re
from typing import List, Optional


DOMAIN_VOCABULARY = {
    "coding": {
        "keywords": [
            # Programming languages
            "python",
            "java",
            "javascript",
            "typescript",
            "rust",
            "golang",
            "c++",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
            # Frameworks & tools
            "react",
            "vue",
            "angular",
            "django",
            "flask",
            "fastapi",
            "spring",
            "node",
            "docker",
            "kubernetes",
            "git",
            "github",
            "vscode",
            "ide",
            "debug",
            "deploy",
            "api",
            "backend",
            "frontend",
            "compiler",
            "database",
            "sql",
            "postgresql",
            "mysql",
            "redis",
            "mongodb",
            # Dev concepts
            "refactor",
            "code review",
            "pull request",
            "merge",
            "branch",
            "unit test",
            "integration test",
            "ci/cd",
            "pipeline",
            "algorithm",
            "data structure",
            "design pattern",
            "architecture",
        ],
        "zh": [
            "编程",
            "代码",
            "开发",
            "程序",
            "软件",
            "数据库",
            "框架",
            "前端",
            "后端",
            "部署",
            "调试",
            "接口",
            "服务器",
        ],
        "ja": [
            "プログラミング",
            "コード",
            "開発",
            "ソフトウェア",
            "データベース",
            "フレームワーク",
            "フロントエンド",
            "バックエンド",
            "デプロイ",
        ],
    },
    "writing": {
        "keywords": [
            "blog",
            "article",
            "draft",
            "publish",
            "editor",
            "writing",
            "content",
            "audience",
            "tone",
            "style guide",
            "copywriting",
            "markdown",
            "wordpress",
            "seo",
            "headline",
            "subtitle",
            "narrative",
            "storytelling",
            "proofread",
            "revision",
        ],
        "zh": ["写作", "博客", "文章", "发布", "编辑", "内容", "读者", "标题"],
        "ja": ["執筆", "ブログ", "記事", "公開", "編集", "コンテンツ", "読者"],
    },
    "research": {
        "keywords": [
            "paper",
            "research",
            "study",
            "hypothesis",
            "experiment",
            "peer-reviewed",
            "citation",
            "methodology",
            "analysis",
            "literature review",
            "thesis",
            "dissertation",
            "journal",
            "conference",
            "arxiv",
            "dataset",
            "statistical",
            "correlation",
        ],
        "zh": ["论文", "研究", "实验", "假设", "方法论", "引用", "学术", "期刊"],
        "ja": ["論文", "研究", "実験", "仮説", "方法論", "引用", "学術", "ジャーナル"],
    },
    "management": {
        "keywords": [
            "sprint",
            "standup",
            "backlog",
            "roadmap",
            "milestone",
            "stakeholder",
            "deadline",
            "resource",
            "budget",
            "timeline",
            "agile",
            "scrum",
            "kanban",
            "jira",
            "okr",
            "kpi",
            "team lead",
            "project manager",
            "deliverable",
            "scope",
        ],
        "zh": ["项目", "团队", "冲刺", "迭代", "里程碑", "交付", "排期", "预算"],
        "ja": ["プロジェクト", "チーム", "スプリント", "マイルストーン", "納品", "予算"],
    },
    "data": {
        "keywords": [
            "analytics",
            "dashboard",
            "metric",
            "visualization",
            "machine learning",
            "model",
            "training",
            "inference",
            "data pipeline",
            "etl",
            "warehouse",
            "lakehouse",
            "pandas",
            "numpy",
            "jupyter",
            "notebook",
            "spark",
            "feature engineering",
            "prediction",
            "classification",
        ],
        "zh": ["数据", "分析", "模型", "训练", "可视化", "仪表盘", "机器学习"],
        "ja": ["データ", "分析", "モデル", "訓練", "可視化", "ダッシュボード"],
    },
}


def infer_domain(text: str) -> Optional[str]:
    """Infer the professional domain from text content.

    Returns the domain with the highest keyword match count,
    or None if no domain scores above threshold.
    """
    if not text or not isinstance(text, str):
        return None

    text_lower = text.lower()
    scores = {}

    for domain, vocab in DOMAIN_VOCABULARY.items():
        score = 0
        # English keywords
        for kw in vocab.get("keywords", []):
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                score += 1
        # Chinese keywords
        for kw in vocab.get("zh", []):
            if kw in text_lower:
                score += 1
        # Japanese keywords
        for kw in vocab.get("ja", []):
            if kw in text_lower:
                score += 1
        if score > 0:
            scores[domain] = score

    if not scores:
        return None

    # Return domain with highest score
    return max(scores, key=scores.get)


def infer_domains_from_memories(memories: list) -> List[str]:
    """Infer user's domains from a list of memory dicts.

    Aggregates domain signals across all memories and returns
    domains sorted by total score (descending).
    """
    domain_scores = {}

    for m in memories:
        content = (m.get("raw_text", "") or "") + " " + (m.get("content", "") or "")
        text_lower = content.lower()

        for domain, vocab in DOMAIN_VOCABULARY.items():
            score = 0
            for kw in vocab.get("keywords", []):
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    score += 1
            for kw in vocab.get("zh", []):
                if kw in text_lower:
                    score += 1
            for kw in vocab.get("ja", []):
                if kw in text_lower:
                    score += 1
            if score > 0:
                domain_scores[domain] = domain_scores.get(domain, 0) + score

    if not domain_scores:
        return []

    # Sort by score descending
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
    # Only return domains with meaningful score (at least 2 keyword hits)
    return [d for d, s in sorted_domains if s >= 2]


def get_domain_description(domain: str) -> str:
    """Get human-readable description for a domain."""
    descriptions = {
        "coding": "Developer / Software Engineer",
        "writing": "Content Creator / Writer",
        "research": "Researcher / Academic",
        "management": "Project Manager / Team Lead",
        "data": "Data Scientist / Analyst",
    }
    return descriptions.get(domain, domain)
