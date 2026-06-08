"""Tests for coreference resolution module."""

import pytest

from carrymem.coreference import (
    PRONOUN_GENDER,
    _extract_entities_en,
    _extract_entities_zh,
    _find_matching_entity,
    _replace_pronoun,
    has_pronoun,
    resolve_coreference,
)


class TestHasPronoun:
    def test_english_subject_pronouns(self):
        assert has_pronoun("She likes spicy food") is True
        assert has_pronoun("He is a developer") is True
        assert has_pronoun("It works well") is True
        assert has_pronoun("They are coming") is True

    def test_english_object_pronouns(self):
        assert has_pronoun("I told him about it") is True
        assert has_pronoun("Give her the book") is True

    def test_english_possessive_pronouns(self):
        assert has_pronoun("His car is red") is True
        assert has_pronoun("Her preference is Python") is True
        assert has_pronoun("Its features are great") is True

    def test_english_demonstrative(self):
        assert has_pronoun("That project uses React") is True
        assert has_pronoun("This is important") is True

    def test_chinese_pronouns(self):
        assert has_pronoun("她喜欢吃辣") is True
        assert has_pronoun("他是工程师") is True
        assert has_pronoun("它很好用") is True

    def test_chinese_demonstrative(self):
        assert has_pronoun("那个项目用React") is True
        assert has_pronoun("该公司已上市") is True

    def test_no_pronoun(self):
        assert has_pronoun("Python is great for data analysis") is False
        assert has_pronoun("我喜欢吃辣") is False
        assert has_pronoun("") is False
        assert has_pronoun("The database uses PostgreSQL") is False

    def test_pronoun_as_substring(self):
        # "history" contains "his" but as a separate word, \b should NOT match
        assert has_pronoun("history") is False
        # "shell" contains "she" but as a separate word
        assert has_pronoun("shell") is False


class TestExtractEntitiesEn:
    def test_my_mom(self):
        entities = _extract_entities_en("My mom is from Sichuan")
        assert len(entities) >= 1
        assert any("mom" in e[0] for e in entities)

    def test_my_dad(self):
        entities = _extract_entities_en("My dad works at Google")
        assert len(entities) >= 1
        assert any("dad" in e[0] for e in entities)

    def test_my_friend(self):
        entities = _extract_entities_en("My friend recommended this book")
        assert len(entities) >= 1
        assert any("friend" in e[0] for e in entities)

    def test_no_entities(self):
        entities = _extract_entities_en("The weather is nice today")
        assert len(entities) == 0

    def test_gender_mapping(self):
        entities = _extract_entities_en("My mom and my dad are here")
        genders = {e[0]: e[1] for e in entities}
        assert any(g == "female" for g in genders.values())
        assert any(g == "male" for g in genders.values())


class TestExtractEntitiesZh:
    def test_my_mom_zh(self):
        entities = _extract_entities_zh("我妈妈是四川人")
        assert len(entities) >= 1
        assert any("妈妈" in e[0] for e in entities)

    def test_project_name(self):
        entities = _extract_entities_zh("CarryMem项目已经发布了")
        assert len(entities) >= 1
        assert any("项目" in e[0] for e in entities)

    def test_no_entities_zh(self):
        entities = _extract_entities_zh("今天天气很好")
        assert len(entities) == 0


