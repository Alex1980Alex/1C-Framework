"""
QA Agent - Testing and Quality Assurance.

This module provides automated testing capabilities for the development pipeline:
- ResultAnalyzer: Parses result.md to extract code changes
- TestGenerator: Generates test cases based on spec.md requirements
- TestRunner: Executes tests and collects results
- ReportGenerator: Creates qa_report.md with test results

Usage:
    from pipeline.agents.qa import QAAgent

    agent = QAAgent()
    report = agent.run(
        result_artifact=result,
        spec_artifact=spec,
        design_artifact=design
    )
"""

from agents.qa.models import TestCase, TestResult, TestSuite, QAReport
from agents.qa.result_analyzer import ResultAnalyzer, analyze_result
from agents.qa.test_generator import TestGenerator, generate_tests, BSLTestTemplates
from agents.qa.test_runner import TestRunner, create_runner, create_dry_runner
from agents.qa.report_generator import ReportGenerator
from agents.qa.agent import (
    QAAgent,
    QAAgentConfig,
    QAContext,
    create_qa_agent,
    run_qa,
)

__all__ = [
    # Main Agent
    "QAAgent",
    "QAAgentConfig",
    "QAContext",
    # Factory functions
    "create_qa_agent",
    "run_qa",
    # Components
    "ResultAnalyzer",
    "TestGenerator",
    "TestRunner",
    "ReportGenerator",
    # Factory functions for components
    "analyze_result",
    "generate_tests",
    "create_runner",
    "create_dry_runner",
    "BSLTestTemplates",
    # Models
    "TestCase",
    "TestResult",
    "TestSuite",
    "QAReport",
]
