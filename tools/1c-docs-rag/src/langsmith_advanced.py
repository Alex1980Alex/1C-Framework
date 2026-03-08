"""
Advanced LangSmith Integration

Расширенная observability: A/B тестирование, replay failed runs,
cost tracking dashboard, alerts на аномалии.

Расширяет базовый tracing из P0.

Author: Claude Opus 4.5
Date: 2026-01-25
Priority: P3-15
"""

import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import statistics


class AlertSeverity(Enum):
    """Серьёзность alert'а"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Тип метрики"""
    LATENCY = "latency"           # Время выполнения
    TOKEN_USAGE = "token_usage"   # Использование токенов
    COST = "cost"                 # Стоимость
    SUCCESS_RATE = "success_rate" # Success rate
    ERROR_RATE = "error_rate"     # Error rate


@dataclass
class PromptVariant:
    """Вариант промпта для A/B тестирования"""
    name: str                       # Имя варианта
    prompt: str                     # Текст промпта
    version: int = 1                # Версия
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestResult:
    """Результат A/B теста"""
    variant_a: PromptVariant        # Вариант A
    variant_b: PromptVariant        # Вариант B
    metrics_a: Dict[str, float]     # Метрики A
    metrics_b: Dict[str, float]     # Метрики B
    winner: str                     # "a" или "b"
    confidence: float = 0.0         # Уверенность (0-1)
    significance: float = 0.0       # Статистическая значимость


@dataclass
class RunTrace:
    """Трэйс выполнения"""
    run_id: str                     # Уникальный ID
    timestamp: datetime             # Время выполнения
    inputs: Dict[str, Any]          # Входные данные
    outputs: Dict[str, Any]         # Выходные данные
    latency_ms: float               # Задержка
    tokens_used: int = 0            # Потрачено токенов
    cost_usd: float = 0.0           # Стоимость в USD
    error: Optional[str] = None     # Ошибка если была
    tags: List[str] = field(default_factory=list)


@dataclass
class Alert:
    """Alert о проблеме"""
    severity: AlertSeverity         # Серьёзность
    metric_type: MetricType         # Тип метрики
    message: str                    # Сообщение
    threshold: float                # Превышенный порог
    actual_value: float             # Фактическое значение
    timestamp: datetime = field(default_factory=datetime.now)


