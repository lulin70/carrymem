"""
Coverage improvement tests for low-coverage modules:
- utils/config.py (47.50%)
- utils/language.py (50.82%)
- security/encryption.py (70.17%)
- rules/skill.py (83.64%)
- rules/refinement_session.py (86.93%)
- semantic/merger.py (87.67%)
"""

import json
import os
import pytest
import tempfile

from carrymem.utils.config import ConfigManager
from carrymem.utils.language import LanguageManager
from carrymem.security.encryption import MemoryEncryption, NoEncryption, EncryptionError
from carrymem.rules.skill import skill_pack, skill_verify, skill_install, SKILL_MAX_RULES
from carrymem.rules.models import Rule
from carrymem.rules.storage import RuleStorage


class TestConfigManager:
    """Cover utils/config.py"""

    def test_default_config_empty(self):
        cm = ConfigManager(config_path="/nonexistent/path")
        assert cm.config == {}

    def test_get_from_empty_config(self):
        cm = ConfigManager(config_path="/nonexistent/path")
        assert cm.get("missing_key") is None
        assert cm.get("missing_key", "default") == "default"

    def test_get_nested_key(self):
        tmpdir = tempfile.mkdtemp()
        config_path = os.path.join(tmpdir, "test_config.json")
        try:
            with open(config_path, "w") as f:
                json.dump({"storage": {"data_path": "/tmp/data"}}, f)

            cm = ConfigManager(config_path=config_path)
            assert cm.get("storage.data_path") == "/tmp/data"
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_get_from_env_override(self):
        cm = ConfigManager(config_path="/nonexistent/path")
        os.environ["CARRYMEM_TEST_KEY"] = "env_value"
        try:
            assert cm.get("test_key") == "env_value"
        finally:
            del os.environ["CARRYMEM_TEST_KEY"]

    def test_set_nested_key(self):
        cm = ConfigManager(config_path="/nonexistent/path")
        cm.set("storage.data_path", "/new/path")
        assert cm.get("storage.data_path") == "/new/path"

    def test_set_deep_nested_key(self):
        cm = ConfigManager(config_path="/nonexistent/path")
        cm.set("a.b.c", "deep_value")
        assert cm.get("a.b.c") == "deep_value"

    def test_reload_config(self):
        tmpdir = tempfile.mkdtemp()
        config_path = os.path.join(tmpdir, "reload_config.json")
        try:
            with open(config_path, "w") as f:
                json.dump({"key": "value1"}, f)

            cm = ConfigManager(config_path=config_path)
            assert cm.get("key") == "value1"

            with open(config_path, "w") as f:
                json.dump({"key": "value2"}, f)

            cm.reload()
            assert cm.get("key") == "value2"
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_get_rules_json(self):
        tmpdir = tempfile.mkdtemp()
        rules_path = os.path.join(tmpdir, "rules.json")
        try:
            with open(rules_path, "w") as f:
                json.dump({"rule1": {"action": "test"}}, f)

            cm = ConfigManager(config_path="/nonexistent/path")
            rules = cm.get_rules(rules_path=rules_path)
            assert "rule1" in rules
        finally:
            if os.path.exists(rules_path):
                os.remove(rules_path)

    def test_get_rules_missing_file(self):
        cm = ConfigManager(config_path="/nonexistent/path")
        rules = cm.get_rules(rules_path="/nonexistent/rules.json")
        assert rules == {}

    def test_load_json_config(self):
        tmpdir = tempfile.mkdtemp()
        config_path = os.path.join(tmpdir, "config.json")
        try:
            with open(config_path, "w") as f:
                json.dump({"key": "value", "nested": {"a": 1}}, f)

            cm = ConfigManager(config_path=config_path)
            assert cm.get("key") == "value"
            assert cm.get("nested.a") == 1
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_env_path_config(self):
        os.environ["CARRYMEM_CONFIG_PATH"] = "/nonexistent/env_config.json"
        try:
            cm = ConfigManager()
            assert cm.config_path == "/nonexistent/env_config.json"
        finally:
            del os.environ["CARRYMEM_CONFIG_PATH"]


