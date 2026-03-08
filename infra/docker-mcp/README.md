# Docker MCP Pilot - Proof of Concept

> **Phase:** 1 - Pilot (2 weeks)
> **Date:** 2026-01-04
> **Status:** Ready for testing
> **Goal:** Validate Docker MCP Gateway with 5 simple NPX wrappers

---

## Quick Start

```bash
# Start pilot
.\scripts\start-pilot.bat

# Check status
.\scripts\status-pilot.bat

# View logs
docker-compose logs -f

# Stop pilot
.\scripts\stop-pilot.bat
```

---

## What is This?

**Docker MCP Pilot** is a proof-of-concept implementation of Docker MCP Gateway for 1C-Enterprise_Framework.

### Problem Being Solved

| Issue | Current State | After Docker MCP |
|-------|---------------|------------------|
| **Startup time** | 30-60 sec | **5-10 sec** ⭐ |
| **Context tokens** | ~372k | **~20k** ⭐ |
| **Management** | 33 manual configs | **1 docker-compose** ⭐ |
| **Logs** | Fragmented | **Centralized** ⭐ |

### Pilot Scope

**Phase 1** tests Docker MCP with **5 simple servers**:

| Server | Type | Purpose | Tokens |
|--------|------|---------|--------|
| **filesystem** | NPX | File operations | 2k |
| **sqlite** | NPX | Database ops | 3k |
| **sequential-thinking** | NPX | Reasoning | 6k |
| **ripgrep** | NPX | File search | 5k |
| **memory** | NPX | JSON storage | 4k |

**Total:** ~20k tokens (vs 372k pre-load!)

---

## Project Structure

```
docker-mcp-pilot/
├── docker-compose.yml      # Main configuration
├── registry/
│   └── tool-registry.json  # Dynamic tool index
├── scripts/
│   ├── start-pilot.bat     # Start all services
│   ├── stop-pilot.bat      # Stop all services
│   └── status-pilot.bat    # Check status
└── README.md               # This file
```

---

## Prerequisites

- ✅ Docker Desktop 4.42+ (Windows)
- ✅ Docker Compose v2.40+
- ✅ Node.js 18+ (in containers)
- ✅ 1GB free disk space

**Verified:**
```
Docker version: 28.5.2
Docker Compose: v2.40.3-desktop.1
```

---

## Usage

### Starting the Pilot

```bash
.\scripts\start-pilot.bat
```

**Output:**
```
========================================
Docker MCP Pilot - Starting...
========================================

[INFO] Docker is running
[INFO] Current directory: D:\1C-Enterprise_Framework\docker-mcp-pilot

[INFO] Starting pilot MCP services...

Creating mcp-filesystem        ... done
Creating mcp-sqlite            ... done
Creating mcp-sequential-thinking ... done
Creating mcp-ripgrep           ... done
Creating mcp-memory            ... done

========================================
Docker MCP Pilot - Started!
========================================

Services:
NAME                     STATUS          PORTS
mcp-filesystem           Up (healthy)    0.0.0.0:->/tcp
mcp-sqlite               Up (healthy)    0.0.0.0:->/tcp
mcp-sequential-thinking  Up (healthy)    0.0.0.0:->/tcp
mcp-ripgrep              Up (healthy)    0.0.0.0:->/tcp
mcp-memory               Up (healthy)    0.0.0.0:->/tcp
```

### Checking Status

```bash
.\scripts\status-pilot.bat
```

Shows:
- Container status
- Health check status
- Resource usage (CPU/Memory)
- Recent logs

### Viewing Logs

```bash
# All logs
docker-compose logs -f

# Specific container
docker logs -f mcp-filesystem

# Last 20 lines
docker-compose logs --tail 20
```

### Monitoring UI (Optional)

```bash
# Start monitoring
docker-compose --profile monitoring up -d

# Open UI
# http://localhost:8080
```

Shows real-time logs from all containers.

### Stopping the Pilot

```bash
.\scripts\stop-pilot.bat
```

---

## Tool Registry

**Dynamic loading** is configured in `registry/tool-registry.json`:

```json
{
  "version": "1.0.0",
  "registry": {
    "filesystem": {
      "name": "Filesystem Operations",
      "tools": ["read_file", "write_file", "list_directory"],
      "estimatedTokens": 2000
    },
    "sqlite": {
      "name": "SQLite Database",
      "tools": ["execute_query", "list_tables", "get_schema"],
      "estimatedTokens": 3000
    }
  },
  "pilotPhase": {
    "servers": ["filesystem", "sqlite", "sequential-thinking", "ripgrep", "memory"],
    "totalEstimatedTokens": 20000,
    "loadStrategy": "on-demand",
    "unloadStrategy": "lru"
  }
}
```

---

## Success Criteria

### Phase 1 (Pilot) Success Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| **All containers healthy** | 5/5 | ⏳ Pending |
| **Startup time** | < 30 sec | ⏳ Pending |
| **Context usage** | ~20k tokens | ⏳ Pending |
| **No errors in logs** | 0 errors | ⏳ Pending |
| **Stable 2 weeks** | No crashes | ⏳ Pending |

### Performance Benchmarks

Run these tests after startup:

```bash
# 1. Startup time
time docker-compose up -d

# 2. Memory usage
docker stats --no-stream

# 3. Tool availability
# Test each tool via Claude Code

# 4. Compare with native setup
# Measure context token usage
```

---

## Troubleshooting

### Port Conflicts

```bash
# Check what's using port
netstat -ano | findstr :8080

# Kill process
taskkill /F /PID <PID>
```

### Container Won't Start

```bash
# Check logs
docker logs mcp-<server-name>

# Rebuild
docker-compose up -d --force-recreate

# Clean restart
docker-compose down -v
docker-compose up -d
```

### Health Check Failing

```bash
# Inspect health
docker inspect mcp-filesystem | findstr Health

# Check container
docker exec -it mcp-filesystem sh
```

---

## Next Steps

### After Pilot Success (Go to Phase 2)

If pilot passes all success criteria:

1. **Phase 2 (4 weeks):** Hybrid setup
   - Add 8-10 medium-complexity servers
   - Keep critical (unified-memory, 1c-docs-rag) native
   - Parallel Docker + native operation

2. **Phase 3 (6 weeks):** Full migration
   - All 33 servers in Docker
   - Including complex dependencies (Neo4j, Qdrant, etc.)
   - Single `docker-compose up` command

### If Pilot Fails (No-Go)

1. Investigate failure root cause
2. Fix issue
3. Re-test pilot
4. OR rollback to native setup

---

## Documentation

- **Full Analysis:** `Проекты/docker-mcp-analysis/DOCKER-MCP-ANALYSIS.md`
- **Dynamic MCP:** `Проекты/docker-mcp-analysis/DYNAMIC-MCP-EXPLAINED.md`
- **MCP Registry:** `docs/framework/mcp-servers/COMPLETE-MCP-REGISTRY.md`

---

## Support

**Issues?** Check:
1. Docker is running: `docker ps`
2. Ports are free: `netstat -ano`
3. Logs: `docker-compose logs -f`

**Still stuck?**
- Check `../Проекты/docker-mcp-analysis/` for troubleshooting
- Review Docker logs: `Docker Desktop Dashboard > Logs`

---

**Version:** 1.0.0
**Created:** 2026-01-04
**Author:** Claude Code
**License:** MIT
