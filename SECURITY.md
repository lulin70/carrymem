# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in CarryMem, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. **Email**: Send details to the maintainers via GitHub's private vulnerability reporting
2. **GitHub Security Advisory**: Use [GitHub's security advisory feature](https://github.com/lulin70/carrymem/security/advisories/new)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Fix Timeline**: Critical issues within 7 days, others within 30 days

## Security Architecture

### Data Isolation

CarryMem stores all data locally in `~/.carrymem/`. Each user has an independent SQLite database. No data is transmitted to external servers.

### Encryption

- **At-rest encryption**: Optional Fernet-based encryption for stored memories
- **USB carry encryption**: AES-256-like stream cipher with HMAC-SHA256 authentication for portable `.carry` files
- **Key management**: Keys derived via PBKDF2-HMAC-SHA256 with 100,000 iterations

### Input Validation

- All user inputs are validated through `InputValidator` before storage
- SQL injection protection via parameterized queries (no string interpolation)
- XSS pattern detection for web-context safety
- Auto-redaction of sensitive content (API keys, passwords, tokens)

### Audit Logging

- All memory operations are logged to an append-only `audit_log` table
- Timestamps use ISO 8601 with UTC timezone
- Audit logs cannot be modified or deleted

### MCP Protocol Security

- MCP server runs via stdio (no network exposure)
- No remote code execution capabilities
- Tool operations are scoped to the user's local data directory

## Known Security Considerations

1. **Encryption key storage**: The encryption key is stored as a file on disk. An attacker with file system access can decrypt stored memories. For higher security, consider using a hardware key store.

2. **Memory dumps**: Decrypted data may briefly exist in process memory. This is inherent to any software that processes encrypted data.

3. **Local-only model**: CarryMem does not encrypt data in transit because all operations are local (stdio MCP). If you expose CarryMem over a network, you must add transport-layer encryption.
