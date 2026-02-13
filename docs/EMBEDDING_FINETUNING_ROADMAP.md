# Domain Fine-Tuning эмбеддингов для 1С:Предприятие — Дорожная карта

> Анализ: февраль 2026. Цель: +10-30% качество поиска по документации 1С.

---

## 1. Проблема: почему general-purpose модель недостаточна

### 1.1. Семантическая перегрузка терминологии 1С

Модель `intfloat/multilingual-e5-large` обучена на общих текстах. Она **не различает** специфику 1С:

| Термин 1С | Что «думает» модель | Реальное значение в 1С |
|---|---|---|
| **Справочник** | Словарь, книга | Иерархический master-data объект с группами, владельцами, реквизитами и ТЧ |
| **Перечисление** | Перечисление чего-либо | Неизменяемый enum, значения фиксированы в конфигураторе |
| **Регистр сведений** | Непонятно | Таблица с Измерениями (PK), Ресурсами (значения), Реквизитами (аннотации) |
| **Проведение документа** | Оформление документа | Механизм платформы: документ создаёт движения (записи) в регистрах |
| **Измерения** | Геометрия/размеры | Компоненты первичного ключа регистра |
| **Ресурсы** | Природные ресурсы | Хранимые значения в регистре |
| **Реквизиты** | Банковские реквизиты | Дополнительные поля объекта |
| **Движения** | Физическое движение | Записи регистра, созданные при проведении |
| **Срез последних** | Последний срез чего-то | Виртуальная таблица РС — актуальные значения по ключу |
| **Табличная часть** | Часть таблицы | Подчинённая таблица внутри документа/справочника |
| **Общий модуль** | Общий → shared | Серверный/клиентский модуль кода конфигурации |
| **Регистратор** | Человек-регистратор | Документ-владелец записей регистра |

**Результат**: при запросе «движения регистров накопления» модель может ранжировать чанк про «регистры сведений» выше, потому что слово «регистр» доминирует, а разницу «накопления» vs «сведений» модель не понимает.

### 1.2. Составные термины

Токенизатор разбивает на подслова и теряет смысл:
- «Регистр накопления остатков» — 4-словный compound
- «Конструктор движений» — дизайн-тайм инструмент
- «Система компоновки данных» (СКД) — runtime для отчётов
- «Управляемое приложение» — UI runtime mode

### 1.3. Аббревиатуры (невидимые для NLP)

| Аббревиатура | Расшифровка |
|---|---|
| ТЧ | Табличная часть |
| ОМ | Общий модуль |
| БСП | Библиотека стандартных подсистем |
| РН | Регистр накопления |
| РС | Регистр сведений |
| РБ | Регистр бухгалтерии |
| СКД | Система компоновки данных |
| УФ | Управляемые формы |
| КА, ЕРП, УТ | Названия конфигураций |

### 1.4. Количественная оценка проблемы

Текущая модель (`multilingual-e5-large`) на ruMTEB:
- **60.4 балла** (avg по 23 задачам)
- Instruction-tuned версия (`mE5-large-instruct`): **64.7** (+4.3 бесплатно)
- SOTA для русского (`Giga-Embeddings-instruct`): **69.1** (+8.7)
- Доменный fine-tuning даёт ещё **+5-15%** поверх базовой модели

---

## 2. State-of-the-Art: методы fine-tuning (2025-2026)

### 2.1. Основной подход: Contrastive Fine-Tuning

```
Документы → LLM генерирует вопросы → (query, passage) пары
                                         ↓
BM25 mining → hard negatives → (query, positive, negative) тройки
                                         ↓
Contrastive Loss (MNRL / GISTEmbed / Matryoshka)
                                         ↓
Fine-tuned модель → ONNX → production
```

### 2.2. Loss-функции (от простых к продвинутым)

| Loss | Формат данных | Плюс | Минус |
|---|---|---|---|
| **MultipleNegativesRankingLoss** (MNRL) | (query, positive) | Стандарт, простая | Ложные негативы в batch |
| **CachedMNRL** | (query, positive) | Batch 4096+ на 8GB GPU | +20% время |
| **GISTEmbedLoss** | (query, pos) + guide model | Фильтрует ложные негативы | Нужна guide model |
| **CachedGISTEmbed** | то же + guide | Лучшее от обоих | Медленнее |
| **MatryoshkaLoss** | обёртка над любым | Гибкие размерности | Обёртка, не самостоятельная |
| **TripletLoss** | (anchor, pos, neg) | Явные негативы | Слабее MNRL |

