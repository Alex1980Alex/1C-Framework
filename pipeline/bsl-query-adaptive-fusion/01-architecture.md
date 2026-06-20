# 01 — Планирование

Захватить семантический +8pp, что наивный RRF теряет (S: dense-only 0.42 > hybrid-RRF 0.34) — улучшить fusion BSL-поиска. Нюанс: оба golden = NL-запросы, поэтому query-form classifier (NL→dense) не сработает (на L dense-heavy регрессит). Правильный рычаг — score-adaptive fusion. Measure-then-apply.
