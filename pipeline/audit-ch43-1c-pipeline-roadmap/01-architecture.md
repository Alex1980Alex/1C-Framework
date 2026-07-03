# 01 — План: аудит главы 43 (Пайплайн 1С) + дорожная карта

**Дата:** 2026-07-03 · **Слаг:** audit-ch43-1c-pipeline-roadmap

## Задача

Глубокий анализ `docs/framework documentation/43_ПАЙПЛАЙН_1С/` (27 файлов), подготовка
максимально детализированной дорожной карты: исправления найденных ошибок + улучшения,
обоснованные GitHub-исследованием ведущих реализаций (мандат пользователя).

## Декомпозиция

1. **Аудит док↔код** — 4 параллельных субагента:
   - A: 43.1/43.2/43.3/43.6 (обзор, команды, маршрутизация, анатомия) ↔ hooks/commands/skills
   - B: 43.5 + 43.5.1–43.5.6 (сквозная карта, детектор/маршрутизация) ↔ pipeline_1c_bridge.py
   - C: 43.4 + 43.9 + 43.9.1–43.9.12 (справочник инструментов) ↔ MCP/scripts/skills
   - D: 43.7/43.8 + гейтовая подсистема ↔ gate_policy/gate_policies/onec-task-completion-stop/sonar_rescan
2. **GitHub-исследование** — ecosystem_scan (ADR-039, 7 запросов) + deep-fetch 4 свежих реализаций
   (agentico, AI-DLC, koto, Graybark) + кеш architecture-research (spec-kit/BMAD/LangGraph/OPA/SARIF).
   Факты → `cache/agentic-quality-gate-workflow-templates-2026.md`.
3. **Синтез** — дорожная карта `docs/roadmap/260703_ROADMAP_CH43_1C_PIPELINE_AUDIT.md`:
   П0 исправления ошибок докам/коду, П1+ улучшения с атрибуцией [web/docs/exp/own].
4. **Фиксация** — кеш обновлён, память (capture_pattern), §18 roadmap-протокол.

## Ограничения

- Ничего в продуктовом коде не менять в рамках этой задачи (анализ + roadmap-документ).
- GitHub-поиск только через ecosystem_scan (хард-энфорсер).