class ABTestRunner:
    """
    Запускает A/B тесты промптов.

    Сравнивает два варианта промпта по метрикам.
    """

    def __init__(self):
        self.variants: List[PromptVariant] = []
        self.results: List[ABTestResult] = []

    def add_variant(self, variant: PromptVariant):
        """Добавляет вариант для тестирования"""
        self.variants.append(variant)

    async def run_test(
        self,
        variant_a: PromptVariant,
        variant_b: PromptVariant,
        test_cases: List[Dict[str, Any]],
        eval_fn: Callable,
        sample_size: int = 10
    ) -> ABTestResult:
        """
        Запускает A/B тест.

        Args:
            variant_a: Вариант A
            variant_b: Вариант B
            test_cases: Тестовые кейсы
            eval_fn: Функция оценки (возвращает score 0-1)
            sample_size: Размер выборки

        Returns:
            ABTestResult с результатами
        """
        # Ограничиваем выборку
        cases = test_cases[:sample_size]

        # Выполняем вариант A
        scores_a = []
        latency_a = []
        for case in cases:
            start = time.time()
            result = await self._run_prompt(variant_a, case)
            latency_a.append((time.time() - start) * 1000)

            score = eval_fn(result, case)
            scores_a.append(score)

        # Выполняем вариант B
        scores_b = []
        latency_b = []
        for case in cases:
            start = time.time()
            result = await self._run_prompt(variant_b, case)
            latency_b.append((time.time() - start) * 1000)

            score = eval_fn(result, case)
            scores_b.append(score)

        # Вычисляем метрики
        metrics_a = {
            "avg_score": statistics.mean(scores_a),
            "avg_latency_ms": statistics.mean(latency_a),
            "std_score": statistics.stdev(scores_a) if len(scores_a) > 1 else 0
        }

        metrics_b = {
            "avg_score": statistics.mean(scores_b),
            "avg_latency_ms": statistics.mean(latency_b),
            "std_score": statistics.stdev(scores_b) if len(scores_b) > 1 else 0
        }

        # Определяем победителя
        if metrics_a["avg_score"] > metrics_b["avg_score"]:
            winner = "a"
            confidence = (metrics_a["avg_score"] - metrics_b["avg_score"])
        else:
            winner = "b"
            confidence = (metrics_b["avg_score"] - metrics_a["avg_score"])

        # Статистическая значимость (t-test approximation)
        significance = self._compute_significance(scores_a, scores_b)

        result = ABTestResult(
            variant_a=variant_a,
            variant_b=variant_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            winner=winner,
            confidence=confidence,
            significance=significance
        )

        self.results.append(result)
        return result

    async def _run_prompt(
        self,
        variant: PromptVariant,
        test_case: Dict[str, Any]
    ) -> str:
        """Выполняет промпт (mock)"""
        # В реальности здесь вызов LLM
        return f"Result for {variant.name}: {test_case.get('input', '')}"

    def _compute_significance(self, scores_a: List[float], scores_b: List[float]) -> float:
        """Вычисляет статистическую значимость"""
        if len(scores_a) < 3 or len(scores_b) < 3:
            return 0.0

        # Простой t-test approximation
        mean_a = statistics.mean(scores_a)
        mean_b = statistics.mean(scores_b)

        var_a = statistics.variance(scores_a) if len(scores_a) > 1 else 0
        var_b = statistics.variance(scores_b) if len(scores_b) > 1 else 0

        n_a = len(scores_a)
        n_b = len(scores_b)

        # Pooled variance
        pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)

        # t-statistic
        t_stat = (mean_a - mean_b) / ((pooled_var / n_a + pooled_var / n_b) ** 0.5)

        # Возвращаем abs(t) как меру значимости
        return abs(t_stat)


class RunReplayer:
    """
    Replayer для неудачных runs.

    Позволяет переиграть выполнение с другими параметрами.
    """

    def __init__(self):
        self.runs: List[RunTrace] = []
        self.replay_history: List[RunTrace] = []

    def record_run(self, run: RunTrace):
        """Записывает run"""
        self.runs.append(run)

    async def replay_failed_run(
        self,
        run_id: str,
        new_params: Optional[Dict[str, Any]] = None
    ) -> RunTrace:
        """
        Переигрывает неудачный run с новыми параметрами.

        Args:
            run_id: ID исходного run
            new_params: Новые параметры для переигрывания

        Returns:
            New RunTrace с результатом
        """
        # Находим исходный run
        original = next((r for r in self.runs if r.run_id == run_id), None)

        if not original:
            raise ValueError(f"Run {run_id} not found")

        if not original.error:
            raise ValueError(f"Run {run_id} did not fail")

        # Создаём новый run с новыми параметрами
        start = time.time()

        # Выполняем с новыми параметрами (mock)
        inputs = new_params if new_params else original.inputs

        # В реальности здесь реальное выполнение
        success = new_params is not None and "fix" in new_params

        end = time.time()

        new_run = RunTrace(
            run_id=f"{run_id}_replay_{int(time.time())}",
            timestamp=datetime.now(),
            inputs=inputs,
            outputs={"result": "success"} if success else {},
            latency_ms=(end - start) * 1000,
            error=None if success else "Still failing"
        )

        self.replay_history.append(new_run)
        return new_run

    def get_failed_runs(self) -> List[RunTrace]:
        """Возвращает все неудачные runs"""
        return [r for r in self.runs if r.error]

    def get_failure_patterns(self) -> Dict[str, int]:
        """Анализирует паттерны ошибок"""
        patterns = {}

        for run in self.get_failed_runs():
            if run.error:
                error_type = run.error.split(":")[0]  # Первая часть ошибки
                patterns[error_type] = patterns.get(error_type, 0) + 1

        return patterns


