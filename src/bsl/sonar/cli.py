"""
SonarQube Integration CLI

Phase 45: Миграция из 1C-Enterprise_Framework

Запуск: python -m src.bsl.sonar.cli --help
"""

import argparse
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Создание парсера аргументов"""
    parser = argparse.ArgumentParser(
        prog="bsl-sonar",
        description="SonarQube Integration for BSL Code"
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


def cmd_analyze(args):
    """Команда анализа"""
    from .rules_manager import RulesManager
    from .report_generator import ReportGenerator, Issue

    logger.info(f"Analyzing BSL code at: {args.path}")

    # TODO: Реальный анализ
    issues = []

    report_gen = ReportGenerator()
    report = report_gen.generate(issues)

    # Экспорт
    markdown = report_gen.export_markdown(report)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown)

    logger.info(f"Report saved to: {args.output}")
    print(f"Quality Gate: {'PASSED' if report.quality_gate else 'FAILED'}")


def cmd_rules(args):
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


def cmd_config(args):
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


def main():
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
