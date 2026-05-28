"""
SonarQube Integration CLI

Phase 45: Миграция из 1C-Enterprise_Framework

Запуск: python -m src.bsl.sonar.cli --help
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Создание парсера аргументов"""
    parser = argparse.ArgumentParser(
        prog="bsl-sonar", description="SonarQube Integration for BSL Code"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze BSL code")
    analyze_parser.add_argument("--path", required=True, help="Path to BSL code")
    analyze_parser.add_argument("--output", default="report.md", help="Output report file")

    # rules command
    rules_parser = subparsers.add_parser("rules", help="List available rules")
    rules_parser.add_argument("--tag", help="Filter by tag")

    # config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_parser.add_argument("--show", action="store_true", help="Show current config")

    return parser


def cmd_analyze(args: argparse.Namespace) -> None:
    """Команда анализа через sonar-scanner subprocess"""
    import shutil
    import subprocess
    from pathlib import Path

    from .config_manager import ConfigManager

    logger.info(f"Analyzing BSL code at: {args.path}")

    manager = ConfigManager()
    config = manager.load()

    scanner = config.sonar_scanner_path
    if not Path(scanner).exists():
        fallback = shutil.which("sonar-scanner")
        if fallback:
            scanner = fallback
        else:
            logger.error("sonar-scanner not found at %s and not in PATH", scanner)
            sys.exit(1)

    project_key = config.project_key or Path(args.path).name
    cmd = [
        scanner,
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.sources={args.path}",
        f"-Dsonar.host.url={config.host}",
    ]
    if config.token:
        cmd.append(f"-Dsonar.token={config.token}")

    cmd_log = [arg if not arg.startswith("-Dsonar.token=") else "-Dsonar.token=***" for arg in cmd]
    logger.info("Running: %s", " ".join(cmd_log))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    issues_url = f"{config.host}/dashboard?id={project_key}"
    if result.returncode == 0:
        logger.info("Analysis completed successfully")
        print("Quality Gate: PASSED")
        print(f"Results: {issues_url}")
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(
                f"# SonarQube Analysis Report\n\nQuality Gate: PASSED\n\nResults: {issues_url}\n"
            )
        logger.info(f"Report saved to: {args.output}")
    else:
        logger.error("sonar-scanner failed (exit %d):\n%s", result.returncode, result.stderr)
        print("Quality Gate: FAILED")
        if result.stdout:
            print(result.stdout[-2000:])
        sys.exit(result.returncode)


def cmd_rules(args: argparse.Namespace) -> None:
    """Команда списка правил"""
    from .rules_manager import RulesManager

    manager = RulesManager()

    if args.tag:
        rules = manager.get_rules_by_tag(args.tag)
    else:
        rules = manager.get_all_rules()

    print(f"Available BSL Rules ({len(rules)}):")
    print()
    for rule in rules:
        print(f"  [{rule.severity}] {rule.key}")
        print(f"      {rule.name}")
        print(f"      Tags: {', '.join(rule.tags)}")
        print()


def cmd_config(args: argparse.Namespace) -> None:
    """Команда конфигурации"""
    from .config_manager import ConfigManager

    manager = ConfigManager()
    config = manager.load()

    if args.show:
        print("Current SonarQube Configuration:")
        print(f"  Host: {config.host}")
        print(f"  Project: {config.project_key}")
        print(f"  Sources: {config.sources}")
        print(f"  Quality Profile: {config.quality_profile}")


def main() -> None:
    """Точка входа CLI"""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "rules":
        cmd_rules(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