**Оптимальная комбинация для нашего случая:**
```python
MatryoshkaLoss(
    model,
    CachedGISTEmbedLoss(model, guide_model),
    matryoshka_dims=[64, 128, 256, 512, 1024]
)
```
Даёт: фильтрация ложных негативов + большие batch + гибкие размерности.

### 2.3. Matryoshka Representation Learning (MRL)

Обучает модель так, что первые D измерений — сами по себе полноценный вектор:
- 64 dims: ~95% качества (16x экономия памяти)
- 128 dims: ~99% качества (8x экономия)
- 256 dims: ~99.5% качества (4x экономия)

**Критический вывод**: fine-tuned модель на 256 dims превосходит base модель на 1024 dims. То есть получаем **лучше И быстрее** одновременно.

### 2.4. LoRA / QLoRA для эмбеддингов

Заморозить базовую модель, обучить только адаптеры (2% параметров):

```python
from peft import LoraConfig, TaskType

peft_config = LoraConfig(
    task_type=TaskType.FEATURE_EXTRACTION,
    r=16,              # ранг (чем больше — мощнее, но медленнее)
    lora_alpha=32,     # масштабирование
    lora_dropout=0.1,
    target_modules=["query", "value"],  # только attention
)
model.add_adapter(peft_config)
# Адаптер: ~10MB vs 1.3GB модели
```

Преимущества:
- Можно держать **несколько адаптеров** для разных доменов (1С, бухгалтерия, юридика)
- Обучение на 8GB VRAM
- `merge_and_unload()` для production (нулевой overhead)

### 2.5. Hard Negative Mining (3 уровня)

| Уровень | Метод | Качество |
|---|---|---|
| 1 | Random in-batch | Базовый |
| 2 | **BM25-mined** (top 10-30 из 50 результатов) | Хороший |
| 3 | Embedding teacher + cross-encoder + LLM фильтрация | Лучший |

**Для нашего фреймворка**: уровень 2 оптимален — у нас уже есть FTS5 BM25 индекс с 1012 чанками.

### 2.6. TermGPT: token-level contrastive learning (2025)

Специально для доменной терминологии. Обычный fine-tuning «размывает» редкие термины (0.08% от датасета). TermGPT добавляет **контрастное обучение на уровне токенов** — заставляя модель различать именно ключевые термины. Результат: +2.36-6.14% на юридических/финансовых задачах.

**Идеально для нашего случая**: «Измерения» (геометрия) vs «Измерения» (ключ регистра).

### 2.7. Graph-Enhanced Contrastive Learning (EMNLP 2025)

Используем граф знаний для генерации обучающих пар:
- Связанные сущности → positive pairs
- Несвязанные → negative pairs
- Превосходит mE5-large на 9.8-14.3% при 3x меньшем количестве параметров

**Наш граф**: 3166 сущностей, 3528 рёбер — готовый источник пар.

---

## 3. Инструменты и библиотеки

### 3.1. Основные инструменты

