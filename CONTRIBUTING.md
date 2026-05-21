# Contributing to CarryMem

Thank you for your interest in the CarryMem project! We welcome all forms of contributions.

## Development Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -e ".[dev]"       # Core + dev dependencies
pip install -e ".[full]"      # All optional dependencies
pip install -e ".[devsquad]"  # DevSquad integration only
```

### 4. Run Tests

```bash
pytest tests/ -v                                    # All tests
pytest tests/ -v --ignore=tests/test_rules/test_performance.py  # Skip flaky benchmarks
pytest tests/test_carrymem.py::TestENPreference -v  # Specific test
pytest --cov=carrymem tests/    # With coverage
```

**Coverage requirement**: ≥ 80% for new code. CI enforces ≥ 55% overall.

## Code Standards

### Python Code Style

- Follow PEP 8 conventions
- Use 4-space indentation
- Maximum line length: 100 characters
- Use type hints on all public APIs
- No comments in code unless explicitly requested

### Naming Conventions

- Class names: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`
- TypedDict return types: `XxxDict` (e.g., `RuleDict`, `BuildContextResultDict`)

### Docstrings

Use Google-style docstrings on all public classes and methods:

```python
def match(self, scene_description: str, limit: int = 10, increment_count: bool = True) -> list:
    """Find rules matching a given scene.

    Uses multi-strategy matching (global > exact > FTS5 > partial).
    By default, increments trigger_count for matched rules.

    Args:
        scene_description: Natural language description of current context
        limit: Maximum results
        increment_count: If True, increment trigger_count for matched rules

    Returns:
        List of MatchResult objects sorted by relevance
    """
```

## API Stability Policy

Before modifying any public API, check [docs/API_STABILITY.md](docs/API_STABILITY.md):

| Tier | Label | Breaking Changes |
|------|-------|-----------------|
| **Stable** | `@stable` | Only in major version bumps |
| **Experimental** | `@experimental` | With 2-version deprecation notice |
| **Internal** | `@internal` | Any time without notice |

**Rules for contributors**:
- Never change the signature of a `@stable` API without a deprecation path
- New parameters must have defaults that preserve existing behavior
- Mark new public APIs as `@experimental` initially; promotion to `@stable` requires maintainer approval

## Commit Conventions

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `style`: Code formatting
- `refactor`: Refactoring
- `perf`: Performance optimization
- `test`: Test-related
- `chore`: Build/toolchain

**Example**:
```
feat(knowledge): add CJK trigram full-text search

- Replace unicode61 tokenizer with trigram for CJK support
- Auto-migrate existing databases
- Add fallback LIKE search for short queries

Closes #123
```

## Testing Requirements

### 1. Unit Tests

- All new features must have corresponding unit tests
- Test coverage for new code should be ≥ 80%
- Use the pytest framework

```python
def test_match_increments_trigger_count(temp_db):
    engine = RuleEngine(db_path=temp_db)
    engine.add_rule("database", "Use SSL", rule_type="always")
    results = engine.match("database design")
    assert len(results) == 1
    rule = engine.storage.get(results[0].rule.id)
    assert rule.trigger_count == 1
```

### 2. Integration Tests

- Test interactions between multiple modules
- Test real-world usage scenarios
- Mark with `@pytest.mark.integration`

### 3. Performance Tests

- Critical operations should have performance benchmarks
- Mark with `@pytest.mark.slow`
- Ensure no performance regression

## Pull Request Process

### 1. Fork the Repository

Click the "Fork" button on the GitHub page.

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 3. Develop and Test

```bash
# Write code
# Run tests
pytest tests/ -v --ignore=tests/test_rules/test_performance.py
# Check coverage
pytest --cov=carrymem tests/
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
```

### 5. Create Pull Request

Fill in the PR template (see `.github/pull_request_template.md`):
- What changed and why
- Related issues
- Test results
- API stability impact
- Documentation updates

### 6. Code Review

- Maintainers will review your code
- Make changes based on feedback
- All tests must pass
- At least one maintainer approval required before merging

## Project Structure

```
carrymem/
├── src/carrymem/
│   ├── carrymem.py              # Main entry point
│   ├── async_carrymem.py        # Async wrapper
│   ├── engine.py                # Classification engine
│   ├── api_types.py             # TypedDict return types
│   ├── adapters/                # Storage adapters
│   │   ├── sqlite_adapter.py    # Default storage
│   │   ├── obsidian_adapter.py  # Knowledge vault (read-only)
│   │   └── json_adapter.py      # JSON export
│   ├── rules/                   # Rules Engine
│   │   ├── models.py            # Rule dataclass
│   │   ├── storage.py           # Rule persistence
│   │   ├── matcher.py           # Multi-strategy matching
│   │   ├── injector.py          # Context injection (anchored/ddd)
│   │   └── ...                  # promotion, refinement, experience
│   ├── security/                # Input validation & audit
│   ├── integration/             # External integrations
│   │   ├── layer2_mcp/          # MCP server
│   │   └── devsquad/            # DevSquad adapter
│   ├── semantic/                # Semantic expansion
│   ├── context/                 # Context building
│   └── utils/                   # Utility functions
├── tests/                       # Test files
├── docs/                        # Documentation
│   ├── API_REFERENCE.md
│   ├── API_STABILITY.md
│   └── ROADMAP.md
├── .github/                     # CI & templates
└── pyproject.toml               # Build configuration
```

## Development Guide

### Adding a New Storage Adapter

1. Create a new adapter in `adapters/` inheriting from `StorageAdapter`
2. Implement `remember()`, `recall()`, `forget()`, `get_stats()`
3. Register in `adapters/loader.py` (`_BUILTIN_ADAPTERS`)
4. Add to `adapters/__init__.py` exports
5. Add test cases in `tests/`

### Adding a New Rule Feature

1. Extend `rules/models.py` if the Rule dataclass needs new fields
2. Update `rules/storage.py` schema and CRUD methods
3. Update `rules/matcher.py` or `rules/injector.py` as needed
4. Mark new public API as `@experimental` in `docs/API_STABILITY.md`
5. Add test cases in `tests/test_rules/`

### Adding a New Integration Adapter

1. Create a new package under `integration/`
2. Define `Protocol` classes in `protocol.py`
3. Implement adapter in `adapter.py`
4. Add to `pyproject.toml` optional-dependencies
5. Add test cases

## FAQ

### Q: How to run specific tests?

```bash
pytest tests/test_carrymem.py::TestENPreference -v
```

### Q: How to check test coverage?

```bash
pytest --cov=carrymem tests/
```

### Q: How to debug tests?

```bash
pytest tests/ -v -s  # -s shows print output
pytest tests/ --pdb  # Enter debugger on failure
```

### Q: How to add a new TypedDict return type?

1. Define in `api_types.py` with `total=False` for optional fields
2. Add to `__init__.py` exports and `__all__`
3. Document in `docs/API_REFERENCE.md` TypedDict table

## Code of Conduct

- Respect all contributors
- Be friendly and professional
- Accept constructive criticism
- Focus on project goals

## License

By contributing code, you agree that your contributions will be released under the MIT License.

---

**Thank you for your contributions!**
