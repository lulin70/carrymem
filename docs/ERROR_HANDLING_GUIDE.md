# CarryMem Error Handling Guide

> **Status**: Active · **Version**: 1.0 · **Last Updated**: 2026-07-18
>
> This guide defines the canonical error handling patterns for the CarryMem codebase.
> All new code MUST follow this guide. Existing code should be migrated when touched.

## 1. Principles

1. **Be specific** — Catch the narrowest exception type that you can actually handle.
2. **Don't swallow** — Never use bare `except:` or `except Exception: pass` without logging.
3. **Fail loud at boundaries** — At system boundaries (CLI, MCP, HTTP), translate exceptions to user-facing messages; internally, let them propagate.
4. **Log once** — Log the exception at the handling point, not at every re-raise.
5. **Preserve context** — Use `raise ... from e` to preserve the original traceback.

## 2. Exception Hierarchy

```
BaseException
└── Exception
    ├── CarryMemError                    # Base for all CarryMem exceptions
    │   ├── StorageNotConfiguredError    # Lifecycle not initialized
    │   ├── ValidationError              # Input validation failed
    │   ├── AuthenticationError          # Auth/token failures
    │   ├── AuthorizationError           # Permission denied
    │   └── RateLimitError               # Throttling
    ├── OSError
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   └── ConnectionError
    ├── json.JSONDecodeError
    ├── sqlite3.Error
    │   ├── sqlite3.OperationalError
    │   └── sqlite3.IntegrityError
    ├── ValueError
    ├── TypeError
    ├── KeyError
    └── asyncio.CancelledError
```

## 3. Decision Matrix

| Situation | Pattern | Example |
|-----------|---------|---------|
| **System boundary (CLI/MCP/HTTP)** | Catch broad, translate to user message, log | `except Exception as e: logger.error(...); return {"error": str(e)}` |
| **Resource cleanup** | `try/finally` or context manager | `with open(path) as f: ...` |
| **Optional feature** | Catch specific, degrade gracefully | `except ImportError: feature = None` |
| **Expected absence** | Catch `FileNotFoundError`, return default | `except FileNotFoundError: return None` |
| **Data parsing** | Catch `ValueError`/`JSONDecodeError`, log & skip | `except json.JSONDecodeError as e: logger.warning(...); continue` |
| **Database operations** | Catch `sqlite3.Error`, rollback, re-raise | `except sqlite3.Error: conn.rollback(); raise` |
| **Async cancellation** | Never catch `asyncio.CancelledError` except to cleanup | `except asyncio.CancelledError: cleanup(); raise` |

## 4. Forbidden Patterns

### 4.1 Bare `except:` (NEVER)

```python
# BAD — catches SystemExit, KeyboardInterrupt
try:
    do_something()
except:
    pass

# GOOD — catch specific exceptions
try:
    do_something()
except (ValueError, TypeError) as e:
    logger.warning("Invalid input: %s", e)
```

### 4.2 `except Exception: pass` (NEVER without log)

```python
# BAD — silently swallows all exceptions
try:
    risky_operation()
except Exception:
    pass

# GOOD — log and decide
try:
    risky_operation()
except Exception as e:
    logger.error("risky_operation failed: %s", e, exc_info=True)
    # Either re-raise, return default, or continue
```

### 4.3 Catching without using the variable (WARN)

```python
# WARN — catching but not using the exception
try:
    parse(data)
except ValueError:
    return None  # Lost the error message

# GOOD — include context in log or return value
try:
    parse(data)
except ValueError as e:
    logger.debug("parse failed: %s", e)
    return None
```

## 5. Required Patterns

### 5.1 System Boundary (CLI commands)

```python
def cmd_xxx(args: list[str]) -> int:
    try:
        # business logic
        return 0
    except CarryMemError as e:
        print(f"  Error: {e.message}")
        return e.code
    except (OSError, ValueError) as e:
        print(f"  Error: {e}")
        return 1
    except Exception as e:
        logger.error("Unexpected error in cmd_xxx: %s", e, exc_info=True)
        print(f"  Unexpected error: {e}")
        return 1
```

### 5.2 MCP Handlers

```python
def handle_xxx(engine, args):
    try:
        # business logic
        return {"success": True, ...}
    except ValidationError as e:
        return {"success": False, "error": str(e), "code": "VALIDATION_ERROR"}
    except Exception as e:
        logger.error("handle_xxx failed: %s", e, exc_info=True)
        return {"success": False, "error": "Internal error", "code": "INTERNAL"}
```

### 5.3 Database Operations

```python
def update_record(conn, record):
    try:
        conn.execute("UPDATE ...", record)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise  # Let caller decide
    except sqlite3.OperationalError as e:
        conn.rollback()
        logger.error("DB operation failed: %s", e)
        raise
```

### 5.4 File I/O

```python
# Preferred: context manager (auto-cleanup)
def read_config(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.debug("Config not found at %s, using defaults", path)
        return {}
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in %s: %s", path, e)
        return {}
    except PermissionError as e:
        logger.error("Cannot read %s: %s", path, e)
        raise
```

## 6. Logging Guidelines

| Level | When to use |
|-------|-------------|
| `logger.debug` | Expected absence (file not found, empty result) |
| `logger.info` | Normal operation milestones |
| `logger.warning` | Recoverable errors, degraded mode |
| `logger.error` | Unrecoverable errors, user-facing failures |
| `logger.exception` | Unexpected exceptions with traceback (equivalent to `logger.error(..., exc_info=True)`) |

**Rule**: Use `logger.exception()` sparingly — only for truly unexpected exceptions. For expected error paths, use `logger.warning()` or `logger.error()` without `exc_info`.

## 7. Testing Error Handling

- **Every `except` block must have a test** that triggers it.
- Use `pytest.raises(SpecificException)` to verify exceptions propagate correctly.
- For system boundaries, test that user-facing messages are helpful (not raw tracebacks).
- Never mock exceptions away — test the real exception handling path.

## 8. Migration Checklist

When touching existing code:

- [ ] Replace bare `except:` with specific exception types
- [ ] Add logging to silent `except: pass` blocks
- [ ] Use `raise ... from e` when re-raising
- [ ] Verify all `except` blocks have tests
- [ ] Update docstrings to document raised exceptions

## 9. Review Checklist

For code reviewers:

- [ ] No bare `except:` or `except Exception: pass`
- [ ] Exception types are specific (not overly broad)
- [ ] Errors are logged (not silently swallowed)
- [ ] System boundaries translate exceptions to user messages
- [ `raise ... from e` used when re-raising
- [ ] New `except` blocks have corresponding tests
