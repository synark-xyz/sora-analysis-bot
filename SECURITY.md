# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by:

1. **Opening a GitHub Security Advisory** at https://github.com/synark-xyz/noor-telegram-bot/security/advisories
2. **Opening an issue** with the label `security` (for non-critical concerns)

Please do **not** report security vulnerabilities through public GitHub issues for critical issues.

## Scope

This project is a personal-use trading signal bot. The following are in scope:

- Code vulnerabilities (injection, authentication bypass, data exposure)
- Credential leaks in git history or committed files
- Dependency vulnerabilities

The following are **out of scope**:

- API keys stored in `.env` files (these are user-managed and gitignored)
- Rate limiting or API abuse of third-party services (Alpaca, OpenRouter, Binance)
- Phishing or social engineering attacks

## Expectations

- You will receive an acknowledgment within 48 hours
- We will investigate and provide a timeline for a fix
- We ask that you allow reasonable time for a fix before public disclosure

## Best Practices for Contributors

- **Never commit API keys, tokens, or secrets** — use `.env` files (gitignored)
- Run `git log -p | grep -i "key\|token\|secret"` before pushing to check for leaks
- If a secret was accidentally committed, rotate it immediately and rebase the commit from history
