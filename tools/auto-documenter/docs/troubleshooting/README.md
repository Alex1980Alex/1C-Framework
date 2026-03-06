# Troubleshooting

This directory contains troubleshooting guides and debugging information.

## Files

### README-RUN.md (182 lines)
Comprehensive guide for running and debugging the MCP server:
- Architecture overview
- Configuration via `run-autodoc.bat`
- Available tools (generate_documentation, generate_test_plan, review_code)
- Project structure explanation
- Debugging checklist
- Common problems and solutions
- API keys and provider limits

## Common Issues

### 1. "OpenRouter API key is required"

**Cause:** Environment variable `ENABLE_ROTATION` not set correctly

**Solution:**
1. Check `run-autodoc.bat` contains `set ENABLE_ROTATION=true`
2. Ensure MCP config launches the batch file, not node directly
3. Test with `test-with-env.bat` to verify variables

### 2. "Provider GEMINI failed"

**Cause:** Invalid API key or daily limit exceeded

**Solution:**
1. Verify API key in `run-autodoc.bat`
2. System will automatically fallback to Groq/Ollama
3. Get new API key: https://ai.google.dev/

### 3. Server won't start

**Troubleshooting steps:**
1. Check Node.js is in PATH: `node --version`
2. Verify build directory exists: `cd build && ls`
3. Rebuild if needed: `npm run build`
4. Check MCP server status in Claude Code

### 4. TypeScript compilation errors

**Known issue:** `gitignore.ts` has import errors

**Workaround:**
```bash
# Use existing build if available
# OR compile with --skipLibCheck:
npx tsc --skipLibCheck && node -e "require('fs').chmodSync('build/index.js', '755')"
```

## Debugging

### Check MCP Status
In Claude Code, verify server status:
```
✓ auto-documenter    running
```

### View Logs
Server outputs to console:
```
✅ Using provider: GEMINI (model: gemini-2.5-flash-lite)
Autodocument MCP server running on stdio
```

### Test Environment Variables
Run `test-with-env.bat`:
```
ENABLE_ROTATION: true
PRIMARY_PROVIDER: gemini
GEMINI_API_KEY: ***SET***
```

## Provider Limits

| Provider | Free Limit | Notes |
|----------|------------|-------|
| **Gemini** | 1,500 req/day | 60 req/minute |
| **Groq** | 500k tokens/day | 30 req/minute |
| **Ollama** | Unlimited | Local, requires installation |
| **Grok** | Paid | No free tier |
| **OpenRouter** | Paid | Fallback only |

## Getting Help

1. Check logs in MCP server output
2. Review configuration in `claude_desktop_config.json`
3. Test with minimal config (Gemini only)
4. Verify API keys are valid
5. Check provider status pages

## Related Documentation

- **Guides:** [../guides/](../guides/) - Setup instructions
- **Architecture:** [../architecture/](../architecture/) - System design
- **Development:** [../development/](../development/) - Technical issues