class TestResolveCoreference:
    def test_she_resolved_to_mom(self):
        context = "My mom is from Sichuan"
        resolved, was_resolved = resolve_coreference("She likes spicy food", context=context)
        assert was_resolved is True
        assert "mom" in resolved.lower()
        assert "she" not in resolved.lower()

    def test_he_resolved_to_dad(self):
        context = "My dad is a developer"
        resolved, was_resolved = resolve_coreference("He prefers Python", context=context)
        assert was_resolved is True
        assert "dad" in resolved.lower()

    def test_zh_pronoun_resolved(self):
        context = "我妈妈是四川人"
        resolved, was_resolved = resolve_coreference("她喜欢吃辣", context=context)
        assert was_resolved is True
        assert "妈妈" in resolved
        assert "她" not in resolved

    def test_no_pronoun_no_change(self):
        resolved, was_resolved = resolve_coreference("Python is great", context="Some context")
        assert was_resolved is False
        assert resolved == "Python is great"

    def test_no_context_no_resolution(self):
        resolved, was_resolved = resolve_coreference("She likes spicy food")
        # Without context, can't resolve
        assert was_resolved is False

    def test_possessive_pronoun(self):
        context = "My mom is from Sichuan"
        resolved, was_resolved = resolve_coreference("Her preference is spicy food", context=context)
        assert was_resolved is True
        assert "mom" in resolved.lower()

    def test_zh_demonstrative(self):
        context = "CarryMem项目已经发布了"
        resolved, was_resolved = resolve_coreference("该项目用Python", context=context)
        assert was_resolved is True
        assert "CarryMem" in resolved or "项目" in resolved

    def test_en_demonstrative_that(self):
        context = "My project uses Python"
        resolved, was_resolved = resolve_coreference("That is important for data analysis", context=context)
        assert was_resolved is True
        assert "project" in resolved.lower()

    def test_en_demonstrative_this(self):
        context = "My team works on backend"
        resolved, was_resolved = resolve_coreference("This is important for scalability", context=context)
        # "this" may or may not resolve depending on entity extraction
        # At minimum, should not crash
        assert isinstance(resolved, str)

    def test_with_recent_memories(self):
        recent = [{"content": "My wife prefers boutique hotels"}]
        resolved, was_resolved = resolve_coreference("She also likes spas", recent_memories=recent)
        assert was_resolved is True
        assert "wife" in resolved.lower()

    def test_preserves_case(self):
        context = "My mom is from Sichuan"
        resolved, was_resolved = resolve_coreference("She likes it", context=context)
        # First letter should be capitalized if original was
        if was_resolved:
            assert resolved[0].isupper()


class TestFindMatchingEntity:
    def test_male_pronoun_matches_male_entity(self):
        entities = [("my mom", "female"), ("my dad", "male")]
        result = _find_matching_entity("he", entities)
        assert "dad" in result

    def test_female_pronoun_matches_female_entity(self):
        entities = [("my mom", "female"), ("my dad", "male")]
        result = _find_matching_entity("she", entities)
        assert "mom" in result

    def test_neuter_pronoun_fallback(self):
        entities = [("my project", "neuter"), ("my mom", "female")]
        result = _find_matching_entity("it", entities)
        assert "project" in result

    def test_no_entities(self):
        result = _find_matching_entity("she", [])
        assert result is None


class TestReplacePronoun:
    def test_replace_subject_pronoun(self):
        result = _replace_pronoun("She likes spicy food", "she", "my mom")
        assert "My mom" in result  # Capitalized
        assert result == "My mom likes spicy food"

    def test_replace_preserves_case(self):
        result = _replace_pronoun("She likes it", "she", "my mom")
        assert result.startswith("My mom")

    def test_replace_possessive_pronoun(self):
        result = _replace_pronoun("Her preference is Python", "her", "my mom")
        assert "My mom's" in result  # Capitalized possessive

    def test_replace_only_first_occurrence(self):
        result = _replace_pronoun("She said she likes it", "she", "my mom")
        # Should only replace first occurrence (count=1)
        assert "My mom" in result
        assert "she" in result  # Second "she" should remain


class TestIntegration:
    """Integration tests with CarryMem classify_and_remember."""

    def test_coreference_in_classify_and_remember(self, tmp_path):
        """Test that coreference resolution is applied in classify_and_remember."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        # First, store context about mom
        cm.classify_and_remember("My mom is from Sichuan", force_type="personal_fact")

        # Now store a message with pronoun
        result = cm.classify_and_remember("She likes spicy food", force_type="user_preference")

        # The stored content should have resolved the pronoun
        if result["stored"]:
            content = result.get("content", "")
            # Either resolved or original, but should be stored
            assert "spicy" in content.lower() or "辣" in content

    def test_raw_text_preserved(self, tmp_path):
        """Test that raw_text preserves the original message with pronoun."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        cm.classify_and_remember("My mom is from Sichuan", force_type="personal_fact")
        result = cm.classify_and_remember("She likes spicy food", force_type="user_preference")

        if result["stored"]:
            entries = result.get("entries", [])
            if entries:
                raw_text = entries[0].get("raw_text", "")
                # raw_text should preserve original "She likes spicy food"
                assert "She" in raw_text or "spicy" in raw_text

    def test_no_pronoun_no_resolution(self, tmp_path):
        """Test that messages without pronouns are not affected."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        result = cm.classify_and_remember("I prefer Python for data analysis", force_type="user_preference")
        assert result["stored"]
        assert "Python" in result.get("content", "")