class CostTracker:
    """
    Трекер стоимости LLM вызовов.

    Ведёт учёт расходов по моделям и типам операций.
    """

    # Прейскурант (примерные цены за 1M токенов)
    PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "claude-opus": {"input": 15.0, "output": 75.0},
        "claude-sonnet": {"input": 3.0, "output": 15.0},
        "glm-4": {"input": 0.1, "output": 0.1}  # Z.AI
    }

    def __init__(self):
        self.costs: List[Dict[str, Any]] = []
        self.daily_budgets: Dict[str, float] = {}  # daily_budgets["2026-01-25"] = 10.0

    def track_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Трекает вызов модели.

        Args:
            model: Название модели
            input_tokens: Входные токены
            output_tokens: Выходные токены
            operation: Тип операции (rag, chat, etc)
            metadata: Доп. метаданные

        Returns:
            Стоимость в USD
        """
        pricing = self.PRICING.get(model, {"input": 0.001, "output": 0.002})

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        self.costs.append({
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "operation": operation,
            "cost_usd": total_cost,
            "metadata": metadata or {}
        })

        return total_cost

    def get_cost_dashboard(self, days: int = 7) -> Dict[str, Any]:
        """
        Генерирует дашборд стоимости.

        Args:
            days: За сколько дней показать

        Returns:
            Сводка затрат
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            c for c in self.costs
            if datetime.fromisoformat(c["timestamp"]) > cutoff
        ]

        # Группируем по моделям
        by_model: Dict[str, float] = {}
        # Группируем по операциям
        by_operation: Dict[str, float] = {}

        total_cost = 0
        total_tokens = 0

        for cost in recent:
            model = cost["model"]
            operation = cost["operation"]
            cost_val = cost["cost_usd"]

            by_model[model] = by_model.get(model, 0) + cost_val
            by_operation[operation] = by_operation.get(operation, 0) + cost_val

            total_cost += cost_val
            total_tokens += cost["input_tokens"] + cost["output_tokens"]

        return {
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "avg_cost_per_1k_tokens": round((total_cost / total_tokens * 1000) if total_tokens else 0, 4),
            "by_model": by_model,
            "by_operation": by_operation,
            "transaction_count": len(recent)
        }

    def check_budget_alert(self, daily_budget: float) -> Optional[Alert]:
        """Проверяет превышение бюджета"""
        today = datetime.now().date().isoformat()

        # Траты за сегодня
        today_costs = [
            c for c in self.costs
            if c["timestamp"].startswith(today)
        ]

        today_total = sum(c["cost_usd"] for c in today_costs)

        if today_total > daily_budget:
            return Alert(
                severity=AlertSeverity.WARNING,
                metric_type=MetricType.COST,
                message=f"Daily budget exceeded: ${today_total:.2f} > ${daily_budget:.2f}",
                threshold=daily_budget,
                actual_value=today_total
            )

        return None


