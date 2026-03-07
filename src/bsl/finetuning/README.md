# Fine-tuning BSL Coder

> **Статус:** Готово к использованию
> **Дата:** 2025-12-08

## Обзор

Fine-tuning модели Qwen2.5-Coder-7B на коде 1С:Предприятие (BSL) для генерации качественного кода.

## Системные требования

### Локально (с GPU)
- NVIDIA GPU с 8+ GB VRAM
- CUDA 11.8+
- Python 3.10+

### Через Google Colab (рекомендуется)
- Google аккаунт
- Google Drive (для сохранения результатов)

## Структура файлов

```
finetuning/
├── scripts/
│   ├── extract_dataset.py    # Извлечение датасета из BSL
│   ├── index_to_chroma.py    # Индексация для RAG
│   └── train_model.py        # Скрипт обучения (локально)
├── notebooks/
│   └── BSL_Finetuning_Colab.ipynb  # Notebook для Google Colab
├── checkpoints/              # Чекпоинты обучения
└── README.md                 # Этот файл
```

## Быстрый старт (Google Colab)

### Шаг 1: Загрузка датасета в Google Drive

1. Создайте папку `BSL_Finetuning` в Google Drive
2. Загрузите файл:
   ```
   D:\1C-Enterprise_Framework\data\datasets\bsl_training.json
   ```

### Шаг 2: Запуск notebook

1. Откройте [Google Colab](https://colab.research.google.com/)
2. File → Upload notebook → выберите `notebooks/BSL_Finetuning_Colab.ipynb`
3. Runtime → Change runtime type → **GPU (T4)**
4. Запускайте ячейки последовательно

### Шаг 3: После обучения

1. Скачайте GGUF файл из Google Drive
2. Поместите в `D:\1C-Enterprise_Framework\data\models\gguf\`
3. Загрузите в Ollama:
   ```bash
   ollama create bsl-coder -f D:\1C-Enterprise_Framework\data\models\Modelfile
   ollama run bsl-coder "Напиши функцию проверки ИНН"
   ```

## Датасет

| Файл | Размер | Примеров | Описание |
|------|--------|----------|----------|
| `bsl_training.json` | 22 MB | 10,000 | Для fine-tuning |
| `bsl_rag.json` | 20 MB | 10,000 | Для RAG индексации |

### Формат примера:

```json
{
  "instruction": "Напиши функцию ПроверитьИНН на языке 1С (BSL)",
  "input": "",
  "output": "Функция ПроверитьИНН(ИНН)\n    // код...\nКонецФункции"
}
```

## Параметры обучения

| Параметр | Значение | Описание |
|----------|----------|----------|
| **Базовая модель** | Qwen2.5-Coder-7B-Instruct | Оптимизирована для кода |
| **LoRA r** | 16 | Ранг адаптеров |
| **LoRA alpha** | 16 | Масштабирование |
| **Learning rate** | 2e-4 | Скорость обучения |
| **Batch size** | 2 (x4 accumulation) | Эффективный = 8 |
| **Max steps** | 500 | ~1-2 часа на T4 |
| **Quantization** | 4-bit (Q4_K_M) | Для Ollama |

## Оценка качества

После обучения проверьте модель на тестовых запросах:

```bash
ollama run bsl-coder "Напиши процедуру для отправки HTTP запроса"
ollama run bsl-coder "Создай функцию проверки заполненности реквизитов документа"
ollama run bsl-coder "Напиши запрос для получения остатков товаров на складе"
```

## Troubleshooting

### "CUDA out of memory"
- Уменьшите `per_device_train_batch_size` до 1
- Увеличьте `gradient_accumulation_steps` до 8

### Медленное обучение
- Проверьте что используется GPU: `torch.cuda.is_available()`
- В Colab: Runtime → Change runtime type → GPU

### Плохое качество генерации
- Увеличьте количество шагов обучения
- Добавьте больше примеров в датасет
- Проверьте качество примеров в датасете

## Ссылки

- [Unsloth](https://github.com/unslothai/unsloth) - Быстрый fine-tuning
- [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) - Базовая модель
- [Ollama](https://ollama.ai/) - Локальный запуск LLM