class TestLanguageManager:
    """Cover utils/language.py"""

    def setup_method(self):
        self.lm = LanguageManager()

    def test_detect_english(self):
        lang, conf = self.lm.detect_language("I prefer dark mode for coding")
        assert lang == "en"

    def test_detect_chinese(self):
        lang, conf = self.lm.detect_language("我喜欢用深色模式写代码")
        assert lang == "zh-cn"
        assert conf >= 0.9

    def test_detect_japanese_hiragana(self):
        lang, conf = self.lm.detect_language("コードレビューは必ず実施してください")
        assert lang == "ja"
        assert conf >= 0.9

    def test_detect_japanese_katakana(self):
        lang, conf = self.lm.detect_language("データベースの設定")
        assert lang == "ja"

    def test_detect_none(self):
        lang, conf = self.lm.detect_language(None)
        assert lang == "en"

    def test_get_keywords_english(self):
        keywords = self.lm.get_keywords("user_preference", "en")
        assert "prefer" in keywords

    def test_get_keywords_chinese(self):
        keywords = self.lm.get_keywords("user_preference", "zh-cn")
        assert "喜欢" in keywords

    def test_get_keywords_fallback_to_english(self):
        keywords = self.lm.get_keywords("user_preference", "xx")
        assert len(keywords) > 0

    def test_get_keywords_unknown_type(self):
        keywords = self.lm.get_keywords("unknown_type", "en")
        assert keywords == []

    def test_get_negation_words_english(self):
        words = self.lm.get_negation_words("en")
        assert "not" in words

    def test_get_negation_words_chinese(self):
        words = self.lm.get_negation_words("zh-cn")
        assert "不" in words

    def test_get_negation_words_fallback(self):
        words = self.lm.get_negation_words("xx")
        assert len(words) > 0

    def test_is_supported_language(self):
        assert self.lm.is_supported_language("en") is True
        assert self.lm.is_supported_language("zh-cn") is True
        assert self.lm.is_supported_language("xx") is False

    def test_get_language_name(self):
        assert self.lm.get_language_name("en") == "English"
        assert self.lm.get_language_name("zh-cn") == "Chinese (Simplified)"
        assert self.lm.get_language_name("xx") == "xx"

    def test_extract_keywords_english(self):
        keywords = self.lm.extract_keywords("I prefer dark mode", "en")
        assert len(keywords) >= 1

    def test_extract_keywords_chinese(self):
        keywords = self.lm.extract_keywords("我喜欢深色模式", "zh-cn")
        assert len(keywords) >= 1

    def test_detect_memory_type(self):
        results = self.lm.detect_memory_type("I prefer dark mode for coding", "en")
        assert len(results) >= 1
        types = [r[0] for r in results]
        assert "user_preference" in types

    def test_map_language_code(self):
        assert self.lm._map_language_code("zh") == "zh-cn"
        assert self.lm._map_language_code("zh-hans") == "zh-cn"
        assert self.lm._map_language_code("zh-hant") == "zh-tw"
        assert self.lm._map_language_code("en") == "en"

    def test_supported_languages_count(self):
        assert len(LanguageManager.SUPPORTED_LANGUAGES) >= 8

    def test_multi_lang_keywords_coverage(self):
        for mem_type in LanguageManager.MULTI_LANG_KEYWORDS:
            for lang in ["en", "zh-cn", "ja"]:
                keywords = self.lm.get_keywords(mem_type, lang)
                assert len(keywords) > 0, f"No keywords for {mem_type}/{lang}"