| Инструмент | Звёзды | Назначение | Наш выбор |
|---|---|---|---|
| [sentence-transformers](https://github.com/huggingface/sentence-transformers) | 17.7K | Стандарт fine-tuning | **Основной** |
| [Unsloth](https://github.com/unslothai/unsloth) | 50.8K | LoRA/QLoRA, 2x быстрее | **Для LoRA** |
| [FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) | 11.1K | BGE models + HNM | Для BGE-M3 |
| [GPL](https://github.com/UKPLab/gpl) | 500+ | Unsupervised domain adapt | **Быстрый старт** |
| [InPars](https://github.com/zetaalphavector/InPars) | 200+ | Synthetic query generation | Альтернатива |
| [MTEB](https://github.com/embeddings-benchmark/mteb) | 3.1K | Оценка на ruMTEB | **Для метрик** |
| [ms-swift](https://github.com/modelscope/ms-swift) | 7K+ | Qwen3/GTE fine-tuning | Для Qwen3 |

### 3.2. Модели-кандидаты для fine-tuning

| Модель | Params | Dims | ruMTEB | Стоимость |
|---|---|---|---|---|
| `intfloat/multilingual-e5-large` (текущая) | 560M | 1024 | 60.4 | 0 (уже есть) |
| `intfloat/multilingual-e5-large-instruct` | 560M | 1024 | 64.7 | Бесплатная замена |
| `BAAI/bge-m3` | 568M | 1024 | 60.8 | Dense + sparse + ColBERT |
| `ai-sage/Giga-Embeddings-instruct` | 2.5B | 2048 | **69.1** | SOTA русский, MIT |
| `Qwen/Qwen3-Embedding-0.6B` | 600M | 1024 | 70.58* | SOTA мультиязычный |

*Qwen3 — результат на MTEB multilingual, не на ruMTEB.

---

## 4. Дорожная карта реализации

### Этап 0: Quick Win — смена базовой модели (1 час)

**Задача**: Переключиться на `mE5-large-instruct` без fine-tuning.

**Что делать**:
```env
EMBEDDING__MODEL=intfloat/multilingual-e5-large-instruct
```

**Ожидание**: +4.3 балла на ruMTEB бесплатно. Нужен полный реиндекс.

**Файлы**: `config.py`, `.env`

---

### Этап 1: Генерация синтетического датасета (2-4 часа)

**Задача**: Создать 3000-5000 пар `(query, positive_chunk)` из наших 1012 чанков.

**1.1. Генератор запросов** (новый скрипт `scripts/generate_training_pairs.py`)

Для каждого текстового чанка (893 шт) генерируем 3-5 вопросов через Claude Sonnet:

```python
_GENERATION_PROMPT = """
Контекст из документации 1С:Предприятие 8:
---------------------
{chunk_text}
---------------------
Раздел: {section_title}

Сгенерируй {n} вопросов на русском языке, на которые данный фрагмент отвечает.

РАЗНООБРАЗИЕ ОБЯЗАТЕЛЬНО:
1. Фактический вопрос (что/где/как) — "Что такое справочник в 1С?"
2. Аналитический вопрос (зачем/почему) — "Зачем нужны табличные части?"
3. Практический вопрос (как сделать) — "Как настроить WS-ссылку?"
4. Сравнительный вопрос — "Чем справочник отличается от перечисления?"
5. Поисковый запрос (2-3 слова) — "справочник иерархия владелец"

Используй терминологию из контекста.
Каждый вопрос на отдельной строке, без нумерации.
"""
```

**1.2. Словарь синонимов и аббревиатур** (новый файл `data/1c_terminology.json`)

```json
{
  "synonyms": {
    "Табличная часть": ["ТЧ", "табличная часть документа", "встроенная таблица"],
    "Общий модуль": ["ОМ", "серверный модуль", "общий модуль конфигурации"],
    "Регистр накопления": ["РН", "регистр остатков и оборотов"],
    "Регистр сведений": ["РС", "информационный регистр"],
    "Регистр бухгалтерии": ["РБ", "бухгалтерский регистр"],
    "Система компоновки данных": ["СКД", "отчёт СКД"],
    "Проведение документа": ["проводка", "проведение", "запись движений"],
    "Библиотека стандартных подсистем": ["БСП", "библиотека подсистем"]
  },
  "term_definitions": {
    "Измерения": "Компоненты первичного ключа регистра (оси хранения данных)",
    "Ресурсы": "Хранимые значения регистра (числа, ссылки)",
    "Реквизиты": "Дополнительные поля объекта конфигурации",
    "Движения": "Записи регистра, созданные при проведении документа",
    "Регистратор": "Документ-владелец записей регистра",
    "Срез последних": "Виртуальная таблица РС — актуальные значения по ключу"
  }
}
```

**1.3. Расширение запросов** — для каждого запроса добавить варианты с аббревиатурами:
- "Как добавить табличную часть?" → доп. запрос: "Как добавить ТЧ?"
- "Настройка регистра сведений" → доп. запрос: "Настройка РС"

**Стоимость**: ~$5-10 на Claude Sonnet API.
**Результат**: ~4000-5000 пар `(query, chunk_id)` в формате JSONL.

---

### Этап 2: Hard Negative Mining (1-2 часа)

**Задача**: Для каждого query найти «обманчиво похожие, но нерелевантные» чанки.

**2.1. BM25 mining** (используем существующий FTS5 индекс)

```python
# scripts/mine_hard_negatives.py
for query, positive_chunk_id in training_pairs:
    # Ищем top-50 по BM25
    bm25_results = bm25_store.search(query, k=50)

    # Пропускаем top-10 (могут быть ложными негативами)
    # Берём ranks 10-30 как hard negatives
    negatives = [r for r in bm25_results[10:30]
                 if r.chunk_id != positive_chunk_id]

    # Оставляем 3-5 негативов на запрос
    hard_negatives = negatives[:5]
```

**2.2. Терминологические негативы** (уникально для 1С)

Генерируем пары, где модель должна различать похожие объекты:

| Query | Positive | Hard Negative |
|---|---|---|
| «Измерения регистра» | Чанк про измерения РН | Чанк про «измерения» в другом контексте |
| «Справочник иерархический» | §5.3 Справочники | §5.4 Документы (тоже объект) |
| «Движения документа» | §5.14 Регистры накопления | §5.13 Регистры сведений |
| «Как создать ТЧ» | Чанк про табличные части | Чанк про реквизиты (оба — «поля объекта») |

**2.3. Cross-encoder фильтрация** (опционально)

Пропустить все пары через cross-encoder (BGE-reranker), отбросить негативы с score > 0.9 от positive (вероятно ложные негативы).

**Результат**: ~4000 троек `(query, positive, negative)` в формате:
```jsonl
{"query": "Что такое регистр сведений?", "positive": "§5.13...", "negative": "§5.14..."}
```

---

### Этап 3: Fine-Tuning модели (30 мин - 2 часа)

**Задача**: Обучить LoRA-адаптер поверх E5-large.

**3.1. Базовый вариант (sentence-transformers v5)**

```python
# scripts/finetune_embeddings.py
import json
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.losses import (
    CachedMultipleNegativesRankingLoss,
    MatryoshkaLoss,
)
from sentence_transformers.evaluation import InformationRetrievalEvaluator
from peft import LoraConfig, TaskType

# 1. Загрузка модели
model = SentenceTransformer("intfloat/multilingual-e5-large")

# 2. LoRA адаптер (~10MB, 2% параметров)
peft_config = LoraConfig(
    task_type=TaskType.FEATURE_EXTRACTION,
    r=16,
    lora_alpha=32,
    lora_dropout=0.1,
    target_modules=["query", "value"],
)
model.add_adapter(peft_config)

# 3. Датасет
train_data = Dataset.from_json("data/training/train.jsonl")
eval_data = Dataset.from_json("data/training/eval.jsonl")

# 4. Loss: Matryoshka + CachedMNRL
inner_loss = CachedMultipleNegativesRankingLoss(model, mini_batch_size=64)
loss = MatryoshkaLoss(
    model, inner_loss,
    matryoshka_dims=[64, 128, 256, 512, 1024]
)

# 5. Evaluator
evaluator = InformationRetrievalEvaluator(
    queries=eval_queries,        # {qid: text}
    corpus=eval_corpus,          # {cid: text}
    relevant_docs=eval_relevant, # {qid: {cid1, cid2}}
    name="1c-domain-eval",
)

# 6. Training
args = SentenceTransformerTrainingArguments(
    output_dir="models/e5-large-1c-domain",
    num_train_epochs=3,
    per_device_train_batch_size=32,
    learning_rate=2e-5,
    warmup_ratio=0.1,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    bf16=True,  # bfloat16 для GPU
)

trainer = SentenceTransformerTrainer(
    model=model,
    train_dataset=train_data,
    eval_dataset=eval_data,
    loss=loss,
    args=args,
    evaluator=evaluator,
)

trainer.train()

# 7. Merge LoRA → полная модель
model.merge_and_unload()
model.save("models/e5-large-1c-domain-merged")
```

**3.2. Продвинутый вариант: GISTEmbed + guide model**

```python
from sentence_transformers.losses import CachedGISTEmbedLoss

# Guide model — более мощная модель для фильтрации ложных негативов
guide_model = SentenceTransformer("BAAI/bge-m3")

loss = MatryoshkaLoss(
    model,
    CachedGISTEmbedLoss(model, guide_model, mini_batch_size=64),
    matryoshka_dims=[64, 128, 256, 512, 1024],
)
```

**3.3. Graph-Enhanced вариант** (используем наш граф)

```python
# Генерация пар из графа знаний
for entity in graph_store.get_entities():
    # Positive: чанки, содержащие эту сущность
    pos_chunks = graph_store.get_entity_chunks(entity.id)

    # Negative: чанки связанных, но ДРУГИХ сущностей
    neighbors = graph_store.get_neighbors(entity.id, depth=2)
    neg_chunks = [c for n in neighbors for c in graph_store.get_entity_chunks(n.id)
                  if c not in pos_chunks]

    # Добавляем в датасет
    for pc in pos_chunks:
        for nc in neg_chunks[:3]:
            pairs.append({"query": entity.name, "positive": pc.content, "negative": nc.content})
```

**Требования к GPU**: 8GB VRAM (LoRA), 16GB (full fine-tuning). Время: 10-30 минут.

---

### Этап 4: Оценка и A/B тестирование (2-4 часа)

**4.1. Метрики**

| Метрика | Что измеряет | Целевое улучшение |
|---|---|---|
| **NDCG@10** | Ранжирование с весом позиции | +5-10% |
| **MRR@10** | Позиция первого релевантного | +5-10% |
| **Recall@5** | Покрытие при k=5 | +8-15% |
| **Recall@10** | Покрытие при k=10 | +8-15% |
| **Hit Rate** | Top-1 релевантен? | +5-10% |

**4.2. Тестовые сценарии (обязательные)**

```python
test_queries = {
    # Терминологические
    "Что такое измерения регистра?": "§5.14 или §5.13 (не геометрия!)",
    "Справочник vs перечисление": "§5.3 + §5.4 (различия)",
    "Движения при проведении": "§5.14 Регистры накопления",

    # Аббревиатуры
    "ТЧ документа": "чанки про табличные части",
    "Настройка СКД": "система компоновки данных",

    # Составные
    "Регистр накопления остатков": "§5.14 (не регистр сведений!)",
    "Подчиненный справочник владелец": "§5.3 (подчинение)",

    # Практические
    "Как создать WS-ссылку": "§5.5.21",
    "Свойства HTTP-сервиса": "§5.5.24",
}
```

**4.3. A/B тест в production**

Используем Phase 34 (DSPy A/B API):
- Группа A: текущая модель (e5-large)
- Группа B: fine-tuned модель
- Метрика: grader relevance ratio + user feedback

---

### Этап 5: Production Deployment (1-2 часа)

**5.1. Экспорт в ONNX**

```python
# После merge LoRA
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("models/e5-large-1c-domain-merged")
model.save_pretrained("models/e5-large-1c-domain-onnx", backend="onnx")
```

**5.2. INT8 квантизация** (опционально, +3x CPU speedup)

```bash
python -m onnxruntime.quantization.quantize \
    --input models/e5-large-1c-domain-onnx/model.onnx \
    --output models/e5-large-1c-domain-int8/model.onnx \
    --quant_format QOperator
```

**5.3. Конфигурация**

```env
EMBEDDING__MODEL=models/e5-large-1c-domain-merged
EMBEDDING__BACKEND=onnx
# или
EMBEDDING__MODEL=models/e5-large-1c-domain-int8
EMBEDDING__BACKEND=onnx
```

**5.4. Реиндексация**

Полный реиндекс всех документов с новыми эмбеддингами:
```bash
python reindex_api.py  # или через API POST /documents/reindex-all
```

BM25 индекс **не меняется** (лексический, не зависит от эмбеддингов).

---

### Этап 6: Расширенные улучшения (опционально)

**6.1. Переход на Giga-Embeddings-instruct** (SOTA русский)

```env
EMBEDDING__MODEL=ai-sage/Giga-Embeddings-instruct
EMBEDDING__DIMENSIONS=2048
```

LoRA fine-tuning на Giga потребует ~24GB VRAM (2.5B модель). Ожидаемый прирост: +8.7 баллов ruMTEB поверх E5.

**6.2. Multi-Adapter System**

Держать несколько LoRA-адаптеров для разных доменов:
```
models/adapters/
  ├── 1c-configurator.bin     # Глава 5: объекты конфигурации
  ├── 1c-programming.bin      # Глава 7: встроенный язык
  ├── 1c-integration.bin      # Глава 17: интеграция
  └── 1c-general.bin          # Общий адаптер
```

Маршрутизатор выбирает адаптер по теме запроса.

**6.3. TermGPT-style token-level contrastive**

Добавить token-level контрастное обучение для критических терминов 1С. Это самый продвинутый подход, но требует кастомной loss-функции.

**6.4. Continuous Learning от feedback**

Используем Phase 22 (FeedbackStore) для сбора пар:
- Grader оценил чанк как relevant → positive pair
- Grader оценил как irrelevant → negative pair
- Накопить 500+ пар → перетренировать адаптер

---

## 5. Timeline и ресурсы

| Этап | Время | GPU | Стоимость | Результат |
|---|---|---|---|---|
| **0. Quick Win** | 1ч + реиндекс | — | $0 | +4.3 ruMTEB (смена на instruct) |
| **1. Генерация данных** | 2-4ч | — | $5-10 LLM | 4000-5000 пар |
| **2. Hard Negatives** | 1-2ч | — | $0 | 4000 троек |
| **3. Fine-Tuning** | 30мин-2ч | 1x 8GB+ | $0-2 cloud | Обученная модель |
| **4. Оценка** | 2-4ч | 1x GPU | $0 | Метрики до/после |
| **5. Deployment** | 1-2ч + реиндекс | — | $0 | Production |
| **6. Расширения** | По необходимости | varies | varies | Дополнительные % |

**Итого минимум**: 8-14 часов работы, $5-12, 1 GPU.
**Ожидаемый результат**: +10-20% на доменных метриках, +5-10% на общих.

---

## 6. Структура файлов

```
scripts/
  generate_training_pairs.py    # Этап 1: генерация (query, chunk) пар
  mine_hard_negatives.py        # Этап 2: BM25 + cross-encoder mining
  generate_graph_pairs.py       # Этап 2: пары из графа знаний
  finetune_embeddings.py        # Этап 3: LoRA fine-tuning
  evaluate_embeddings.py        # Этап 4: NDCG/MRR/Recall оценка
  export_onnx.py                # Этап 5: ONNX экспорт + квантизация

data/
  training/
    train.jsonl                 # Обучающий датасет (80%)
    eval.jsonl                  # Валидационный датасет (20%)
  1c_terminology.json           # Словарь терминов + синонимы

models/
  e5-large-1c-domain/           # LoRA adapter
  e5-large-1c-domain-merged/    # Merged model
  e5-large-1c-domain-onnx/      # ONNX export
```

---

## 7. Ключевые источники

### Методы и подходы
- [Fine-tune Embedding Models for RAG — Philipp Schmid](https://www.philschmid.de/fine-tune-embedding-model-for-rag)
- [LlamaIndex: Fine-Tuning Embeddings with Synthetic Data](https://www.llamaindex.ai/blog/fine-tuning-embeddings-for-rag-with-synthetic-data-e534409a3971)
- [Matryoshka Representation Learning (arXiv 2205.13147)](https://arxiv.org/abs/2205.13147)
- [GISTEmbed (arXiv:2402.16829)](https://arxiv.org/abs/2402.16829)
- [TermGPT: Domain Terminology Fine-Tuning (arXiv:2511.09854)](https://arxiv.org/html/2511.09854)
- [Graph-Enhanced Contrastive Learning (EMNLP 2025)](https://aclanthology.org/2025.emnlp-industry.103.pdf)
- [NV-Retriever Hard Negative Mining (arXiv)](https://arxiv.org/pdf/2407.15831)
- [Learn Before Represent (arXiv:2601.11124)](https://arxiv.org/html/2601.11124)

### Инструменты
- [sentence-transformers](https://github.com/huggingface/sentence-transformers) — 17.7K stars
- [Unsloth](https://github.com/unslothai/unsloth) — 50.8K stars, LoRA/QLoRA
- [FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) — 11.1K stars, BGE toolkit
- [GPL](https://github.com/UKPLab/gpl) — unsupervised domain adaptation
- [MTEB](https://github.com/embeddings-benchmark/mteb) — 3.1K stars, evaluation

### Русскоязычные модели
- [Giga-Embeddings-instruct](https://huggingface.co/ai-sage/Giga-Embeddings-instruct) — SOTA русский, MIT, 69.1 ruMTEB
- [ru-en-RoSBERTa](https://huggingface.co/ai-forever/ru-en-RoSBERTa) — bilingual, 60.4 ruMTEB
- [ruMTEB benchmark (NAACL 2025)](https://arxiv.org/abs/2408.12503) — 23 задачи, стандарт оценки

### 1С + AI
- [vibecoding1c.ru](http://vibecoding1c.ru/) — MCP + Qdrant RAG для 1С
- [mcp-bsl-platform-context](https://github.com/alkoleft/mcp-bsl-platform-context) — MCP для синтаксис-помощника
- [Habr: LLM и 1С (Magnit)](https://habr.com/ru/companies/magnit/articles/819583/) — анализ ограничений
- [Habr: Регистры в 1С](https://habr.com/ru/companies/otus/articles/714712/) — терминология
