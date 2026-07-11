"""Pytest configuration shared across all test modules.

Auto-applies a longer timeout (600s) to slow-marked tests so they don't fail
when running the full suite locally with --timeout=120. CI excludes slow tests
via `-m "not slow"`, so this hook has no CI impact.
"""

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        slow_marker = item.get_closest_marker("slow")
        if slow_marker:
            item.add_marker(pytest.mark.timeout(600))
