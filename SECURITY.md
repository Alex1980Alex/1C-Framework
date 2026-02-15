# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.5.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately:

1. Do NOT create a public GitHub issue
2. Send details to the repository maintainer
3. Include: description, steps to reproduce, potential impact

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Security Considerations

- API keys and secrets should be stored in `.env` (never committed to git)
- JWT tokens have configurable expiration (`AUTH__TOKEN_EXPIRE_HOURS`)
- RBAC roles: `viewer` (read-only), `editor` (read+write), `admin` (full access)
- CORS origins should be restricted in production (`API__CORS_ORIGINS`)
- Rate limiting is available via middleware
