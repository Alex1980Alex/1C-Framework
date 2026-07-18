# ADR-052: OTel→Langfuse — топология, ретеншн, безопасность (тяжёлый путь tool-observability)

- **Статус:** accepted
- **Дата:** 2026-07-18
- **Исследование:** [`langfuse-llm-observability-2026`](../cache/langfuse-llm-observability-2026.md), [`tool-call-observability-effectiveness-2026`](../cache/tool-call-observability-effectiveness-2026.md) (EMPIRICAL ground-truth нативной эмиссии), официальный self-host compose (langfuse/langfuse main).
- **Контекст-источник:** roadmap [260718 H-P0.2](../../../../docs/roadmap/260718_ROADMAP_OTEL_LANGFUSE_HEAVY_PATH.md); предшественник [ADR-051](051-tool-observability-heavy-path-gating.md) (триггер сработал), [ADR-022](022-tool-call-observability-effectiveness.md) P2 (коллектор уже развёрнут).

## Контекст

Тяжёлый путь активирован (мандат пользователя = триггер ADR-051). H-P1 расширил
существующий otel-collector file-exporter'ом (сырец в `data/otel/`, кормит cross-check
H-P3). H-P2 добавляет дашборд-слой (Langfuse self-host) + LLM-judge (H-P4). ADR-051
требовал перед подъёмом инфраструктуры зафиксировать топологию, ретеншн и безопасность —
это ADR.

## Решение

### Топология

```
Claude Code (нативный OTLP, opt-in env в settings.local.json)
  │ http/protobuf → localhost:4318
  ▼
otel-collector (уже развёрнут, ADR-022 P2 + H-P1)
  ├─ file/logs, file/traces → data/otel/*.jsonl   (H-P1: cross-check H-P3, БЕЗ Langfuse)
  ├─ debug                  → docker logs          (ADR-022: верификация эмиссии)
  └─ otlphttp → Langfuse /api/public/otel          (H-P2: дашборды; overlay-конфиг)
       ▼
Langfuse self-host (docker/docker-compose.langfuse.yml, opt-in)
  web+worker + postgres + clickhouse + redis + minio (6 контейнеров)
```

Коллектор — **единственная точка fan-out**: у Claude Code ОДИН OTLP-endpoint, поэтому
и файл-сырец (H-P3), и Langfuse (H-P2) кормятся из коллектора, а не двумя экспортами клиента.
Langfuse-ветка — отдельный overlay-конфиг (`otel-collector-langfuse.yaml`): при поднятом
Langfuse коллектор форвардит; когда Langfuse не нужен — базовый конфиг без этой ветки
(коллектор не спамит ошибками connection-refused).

### Нагрузка (оценка — почему opt-in, а не default-on)

| Компонент | Ресурс | Нота |
|---|---|---|
| ClickHouse | ~1-2 ГБ RAM | аналитический стор Langfuse; тяжелейший |
| Postgres + Redis + MinIO | ~0.5 ГБ суммарно | метаданные / очередь / S3-хранилище событий |
| langfuse-web + worker | ~0.5 ГБ | Node-сервисы |
| **Итого +6 контейнеров** | **~2.5-3 ГБ RAM** | поверх 7 живых (TEI/Qdrant/Sonar/Neo4j/…) |

Машина: 24 CPU (из лога коллектора) — CPU не узкое место; RAM — ограничитель. Вывод:
**Langfuse НЕ default-on** — поднимается по требованию (`langfuse_up.py`), не автостартом
с ОС. **Cross-check H-P3 не зависит от Langfuse** (работает по file-сырцу) → тяжёлый стор
не на критическом пути. Fallback при нехватке RAM — остаться на file+DuckDB.

### Ретеншн

- **Langfuse** (ClickHouse): встроенного TTL-джоба в этом ADR не заводим — для локального
  dev-инструмента retention-политику применяем вручную/по потребности (данные в docker
  volume `langfuse_clickhouse_data`, сносятся `down -v`). Для prod — отдельный ADR с TTL.
- **File-сырец** `data/otel/*.jsonl`: ротация в file-exporter'е (`max_megabytes: 20`,
  `max_backups: 5` = ~100 МБ/сигнал). gitignored.
- **LLM-judge** `data/reports/tools/llm-judge.jsonl`: append; ротацию добавить при росте
  (сейчас сэмпл 5-10% + cap → медленный рост).

### Безопасность

- **Всё opt-in в gitignored файлах**: OTel-env — `settings.local.json` (team не трогаем);
  Langfuse-креды — `.env.otel` (gitignored, `.env.otel.example` — шаблон). Реверс:
  `enable_claude_otel --disable` + `docker compose ... down`.
- **Контент OFF по умолчанию**: `OTEL_LOG_TOOL_CONTENT`/`_USER_PROMPTS`/`_TOOL_DETAILS` не
  включаем (промпты/args/result = PII/секреты). H-P4 judge требует их → активация осознанна.
- **`user.email` в resource attrs** нативной эмиссии → **localhost-only bind**: все порты
  Langfuse (3000/5432/6379/8123/9000/9090) биндим на `127.0.0.1`; коллектор :4318 —
  локальный. Телеметрия не выходит за машину.
- **Секреты Langfuse** (`ENCRYPTION_KEY` 64-hex, `SALT`, `NEXTAUTH_SECRET`, `REDIS_AUTH`):
  генерятся `langfuse_up.py` в `.env.otel` (не дефолтные из compose — те для «поиграться»).

## Последствия

- **+**: полноценные дашборды (P50/P99, sessions, per-agent), Scores для LLM-judge (H-P4),
  независимый второй источник для сверки честности лёгкого контура (главная ценность —
  реализована уже на file-уровне H-P3, Langfuse добавляет UI).
- **−**: +6 контейнеров ~3 ГБ RAM (opt-in, не критический путь) + операционный вес
  (обновления, миграции ClickHouse). Плавающие теги образов (`langfuse:3` и др. — как
  официальный compose) → для prod пинить дайджесты (отдельный ADR).
- **Реверс**: `docker compose -f docker/docker-compose.langfuse.yml down` (`-v` — с данными);
  overlay-ветку коллектора убрать (базовый конфиг). File+cross-check остаются.

## Альтернативы (отклонены)

- **SigNoz вместо Langfuse** — отклонён: Langfuse даёт нативные Scores (LLM-judge H-P4) и
  прямой OTLP-ingest `gen_ai.*`; SigNoz — APM-уклон, без eval-слоя. `enable_claude_otel --otlp`
  оставляет дверь (endpoint+headers) при смене решения.
- **Клиент шлёт в 2 endpoint'а (collector + Langfuse)** — невозможно: у Claude Code ОДИН
  OTLP-endpoint → fan-out только через коллектор.
- **Langfuse default-on** — отклонён: RAM-вес + H-P3 не требует (см. Нагрузка).
- **Вендорить весь стек с пиннингом дайджестов сейчас** — отложено: локальный dev opt-in
  трекает официальные теги (тестируются апстримом); дайджест-пиннинг — при переносе в prod/CI.
