"""Benchmark Dataset for RAG Evaluation (Phase 20.1).

Provides a dataset of questions and expected answers for evaluating RAG quality.
Based on RAGAS and FlashRAG evaluation patterns.

Author: Claude Code
Version: 1.0.0 - Phase 20: AutoRAG Optimization
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BenchmarkQuestion(BaseModel):
    """A single benchmark question."""

    id: str
    question: str
    expected_answer: str
    category: str = ""  # "factual", "procedural", "conceptual"
    difficulty: str = "medium"  # "easy", "medium", "hard"
    source_documents: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class BenchmarkDataset(BaseModel):
    """A complete benchmark dataset."""

    name: str
    description: str = ""
    questions: list[BenchmarkQuestion]
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkLoader:
    """Loads and manages benchmark datasets."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize the benchmark loader.

        Args:
            data_dir: Directory containing benchmark datasets
        """
        self._data_dir = Path(data_dir or Path.cwd() / "data" / "benchmarks")
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def load_dataset(self, name: str) -> BenchmarkDataset:
        """Load a benchmark dataset by name.

        Args:
            name: Dataset name (without .json)

        Returns:
            Loaded BenchmarkDataset
        """
        dataset_file = self._data_dir / f"{name}.json"

        if not dataset_file.exists():
            logger.warning(f"[BENCHMARK] Dataset {name} not found, creating default")
            return self._create_default_dataset()

        with dataset_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        questions = [
            BenchmarkQuestion(**q) for q in data.get("questions", [])
        ]

        return BenchmarkDataset(
            name=data.get("name", name),
            description=data.get("description", ""),
            questions=questions,
            metadata=data.get("metadata", {}),
        )

    def save_dataset(self, dataset: BenchmarkDataset):
        """Save a benchmark dataset to disk.

        Args:
            dataset: Dataset to save
        """
        dataset_file = self._data_dir / f"{dataset.name}.json"

        with dataset_file.open("w", encoding="utf-8") as f:
            json.dump(dataset.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info(f"[BENCHMARK] Saved dataset: {dataset_file}")

    def list_datasets(self) -> list[str]:
        """List available benchmark datasets.

        Returns:
            List of dataset names
        """
        datasets = []
        for file in self._data_dir.glob("*.json"):
            datasets.append(file.stem)
        return datasets

    def _create_default_dataset(self) -> BenchmarkDataset:
        """Create a default 1C:Enterprise benchmark dataset.

        Returns:
            Default BenchmarkDataset
        """
        questions = [
            BenchmarkQuestion(
                id="q001",
                question="Что такое СКД в 1С:Предприятие?",
                expected_answer="СКД (Система Компоновки Данных) - это встроенный в платформу 1С:Предприятие инструмент для создания сложных отчетов. Позволяет гибко настраивать структуру, параметры и варианты отчетов без программирования.",
                category="conceptual",
                difficulty="easy",
                keywords=["СКД", "Схема компоновки данных", "отчеты"],
            ),
            BenchmarkQuestion(
                id="q002",
                question="Как создать обычныйフォーム в управляемом приложении?",
                expected_answer="В управляемом приложении обычные формы не используются. Вместо них применяются управляемые формы. Для создания управляемой формы нужно: 1) Открыть конфигуратор, 2) Нажать правой кнопкой на объект, 3) Выбрать 'Открыть форму объекта', 4) Настроить элементы управления.",
                category="procedural",
                difficulty="medium",
                keywords=["форма", "управляемое приложение", "интерфейс"],
            ),
            BenchmarkQuestion(
                id="q003",
                question="Какие режимы блокировок существуют в 1С:Предприятие?",
                expected_answer="В 1С:Предприятие существуют два основных режима блокировок: 1) Управляемый - блокировки устанавливаются явным образом через НачатьТранзакцию() и ЗафиксироватьТранзакцию(), 2) Автоматический - платформа управляет блокировками автоматически. Автоматический режим делится на: Автоматический, Управляемый, Исключительный.",
                category="factual",
                difficulty="medium",
                keywords=["блокировки", "транзакции", "конкурентный доступ"],
            ),
            BenchmarkQuestion(
                id="q004",
                question="Как работает механизм упреждающего управления?",
                expected_answer="Упреждающее управление позволяет отслеживать изменения в ссылочных полях объектов и реагировать на них. Основной способ - подписки на события. При изменении объекта, на который ссылается текущий объект, вызывается обработчик ОбработкаПолученияФормУпреждающего управления, где можно выполнить произвольный код.",
                category="conceptual",
                difficulty="hard",
                keywords=["упреждающее управление", "подписки", "события"],
            ),
            BenchmarkQuestion(
                id="q005",
                question="Как выполнить HTTP-запрос из 1С:Предприятие?",
                expected_answer="Для выполнения HTTP-запросов используются объекты: HTTPСоединение, HTTPЗапрос, HTTPОтвет. Основной код: Соединение = Новый HTTPСоединение(Хост, Порт); Запрос = Новый HTTPЗапрос(Ресурс); Запрос.Заголовки.Вставить('Content-Type', 'application/json'); Ответ = Соединение.ВызватьHTTPМетод('POST', Запрос);",
                category="procedural",
                difficulty="medium",
                keywords=["HTTP", "запрос", "web", "REST", "API"],
            ),
        ]

        return BenchmarkDataset(
            name="1c_enterprise_default",
            description="Базовый набор тестовых вопросов для 1С:Предприятие",
            questions=questions,
            metadata={
                "version": "1.0",
                "created_for": "Phase 20 AutoRAG",
                "total_questions": len(questions),
            },
        )

    def to_autorag_format(self, dataset: BenchmarkDataset) -> list[dict[str, Any]]:
        """Convert benchmark dataset to AutoRAG format.

        Args:
            dataset: Benchmark dataset

        Returns:
            List of dictionaries for AutoRAG
        """
        return [
            {
                "question_id": q.id,
                "question": q.question,
                "expected_answer": q.expected_answer,
                "category": q.category,
                "difficulty": q.difficulty,
                "keywords": q.keywords,
            }
            for q in dataset.questions
        ]

    def split_dataset(
        self,
        dataset: BenchmarkDataset,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
    ) -> dict[str, list[BenchmarkQuestion]]:
        """Split dataset into train/validation/test sets.

        Args:
            dataset: Dataset to split
            train_ratio: Ratio for training set
            val_ratio: Ratio for validation set

        Returns:
            Dict with 'train', 'val', 'test' lists
        """
        import random

        questions = dataset.questions.copy()
        random.shuffle(questions)

        total = len(questions)
        train_size = int(total * train_ratio)
        val_size = int(total * val_ratio)

        return {
            "train": questions[:train_size],
            "val": questions[train_size:train_size + val_size],
            "test": questions[train_size + val_size:],
        }


def load_benchmark(name: str = "1c_enterprise_default") -> BenchmarkDataset:
    """Convenience function to load a benchmark dataset.

    Args:
        name: Dataset name

    Returns:
        Loaded BenchmarkDataset
    """
    loader = BenchmarkLoader()
    return loader.load_dataset(name)