class AlertManager:
    """
    Менеджер alert'ов о проблемах.

    Генерирует уведомления при аномалиях.
    """

    def __init__(self):
        self.alerts: List[Alert] = []
        self.thresholds: Dict[MetricType, float] = {
            MetricType.LATENCY: 5000,          # 5 секунд
            MetricType.ERROR_RATE: 0.1,        # 10%
            MetricType.COST: 10.0,             # $10 за сессию
            MetricType.TOKEN_USAGE: 10000     # 10k токенов
        }

    def set_threshold(self, metric_type: MetricType, value: float):
        """Устанавливает порог для метрики"""
        self.thresholds[metric_type] = value

    def check_metrics(
        self,
        metrics: Dict[MetricType, float]
    ) -> List[Alert]:
        """Проверяет метрики и генерирует alert'ы"""
        new_alerts = []

        for metric_type, value in metrics.items():
            threshold = self.thresholds.get(metric_type)

            if threshold and value > threshold:
                alert = Alert(
                    severity=self._get_severity(metric_type, value, threshold),
                    metric_type=metric_type,
                    message=f"{metric_type.value} exceeded threshold: {value:.2f} > {threshold:.2f}",
                    threshold=threshold,
                    actual_value=value
                )
                new_alerts.append(alert)
                self.alerts.append(alert)

        return new_alerts

    def _get_severity(
        self,
        metric_type: MetricType,
        value: float,
        threshold: float
    ) -> AlertSeverity:
        """Определяет серьёзность alert'а"""
        ratio = value / threshold if threshold else 1

        if ratio > 2:
            return AlertSeverity.CRITICAL
        elif ratio > 1.5:
            return AlertSeverity.ERROR
        elif ratio > 1.1:
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO

    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Возвращает alert'ы за последние N часов"""
        cutoff = datetime.now() - timedelta(hours=hours)

        return [
            a for a in self.alerts
            if a.timestamp > cutoff
        ]


# ============================================================================
# Integration Functions
# ============================================================================

async def ab_test_prompts(
    prompt_a: str,
    prompt_b: str,
    test_cases: List[Dict],
    eval_fn: Callable
) -> ABTestResult:
    """
    Быстрый A/B тест двух промптов.

    Args:
        prompt_a: Промпт A
        prompt_b: Промпт B
        test_cases: Тестовые кейсы
        eval_fn: Функция оценки

    Returns:
        Результат теста
    """
    runner = ABTestRunner()

    variant_a = PromptVariant(name="A", prompt=prompt_a)
    variant_b = PromptVariant(name="B", prompt=prompt_b)

    return await runner.run_test(variant_a, variant_b, test_cases, eval_fn)


def track_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    operation: str = "unknown"
) -> float:
    """
    Трекает стоимость LLM вызова.

    Args:
        model: Модель
        input_tokens: Входные токены
        output_tokens: Выходные токены
        operation: Операция

    Returns:
        Стоимость в USD
    """
    tracker = CostTracker()
    return tracker.track_call(model, input_tokens, output_tokens, operation)


# ============================================================================
# CLI Interface
# ============================================================================

async def demo():
    """Демонстрация advanced features"""

    print("=== A/B Testing Demo ===")
    runner = ABTestRunner()

    variant_a = PromptVariant(name="Concise", prompt="Be concise.")
    variant_b = PromptVariant(name="Detailed", prompt="Be detailed.")

    test_cases = [
        {"input": "Explain recursion"},
        {"input": "What is a closure?"}
    ]

    async def mock_eval(result, case):
        return 0.8 if "concise" in result.lower() else 0.6

    result = await runner.run_test(variant_a, variant_b, test_cases, mock_eval)

    print(f"Winner: {result.winner}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Significance: {result.significance:.2f}")
    print()

    print("=== Cost Tracking Demo ===")
    tracker = CostTracker()

    # Трекируем несколько вызовов
    tracker.track_call("gpt-4", 1000, 500, "rag")
    tracker.track_call("gpt-3.5-turbo", 2000, 1000, "chat")
    tracker.track_call("glm-4", 500, 300, "rag")

    dashboard = tracker.get_cost_dashboard(days=1)

    print(json.dumps(dashboard, indent=2))
    print()

    print("=== Alerts Demo ===")
    alert_mgr = AlertManager()

    metrics = {
        MetricType.LATENCY: 6000,     # Превышение
        MetricType.ERROR_RATE: 0.05,  # OK
        MetricType.COST: 5.0           # OK
    }

    alerts = alert_mgr.check_metrics(metrics)

    for alert in alerts:
        print(f"[{alert.severity.value.upper()}] {alert.message}")


def main():
    """CLI для тестирования"""
    import asyncio
    asyncio.run(demo())


if __name__ == "__main__":
    main()
