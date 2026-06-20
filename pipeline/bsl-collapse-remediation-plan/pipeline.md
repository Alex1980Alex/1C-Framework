# BSL embedding collapse — research + remediation plan (trivial: research/планирование)

## План
Вопрос: чинить ли BSL dense embedding collapse (trade-отчёт: eff_rank 5.5%, anisotropy 0.607; ceiling recall 45-65%). Исследовать техники + дать план.

## Дизайн
Measurement-gated лестница: **Фаза 0** ROI-гейт (golden-set, BM25 vs dense на лексич./семантич. запросах) → **1** post-hoc (mean-center → soft-ZCA, A/B) → **2** чанкинг (AST/функция + CamelCase-сплит + dedup, reindex) → **3** LoRA contrastive fine-tune Qwen3-Embedding на BSL-парах. Ключевой инсайт: anisotropy/isoscore — неверная цель; решает измеренный recall-разрыв; BM25 уже 90% Hit@10 → ROI фикса под вопросом (Фаза 0 решает «чинить ли вообще»).

## Реализация
3 параллельных research-агента (web 2023-2026): (A) whitening/anisotropy — soft-ZCA для code search помогает, но на fine-tuned Qwen3 риск net-zero; anisotropy≠плохой retrieval (консенсус); (B) code+Cyrillic модели — нет публичного бенча, Qwen3 BBPE без OOV (collapse content-specific), fine-tune на 1 GPU реально (CardioEmbed); (C) чанкинг — AST +4.3pp, размер слабый рычаг, CamelCase-сплит/dedup дёшевы. Факты → [`cache/bsl-embedding-collapse-remediation-2026.md`](../../.claude/skills/architecture-research/cache/bsl-embedding-collapse-remediation-2026.md) + индекс (commit 761777205). План выдан в ответе.

## Тест
Research-задача — верификация = атрибуция (URL/arxiv/ESANN/ACL на каждый факт). Реализация фиксов (Фазы 0-3) — отдельный прогон по решению об автономии (Workflow).
