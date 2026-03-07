"""
Setup script for development-pipeline package.

Installs the package as 'devpipeline' to avoid Python's hyphen limitation.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent.parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="devpipeline",
    version="0.1.0",
    author="Claude Code",
    description="Multi-Agent System for 1C Development",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests*", "tests.*", "*.tests"]),
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.0.0",
        "pytest>=7.0.0",
        "pytest-cov>=4.0.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
