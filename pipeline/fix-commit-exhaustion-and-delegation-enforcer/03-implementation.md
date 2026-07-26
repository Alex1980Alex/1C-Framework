# 03. Кодирование

## A. Память

- Создан `%USERPROFILE%\.wslconfig` (файла не было → WSL брал до 50% RAM). Применение подтверждено:
  `docker info --format '{{.MemTotal}}'` = **23.47 GiB** (было 30.18).
- MSSQL: `sp_configure 'max server memory (MB)', 12288` + `RECONFIGURE`, `value_in_use` подтверждён.
  ⚠ `sqlcmd` в момент правки не стартовал (`Starting the CLR failed with HRESULT 80004005`) - это тот же
  дефицит памяти; обошли через `System.Data.SqlClient` из PowerShell (не требует запуска отдельного процесса).

Замеры commit charge: **124.9 / 129.1 ГБ (свободно 4.2)** → после `wsl --shutdown` 89.2 → после возврата
всех контейнеров и лимита MSSQL **116.4 / 127.1 (свободно 10.6)**. `sqlservr` 18.07 → 12.34 ГБ.

### Побочный ущерб и его устранение

`wsl --shutdown` уронил все 13 контейнеров. 12 вернулись сами (`restart=unless-stopped`), два потребовали рук:

- **pdf-rag-tei** ушёл в вечный `CUDA_ERROR_OUT_OF_MEMORY`. Корень - не нехватка VRAM, а самоотравление:
  политика перезапуска стартовала новую попытку (запрос ~16 ГБ под Qwen3-8B) раньше, чем возвращалась
  память предыдущей. `docker stop` разорвал цикл (занято 19550 → 3986 МиБ), чистый старт занял ~108 с.
  Итог: 19.3 ГБ VRAM = Qwen3-8B + `bge-reranker-v2-m3` уживаются штатно, как и до инцидента.
- **langfuse-web** не поднялся сам. По `data/mcp-health.jsonl`: `ok=True` в 16:53, `ok=False` с 17:10 -
  то есть уронил его именно перезапуск. Вылечен `docker restart langfuse-web`.

Финал: пробник проекта `scripts/probe_mcp_health.py` → **14/14 up**.

## B. Хук

`.claude/hooks/z-ai-delegation-enforcer.py`: возвращены **четыре** метода (потерян был весь блок, не один):
`_bandit_level`, `_router_level`, `_should_canary`, `_delegation_level`. Плюс env-гейт телеметрии по дизайну B.2.

Ключевая находка при реализации: вызов `_delegation_level` стоит **до** проверок orchestrator/hard/medium,
поэтому мёртвыми были **все** ветки советов, а не только бандит - хук два месяца не выдавал вообще ничего.

`CLAUDE.md`: запись о дефекте, замерах и уроке наблюдаемости (`outcome=error` копился два месяца без читателя).

Коммит: `00796524d` (auto-save, 3 файла, +270 строк).
