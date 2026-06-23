# 01 Планирование — устойчивый ERP-reindex

## Проблема
Реиндекс ERP (`bsl_code_erp_ref`, qwen3-st) застрял на ~35% (175k чанков). Прогон висел 10.5ч
без OOM/traceback (idle рос, GPU 24.2/24.5GB).

## Корень (live-диагностика)
Qwen3-Embedding-8B (~16GB) на 24GB **тихо заклинивает** (CUDA kernel-wedge, не OOM) при
эмбеддинге батча длинных чанков **тяжёлого модуля**: и >2MB монстры (ERP до 10MB), и крупные
<2MB (621KB / 7562 строки). `expandable_segments` ВРЕДИТ (перебивает тюнинг аллокатора).
Зависший CUDA нельзя прибить in-process.

## Recall / research
- Память: [[feedback-bsl-reindex-segfault-torch210]] (load-time segfault — ДРУГОЕ), [[feedback-bsl-indexer-backend-choice]].
- Скрипт `reindex_bsl_qwen3.py`: бакетер уже имеет таблицу token→batch (8193+→1) + `--batch-size`
  как потолок бакета; `garbage_collection_threshold:0.6,max_split_size_mb:512` через setdefault; FA2 авто-вкл.

## Цель
Устойчивый прогон без вечного wedge + no-loss (все файлы индексируются), аддитивно/реверсивно.
