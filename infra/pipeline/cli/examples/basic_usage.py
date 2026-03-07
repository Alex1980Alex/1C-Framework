#!/usr/bin/env python3
"""
Basic CLI Usage Examples.

Примеры базового использования Pipeline CLI.

Версия: 1.0.0
Дата: 2025-12-23
"""

import subprocess
import sys
from pathlib import Path


def run_cli_command(args: list[str]) -> tuple[int, str, str]:
    """
    Запускает CLI команду и возвращает результат.

    Returns:
        Tuple[int, str, str]: (exit_code, stdout, stderr)
    """
    result = subprocess.run(
        [sys.executable, "-m", "shared.pipeline.cli"] + args,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[4]  # Корень проекта
    )
    return result.returncode, result.stdout, result.stderr


def example_show_help():
    """Показать справку CLI."""
    print("\n" + "=" * 60)
    print("Example: Show Help")
    print("=" * 60)

    code, stdout, stderr = run_cli_command(["--help"])
    print(stdout)


def example_show_version():
    """Показать версию CLI."""
    print("\n" + "=" * 60)
    print("Example: Show Version")
    print("=" * 60)

    code, stdout, stderr = run_cli_command(["--version"])
    print(stdout)


def example_list_projects():
    """Показать список проектов."""
    print("\n" + "=" * 60)
    print("Example: List Projects")
    print("=" * 60)

    code, stdout, stderr = run_cli_command(["list", "projects"])
    print(stdout)
    if stderr:
        print(f"Errors: {stderr}")


def example_show_config():
    """Показать конфигурацию."""
    print("\n" + "=" * 60)
    print("Example: Show Configuration")
    print("=" * 60)

    code, stdout, stderr = run_cli_command(["config", "show"])
    print(stdout)


def example_dry_run():
    """Запустить pipeline в режиме симуляции."""
    print("\n" + "=" * 60)
    print("Example: Dry Run")
    print("=" * 60)

    code, stdout, stderr = run_cli_command([
        "run",
        "--project", "GKSTCPLK-1872",
        "--task", "Тестовая задача",
        "--dry-run"
    ])
    print(stdout)
    if stderr:
        print(f"Errors: {stderr}")


def example_json_output():
    """Вывод в формате JSON."""
    print("\n" + "=" * 60)
    print("Example: JSON Output")
    print("=" * 60)

    code, stdout, stderr = run_cli_command([
        "list", "projects",
        "--format", "json"
    ])
    print(stdout)


def main():
    """Запуск всех примеров."""
    print("=" * 60)
    print("Pipeline CLI - Basic Usage Examples")
    print("=" * 60)

    examples = [
        example_show_help,
        example_show_version,
        example_list_projects,
        example_show_config,
        example_dry_run,
        example_json_output,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
