# ADR-011: Fernet-Only Encryption (Supersedes ADR-003)

**Status**: Accepted
**Date**: 2026-07-13 (v0.7.3)
**Supersedes**: [ADR-003](ADR-003-dual-backend-encryption.md)
**Decision Maker**: Architect role

## Context

ADR-003 established a dual-backend encryption strategy with three security levels:
- `strong`: Fernet (AES-128-CBC + HMAC) via `cryptography` package
- `weak`: HMAC-CTR stream cipher (fallback when `cryptography` is not installed)
- `none`: No encryption (testing only)

The `cryptography` package was optional, and the system would automatically degrade to the HMAC-CTR stream cipher when it was unavailable.

## Problem

1. **Security risk**: The HMAC-CTR stream cipher is a custom implementation with weaker security guarantees than Fernet. It was intended as a fallback for environments where `cryptography` cannot be installed, but this scenario is rare in practice.

2. **Complexity**: Maintaining two encryption backends increases code complexity, testing burden, and the attack surface.

3. **User confusion**: Users may unknowingly run with the weaker cipher, believing their data is strongly encrypted.

4. **Dependency management**: The optional dependency pattern makes it harder to reason about the security posture of a given installation.

## Decision

**Remove the HMAC-CTR stream cipher fallback entirely. `cryptography` becomes a hard dependency.**

### Changes

1. `cryptography>=46.0.6` is now in `install_requires` (not `extras_require["encryption"]`)
2. `MemoryEncryption` only supports `strong` (Fernet) and `none` (testing only)
3. The `security_level` parameter no longer accepts `"weak"`
4. A migration script (`scripts/migrate_encryption.py`) is provided for users upgrading from v0.7.2 or earlier
5. The `NoEncryption` class is retained for testing purposes only

### Rationale

- Fernet is the industry standard for symmetric encryption in Python
- `cryptography` is a well-maintained, audited package available on all major platforms
- Removing the custom cipher reduces the attack surface and maintenance burden
- Breaking change is justified by the security improvement

## Consequences

- **Breaking change**: Users with `security_level="weak"` must migrate to `"strong"` using the migration script
- **New dependency**: `cryptography` must be installed; `pip install carrymem` now includes it automatically
- **Simplified API**: `MemoryEncryption` constructor no longer needs to handle the fallback logic
- **Improved security**: All production data is now encrypted with Fernet (AES-128-CBC + HMAC)

## Migration Guide

1. Install v0.7.3+: `pip install --upgrade carrymem`
2. Run the migration script: `python scripts/migrate_encryption.py --data-dir <your_data_dir>`
3. The script will:
   - Create a backup of your existing database (VACUUM INTO)
   - Decrypt all data using the old HMAC-CTR cipher
   - Re-encrypt using Fernet
   - Verify the migration

## Implementation References

- `src/carrymem/security/encryption.py`: Fernet-only implementation (lines 1-21 document the v0.7.3+ strategy)
- `setup.py:94`: `cryptography>=46.0.6` in `install_requires`
- `scripts/migrate_encryption.py`: Migration script for v0.7.2 → v0.7.3+
- `CHANGELOG.md`: v0.7.3 release notes (lines 60-78)

## Review

This decision was reviewed and accepted during the v0.7.3 security hardening sprint. The breaking change was deemed acceptable given the security improvement and the availability of a migration script.
