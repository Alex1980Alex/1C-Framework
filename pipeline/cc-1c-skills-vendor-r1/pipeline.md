# Pipeline: Вендоринг cc-1c-skills + закрытие R-1 (full cycle .mxlx)

**Тип:** complex · **Дата:** 2026-06-21

## 1. План
(A) Вендорить pinned cc-1c-skills в external/. (B) Закрыть R-1: правка реального .mxlx через cc-1c-skills → update_database → рендер PDF → откат.

## 2. Дизайн
A: robocopy pinned 3d36c20 без tests/.git → external/cc-1c-skills + VENDOR.md. B: decompile→marker→recompile→validate→backup→deploy реального ПФ_MXL_АктРасхожденияВеса_by → EDT update_database → execute_code (маркер+рендер) → revert→update_database→verify.

## 3. Реализация
- external/cc-1c-skills (340 файлов, 6.6MB, VENDOR.md pin 3d36c20), smoke vendored mxl-info OK.
- R-1 драйвер (temp): deploy recompiled .mxlx с маркером.
- ADR-031 + кеш + память (feedback_edt_mcp_mxlx_not_compiled) обновлены: R-1 ЗАКРЫТ.

## 4. Тест / результат
- A: вендоренный mxl-info прочитал реальный макет — OK.
- B: до апдейта ИБ marker=NO → deploy → EDT INCREMENTAL_UPDATE_REQUIRED → update_database UPDATED → ИБ marker=YES, pdfBytes=41553 (рендер OK) → revert → update_database → marker=NO, pdfBytes=40530, git CLEAN.
- Вывод: полный цикл правки .mxlx через cc-1c-skills платформой принят; R-1 закрыт.