class TestMemoryEncryption:
    """Cover security/encryption.py"""

    def test_no_encryption_passthrough(self):
        enc = NoEncryption()
        assert enc.encrypt("hello") == "hello"
        assert enc.decrypt("hello") == "hello"
        assert enc.is_active is False
        assert enc.backend == "none"

    def test_stream_cipher_roundtrip(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "test.key")
        try:
            enc = MemoryEncryption(key="test_password", key_file=key_file)
            if enc.backend == "hmac-ctr":
                plaintext = "Hello, World! こんにちは 你好"
                ciphertext = enc.encrypt(plaintext)
                assert ciphertext != plaintext
                decrypted = enc.decrypt(ciphertext)
                assert decrypted == plaintext
        finally:
            for f in [key_file, key_file + ".salt"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_encrypt_empty_string(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "empty.key")
        try:
            enc = MemoryEncryption(key="test", key_file=key_file)
            assert enc.encrypt("") == ""
            assert enc.decrypt("") == ""
        finally:
            for f in [key_file, key_file + ".salt"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_encryption_is_active(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "active.key")
        try:
            enc = MemoryEncryption(key="test", key_file=key_file)
            assert enc.is_active is True
        finally:
            for f in [key_file, key_file + ".salt"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_encryption_backend(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "backend.key")
        try:
            enc = MemoryEncryption(key="test", key_file=key_file)
            assert enc.backend in ("hmac-ctr", "fernet")
        finally:
            for f in [key_file, key_file + ".salt"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_auto_generated_key(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "auto.key")
        try:
            enc = MemoryEncryption(key_file=key_file)
            assert enc.is_active is True

            plaintext = "auto key test"
            ciphertext = enc.encrypt(plaintext)
            assert enc.decrypt(ciphertext) == plaintext
        finally:
            for f in [key_file]:
                if os.path.exists(f):
                    os.remove(f)

    def test_invalid_ciphertext(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "invalid.key")
        try:
            enc = MemoryEncryption(key="test", key_file=key_file)
            if enc.backend == "hmac-ctr":
                with pytest.raises(EncryptionError):
                    enc.decrypt("not_valid_base64!!!")
        finally:
            for f in [key_file, key_file + ".salt"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_key_file_permissions(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "perms.key")
        try:
            MemoryEncryption(key_file=key_file)
            if os.path.exists(key_file):
                mode = os.stat(key_file).st_mode & 0o777
                assert mode == 0o600
        finally:
            for f in [key_file]:
                if os.path.exists(f):
                    os.remove(f)

    def test_derive_key_deterministic(self):
        tmpdir = tempfile.mkdtemp()
        key_file = os.path.join(tmpdir, "derive.key")
        try:
            enc1 = MemoryEncryption(key="same_password", key_file=key_file)
            enc2 = MemoryEncryption(key="same_password", key_file=key_file)

            plaintext = "deterministic test"
            ct1 = enc1.encrypt(plaintext)
            assert enc2.decrypt(ct1) == plaintext
        finally:
            for f in [key_file, key_file + ".salt"]:
                if os.path.exists(f):
                    os.remove(f)


class TestSkillEdgeCases:
    """Cover uncovered branches in rules/skill.py"""

    def test_skill_pack_invalid_name(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="Invalid skill name"):
            skill_pack(rules=rules, name="")

    def test_skill_pack_invalid_name_chars(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="Invalid skill name"):
            skill_pack(rules=rules, name="bad name!")

    def test_skill_pack_invalid_scope(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="Invalid scope"):
            skill_pack(rules=rules, name="test", scope="invalid")

    def test_skill_pack_self_dependency(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="cannot depend on itself"):
            skill_pack(rules=rules, name="self-dep", dependencies=["self-dep"])

    def test_skill_pack_duplicate_dependency(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="Duplicate dependency"):
            skill_pack(rules=rules, name="test", dependencies=["dep1", "dep1"])

    def test_skill_pack_empty_rules(self):
        with pytest.raises(ValueError, match="Cannot pack empty rules"):
            skill_pack(rules=[], name="empty")

    def test_skill_verify_wrong_format(self):
        result = skill_verify({"format": "wrong-format"})
        assert result["valid"] is False
        assert "Unsupported format" in result["reason"]

    def test_skill_verify_no_signature(self):
        result = skill_verify({"format": "carrymem-skill-v1", "rules": []})
        assert result["valid"] is False
        assert "No signature" in result["reason"]

    def test_skill_verify_unsupported_algorithm(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-algo")
        bundle["signature"]["algorithm"] = "md5"
        result = skill_verify(bundle)
        assert result["valid"] is False
        assert "Unsupported algorithm" in result["reason"]

    def test_skill_install_invalid_scope(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "invalid_scope.db")
        try:
            storage = RuleStorage(db_path)
            rules = [Rule(trigger="test", action="a")]
            bundle = skill_pack(rules=rules, name="test")
            bundle["manifest"]["scope"] = "invalid"

            result = skill_install(bundle, storage, scope_override="invalid")
            assert result["installed"] == 0
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_skill_install_missing_dependency(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "missing_dep.db")
        try:
            storage = RuleStorage(db_path)
            rules = [Rule(trigger="test", action="a")]
            bundle = skill_pack(rules=rules, name="dep-test", dependencies=["missing-skill"])

            result = skill_install(bundle, storage)
            assert result["installed"] == 0
            assert "missing_dependencies" in result
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_skill_install_empty_rules(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "empty_rules.db")
        try:
            storage = RuleStorage(db_path)
            bundle = {
                "format": "carrymem-skill-v1",
                "manifest": {"name": "empty", "version": "1.0.0", "scope": "personal", "dependencies": [], "tags": [], "rule_count": 0},
                "signature": {"algorithm": "sha256", "hash": "abc"},
                "rules": [],
                "templates": [],
                "config": {},
            }

            result = skill_install(bundle, storage)
            assert result["installed"] == 0
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_skill_install_rename_mode(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "rename.db")
        try:
            storage = RuleStorage(db_path)
            storage.create(trigger="test", action="a", scope="personal")

            rules = [Rule(trigger="test", action="a")]
            bundle = skill_pack(rules=rules, name="rename-test")

            result = skill_install(bundle, storage, mode="rename")
            assert result["installed"] >= 1
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_skill_install_unknown_mode(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "unknown_mode.db")
        try:
            storage = RuleStorage(db_path)
            storage.create(trigger="test", action="a", scope="personal")

            rules = [Rule(trigger="test", action="a")]
            bundle = skill_pack(rules=rules, name="mode-test")

            result = skill_install(bundle, storage, mode="unknown_mode")
            assert len(result["errors"]) >= 1
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_skill_verify_valid_returns_metadata(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="meta-test", version="2.0.0", author="tester", tags=["t1"])

        result = skill_verify(bundle)
        assert result["valid"] is True
        assert result["name"] == "meta-test"
        assert result["version"] == "2.0.0"
        assert result["author"] == "tester"
        assert result["rule_count"] == 1
        assert "t1" in result["tags"]
