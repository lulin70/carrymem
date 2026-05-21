"""
Test Suite for Rule Templates

Validates:
- Template registry completeness
- get_template() retrieval and error handling
- list_templates() output format
- Template field consistency
"""

import pytest

from carrymem.rules.templates import (
    RULE_TEMPLATES,
    get_template,
    list_templates,
)


class TestTemplateRegistry:
    """Test template registry structure and completeness"""

    def test_minimum_template_count(self):
        """Should have at least 10 templates"""
        assert len(RULE_TEMPLATES) >= 10

    def test_all_templates_have_required_fields(self):
        """Each template must have trigger, action, rule_type, override, description"""
        required_fields = {"trigger", "action", "rule_type", "override", "description"}
        for name, tmpl in RULE_TEMPLATES.items():
            missing = required_fields - set(tmpl.keys())
            assert not missing, f"Template '{name}' missing fields: {missing}"

    def test_all_rule_types_valid(self):
        """Each template rule_type must be a valid type"""
        valid_types = {"avoid", "always", "prefer", "forbid", "format"}
        for name, tmpl in RULE_TEMPLATES.items():
            assert tmpl["rule_type"] in valid_types, (
                f"Template '{name}' has invalid rule_type: {tmpl['rule_type']}"
            )

    def test_override_is_boolean(self):
        """Each template override must be boolean"""
        for name, tmpl in RULE_TEMPLATES.items():
            assert isinstance(tmpl["override"], bool), (
                f"Template '{name}' override is not boolean: {tmpl['override']}"
            )

    def test_trigger_not_empty(self):
        """Each template trigger must be non-empty string"""
        for name, tmpl in RULE_TEMPLATES.items():
            assert isinstance(tmpl["trigger"], str) and len(tmpl["trigger"].strip()) > 0, (
                f"Template '{name}' has empty trigger"
            )

    def test_action_not_empty(self):
        """Each template action must be non-empty string"""
        for name, tmpl in RULE_TEMPLATES.items():
            assert isinstance(tmpl["action"], str) and len(tmpl["action"].strip()) > 0, (
                f"Template '{name}' has empty action"
            )

    def test_description_not_empty(self):
        """Each template description must be non-empty string"""
        for name, tmpl in RULE_TEMPLATES.items():
            assert isinstance(tmpl["description"], str) and len(tmpl["description"].strip()) > 0, (
                f"Template '{name}' has empty description"
            )


class TestGetTemplate:
    """Test get_template() function"""

    def test_get_existing_template(self):
        """Should return template dict for valid name"""
        tmpl = get_template("code-review")
        assert tmpl["trigger"] == "代码评审"
        assert tmpl["rule_type"] == "always"
        assert tmpl["override"] is True

    def test_get_all_templates(self):
        """Should be able to retrieve every registered template"""
        for name in RULE_TEMPLATES:
            tmpl = get_template(name)
            assert "trigger" in tmpl
            assert "action" in tmpl

    def test_get_nonexistent_template_raises_keyerror(self):
        """Should raise KeyError for unknown template name"""
        with pytest.raises(KeyError, match="Template 'nonexistent' not found"):
            get_template("nonexistent")

    def test_error_message_lists_available_templates(self):
        """KeyError message should list available template names"""
        with pytest.raises(KeyError, match="code-review") as exc_info:
            get_template("invalid-name")
        error_msg = str(exc_info.value)
        assert "code-review" in error_msg
        assert "security-first" in error_msg


class TestListTemplates:
    """Test list_templates() function"""

    def test_returns_dict(self):
        """Should return a dictionary"""
        result = list_templates()
        assert isinstance(result, dict)

    def test_count_matches_registry(self):
        """Number of entries should match RULE_TEMPLATES"""
        result = list_templates()
        assert len(result) == len(RULE_TEMPLATES)

    def test_values_are_descriptions(self):
        """Each value should be the template description string"""
        result = list_templates()
        for name, desc in result.items():
            assert desc == RULE_TEMPLATES[name]["description"]

    def test_keys_are_template_names(self):
        """Each key should be a template name"""
        result = list_templates()
        assert set(result.keys()) == set(RULE_TEMPLATES.keys())


class TestTemplateSpecificContent:
    """Test specific template content for correctness"""

    def test_code_review_template(self):
        """Code review template should enforce always-check"""
        tmpl = get_template("code-review")
        assert tmpl["rule_type"] == "always"
        assert tmpl["override"] is True

    def test_no_shortcut_template_is_forbid(self):
        """No-shortcut template should be forbid type"""
        tmpl = get_template("no-shortcut")
        assert tmpl["rule_type"] == "forbid"

    def test_tech_selection_template_is_prefer(self):
        """Tech selection template should be prefer type"""
        tmpl = get_template("tech-selection")
        assert tmpl["rule_type"] == "prefer"
        assert tmpl["override"] is False

    def test_report_format_template(self):
        """Report format template should be format type"""
        tmpl = get_template("report-format")
        assert tmpl["rule_type"] == "format"

    def test_competitor_analysis_template(self):
        """Competitor analysis template should enforce verification"""
        tmpl = get_template("competitor-analysis")
        assert tmpl["rule_type"] == "always"
        assert "待验证" in tmpl["action"] or "Unverified" in tmpl["description"]
