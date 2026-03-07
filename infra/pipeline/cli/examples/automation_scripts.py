#!/usr/bin/env python3
"""
Automation Scripts for Pipeline CLI.

Примеры скриптов автоматизации с использованием Pipeline CLI.

Версия: 1.0.0
Дата: 2025-12-23
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# Корень проекта
PROJECT_ROOT = Path(__file__).parents[4]


class PipelineAutomation:
    """
    Класс для автоматизации работы с Pipeline CLI.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Инициализация.

        Args:
            config_path: Путь к конфигурации (опционально)
        """
        self.config_path = config_path
        self.python = sys.executable

    def run_cli(self, args: list[str], format_json: bool = False) -> dict:
        """
        Запустить CLI команду.

        Args:
            args: Аргументы команды
            format_json: Получить результат в JSON

        Returns:
            Dict с результатами
        """
        cmd_args = args.copy()

        if format_json:
            cmd_args.extend(["--format", "json"])

        if self.config_path:
            cmd_args.extend(["--config", str(self.config_path)])

        result = subprocess.run(
            [self.python, "-m", "shared.pipeline.cli"] + cmd_args,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        output = {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }

        if format_json and result.stdout:
            try:
                output["data"] = json.loads(result.stdout)
            except json.JSONDecodeError:
                output["data"] = None

        return output

    def run_pipeline(
        self,
        project: str,
        task: str,
        timeout: int = 3600,
        dry_run: bool = False
    ) -> dict:
        """
        Запустить pipeline.

        Args:
            project: Имя проекта
            task: Описание задачи
            timeout: Таймаут в секундах
            dry_run: Режим симуляции

        Returns:
            Dict с результатом
        """
        args = [
            "run",
            "--project", project,
            "--task", task,
            "--timeout", str(timeout)
        ]

        if dry_run:
            args.append("--dry-run")

        return self.run_cli(args)

    def get_status(self, run_id: Optional[str] = None) -> dict:
        """
        Получить статус pipeline.

        Args:
            run_id: ID запуска (опционально)

        Returns:
            Dict со статусом
        """
        args = ["status"]

        if run_id:
            args.extend(["--run-id", run_id])

        return self.run_cli(args, format_json=True)

    def list_projects(self) -> dict:
        """
        Получить список проектов.

        Returns:
            Dict со списком проектов
        """
        return self.run_cli(["list", "projects"], format_json=True)

    def add_project(
        self,
        name: str,
        path: str,
        project_type: str = "configuration"
    ) -> dict:
        """
        Добавить проект.

        Args:
            name: Имя проекта
            path: Путь к проекту
            project_type: Тип проекта

        Returns:
            Dict с результатом
        """
        return self.run_cli([
            "config", "add-project",
            "--name", name,
            "--path", path,
            "--type", project_type
        ])

    def wait_for_completion(
        self,
        run_id: str,
        timeout: int = 3600,
        poll_interval: int = 10
    ) -> dict:
        """
        Ожидать завершения pipeline.

        Args:
            run_id: ID запуска
            timeout: Максимальное время ожидания
            poll_interval: Интервал проверки

        Returns:
            Dict с финальным статусом
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_status(run_id)

            if status.get("data", {}).get("status") in ["completed", "failed", "cancelled"]:
                return status

            time.sleep(poll_interval)

        return {
            "success": False,
            "error": "Timeout waiting for pipeline completion"
        }


def example_batch_processing():
    """
    Пример пакетной обработки нескольких задач.
    """
    print("\n" + "=" * 60)
    print("Example: Batch Processing")
    print("=" * 60)

    automation = PipelineAutomation()

    tasks = [
        {
            "project": "GKSTCPLK-1872",
            "task": "Добавить валидацию номенклатуры"
        },
        {
            "project": "GKSTCPLK-1872",
            "task": "Оптимизировать запрос в регистре"
        },
        {
            "project": "GKSTCPLK-1996",
            "task": "Исправить ошибку проведения"
        }
    ]

    results = []

    for i, task_info in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] Processing: {task_info['task'][:50]}...")

        result = automation.run_pipeline(
            project=task_info["project"],
            task=task_info["task"],
            dry_run=True  # Симуляция
        )

        results.append({
            "task": task_info,
            "success": result["success"],
            "output": result["stdout"][:200] if result["stdout"] else ""
        })

        print(f"  Status: {'✅ Success' if result['success'] else '❌ Failed'}")

    # Сводка
    print("\n" + "-" * 40)
    print("Summary:")
    print(f"  Total: {len(results)}")
    print(f"  Success: {sum(1 for r in results if r['success'])}")
    print(f"  Failed: {sum(1 for r in results if not r['success'])}")


def example_scheduled_run():
    """
    Пример запуска по расписанию.
    """
    print("\n" + "=" * 60)
    print("Example: Scheduled Run")
    print("=" * 60)

    automation = PipelineAutomation()

    # Проверить день недели
    today = datetime.now()
    is_weekend = today.weekday() >= 5

    if is_weekend:
        print("Weekend detected - running full analysis")
        task = "Полный анализ кода и рефакторинг"
    else:
        print("Weekday - running quick check")
        task = "Быстрая проверка качества кода"

    result = automation.run_pipeline(
        project="GKSTCPLK-1872",
        task=task,
        dry_run=True
    )

    print(f"\nScheduled task result: {'✅' if result['success'] else '❌'}")


def example_conditional_workflow():
    """
    Пример условного workflow.
    """
    print("\n" + "=" * 60)
    print("Example: Conditional Workflow")
    print("=" * 60)

    automation = PipelineAutomation()

    # Шаг 1: Проверить список проектов
    print("Step 1: Check projects...")
    projects = automation.list_projects()

    if not projects.get("success"):
        print("❌ Failed to get projects")
        return

    # Шаг 2: Выбрать проект (симуляция)
    print("Step 2: Select project...")
    project_name = "GKSTCPLK-1872"

    # Шаг 3: Проверить статус
    print("Step 3: Check current status...")
    status = automation.get_status()

    if status.get("data", {}).get("status") == "in_progress":
        print("⚠️ Pipeline already running, skipping")
        return

    # Шаг 4: Запустить pipeline
    print("Step 4: Start pipeline...")
    result = automation.run_pipeline(
        project=project_name,
        task="Условный workflow - автоматическая задача",
        dry_run=True
    )

    print(f"\nWorkflow completed: {'✅' if result['success'] else '❌'}")


def example_report_generation():
    """
    Пример генерации отчёта.
    """
    print("\n" + "=" * 60)
    print("Example: Report Generation")
    print("=" * 60)

    automation = PipelineAutomation()

    report = {
        "generated_at": datetime.now().isoformat(),
        "sections": []
    }

    # Собрать данные о проектах
    print("Collecting projects data...")
    projects_result = automation.list_projects()
    report["sections"].append({
        "name": "Projects",
        "success": projects_result.get("success", False),
        "data": projects_result.get("data")
    })

    # Собрать статус
    print("Collecting status data...")
    status_result = automation.get_status()
    report["sections"].append({
        "name": "Current Status",
        "success": status_result.get("success", False),
        "data": status_result.get("data")
    })

    # Вывести отчёт
    print("\n" + "-" * 40)
    print("REPORT")
    print("-" * 40)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


def main():
    """Запуск примеров автоматизации."""
    print("=" * 60)
    print("Pipeline CLI - Automation Examples")
    print("=" * 60)

    examples = [
        example_batch_processing,
        example_scheduled_run,
        example_conditional_workflow,
        example_report_generation,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")

    print("\n" + "=" * 60)
    print("Automation examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
