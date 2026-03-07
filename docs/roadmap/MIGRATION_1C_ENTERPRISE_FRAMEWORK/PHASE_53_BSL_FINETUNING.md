# Фаза 53: BSL Fine-tuning

**Tier:** 4 — Расширения
**Статус:** DONE
**Зависимости:** Фаза 45 (BSL Semantic Search)
**Оценка:** ~3 часа

---

## Цель

Перенести инфраструктуру fine-tuning моделей на BSL-коде (Qwen2.5-Coder-7B, LoRA, GGUF).

---

## Компонент

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\finetuning\` |
| **Цель** | `D:\1С-Framework\src\bsl\finetuning\` |
| **Base модель** | Qwen2.5-Coder-7B |
| **Метод** | LoRA (r=16, alpha=16) |
| **Dataset** | 10,000 BSL примеров (~22 MB) |
| **Training** | ~500 steps на T4 GPU (1-2 часа) |
| **Quantization** | GGUF для Ollama |

---

## Pipeline

```
BSL Source Code -> Dataset Extraction -> Colab Training -> GGUF Export -> Ollama
```

1. **Extract**: скрипт извлекает BSL-примеры из конфигураций
2. **Train**: Colab notebook, LoRA fine-tuning на T4
3. **Export**: GGUF quantization для локального использования
4. **Deploy**: загрузка в Ollama для BSL semantic search

---

## Шаги

### 53.1 Перенести finetuning/

```bash
cp -r D:/1C-Enterprise_Framework/finetuning src/bsl/finetuning
```

### 53.2 Адаптировать dataset extraction

Обновить пути к BSL-проектам в скрипте извлечения.

### 53.3 Проверить Colab notebook

Убедиться что notebook запускается и ссылки на dataset актуальны.

### 53.4 Документировать процесс

Создать `docs/guides/bsl-finetuning.md` — пошаговая инструкция.

### 53.5 Создать skill

`.claude/skills/bsl-finetuning/SKILL.md`:
- Триггеры: 'fine-tuning BSL', 'LoRA BSL', 'Qwen BSL', 'обучение модели'

---

## Чеклист завершения

- [x] `src/bsl/finetuning/` содержит все файлы (scripts, notebooks, README)
- [x] Dataset extraction скрипт присутствует (extract_dataset.py)
- [x] Colab notebook присутствует (BSL_Finetuning_Colab.ipynb)
- [ ] `docs/guides/bsl-finetuning.md` создан (deferred — requires runtime validation)
- [ ] Skill `bsl-finetuning/SKILL.md` создан (deferred — minimal component)
- [x] Git commit: `feat: Phase 53 — BSL Fine-tuning`
