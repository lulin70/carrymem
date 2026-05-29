"""Tests for automatic domain sensing."""

import pytest
from carrymem.domain import infer_domain, infer_domains_from_memories, get_domain_description


class TestInferDomain:
    def test_coding_domain(self):
        assert infer_domain("I prefer Python for backend development") == "coding"

    def test_writing_domain(self):
        assert infer_domain("I write blog posts about technology") == "writing"

    def test_research_domain(self):
        assert infer_domain("My research focuses on machine learning methodology") == "research"

    def test_management_domain(self):
        assert infer_domain("We use agile scrum for sprint planning") == "management"

    def test_data_domain(self):
        assert infer_domain("I use pandas for data analysis and visualization") == "data"

    def test_no_domain(self):
        assert infer_domain("I like coffee") is None

    def test_empty_input(self):
        assert infer_domain("") is None
        assert infer_domain(None) is None

    def test_chinese_coding(self):
        assert infer_domain("我偏好用Python做后端开发") == "coding"

    def test_japanese_research(self):
        assert infer_domain("論文の研究方法について") == "research"


class TestInferDomainsFromMemories:
    def test_multiple_domains(self):
        memories = [
            {
                "content": "I use Python and django for backend development with docker",
                "raw_text": "",
            },
            {"content": "We follow agile scrum and use jira for sprint planning", "raw_text": ""},
            {"content": "I like dark mode", "raw_text": ""},
        ]
        domains = infer_domains_from_memories(memories)
        assert "coding" in domains
        assert "management" in domains

    def test_empty_memories(self):
        assert infer_domains_from_memories([]) == []

    def test_threshold_filtering(self):
        # Single keyword hit should not qualify (threshold = 2)
        memories = [{"content": "I mentioned python once", "raw_text": ""}]
        domains = infer_domains_from_memories(memories)
        # "python" alone scores 1, below threshold of 2
        assert "coding" not in domains


class TestGetDomainDescription:
    def test_known_domain(self):
        assert "Developer" in get_domain_description("coding")

    def test_unknown_domain(self):
        assert get_domain_description("unknown") == "unknown"
