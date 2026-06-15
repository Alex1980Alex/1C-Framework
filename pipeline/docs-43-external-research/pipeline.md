# Обязательный внешний анализ (Infostart + GitHub) в 43.4 — pipeline (trivial)

**План.** Пользователь: добавить в 43.4 обязательный анализ GitHub best-practices + Infostart (доверенный
1С-источник) для 1С-задач.
**Дизайн.** В 43.4: строка «Внешний анализ (ОБЯЗ. для 1С)» в Сквозных + раздел «Обязательный внешний анализ»
(источники с уровнем доверия + механизмы + минимум) + строка в шаблоне TOOL-PLAN. Заземление: docs 8.3.27
первоисточник, Infostart доверенный, GitHub доп.; атрибуция (1c-doc-research) + кеш (knowledge-cache-reminder).
**Реализация.** 3 правки 43.4. Механизмы verified: prework-github-bp.py, prework-stackoverflow.py,
knowledge-cache-reminder.py, skill 1c-doc-research (infostart уже в его кеше).
**Тест.** Ссылки/механизмы существуют; fence-баланс чётный. Новый хук не нужен (knowledge-cache-reminder уже
форсит кеш после WebSearch; полный hard-gate «исследовал ли GitHub+Infostart» — опция, предложена отдельно).
