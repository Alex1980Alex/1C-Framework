"""Unit tests for framework_search.python_chunker.chunk_python()."""

from __future__ import annotations

import pytest

from framework_search.python_chunker import chunk_python

pytestmark = pytest.mark.unit


class TestChunkPythonFunctions:
    def test_simple_function(self) -> None:
        src = "def foo():\n    return 1\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        funcs = [c for c in chunks if c.chunk_type == "function"]
        assert len(funcs) == 1
        assert funcs[0].symbol_name == "foo"

    def test_async_function(self) -> None:
        src = "async def bar():\n    pass\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        funcs = [c for c in chunks if c.chunk_type == "function"]
        assert len(funcs) == 1
        assert funcs[0].symbol_name == "bar"

    def test_multiple_functions(self) -> None:
        src = "def a():\n    pass\n\ndef b():\n    pass\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        names = {c.symbol_name for c in chunks if c.chunk_type == "function"}
        assert names == {"a", "b"}

    def test_decorated_function(self) -> None:
        src = "@staticmethod\ndef decorated():\n    pass\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        funcs = [c for c in chunks if c.chunk_type == "function"]
        assert any(c.symbol_name == "decorated" for c in funcs)


class TestChunkPythonClasses:
    def test_small_class(self) -> None:
        src = "class MyClass:\n    x = 1\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        cls_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(cls_chunks) >= 1
        assert cls_chunks[0].symbol_name == "MyClass"

    def test_class_with_method(self) -> None:
        src = "class Foo:\n    def bar(self):\n        pass\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        # small class: either single class chunk or class + function
        symbols = {c.symbol_name for c in chunks if c.symbol_name}
        assert "Foo" in symbols or "Foo.bar" in symbols


class TestChunkPythonModule:
    def test_imports_become_module_chunk(self) -> None:
        src = "import os\nimport sys\n\ndef f():\n    pass\n"
        chunks = chunk_python("src/x.py", src, 1.0)
        module_chunks = [c for c in chunks if c.chunk_type == "module"]
        assert len(module_chunks) >= 1

    def test_empty_file(self) -> None:
        chunks = chunk_python("src/x.py", "", 1.0)
        assert chunks == []

    def test_whitespace_only(self) -> None:
        chunks = chunk_python("src/x.py", "   \n\n  ", 1.0)
        assert chunks == []


class TestChunkPythonFallback:
    def test_syntax_error_falls_back(self) -> None:
        src = "def broken(\n    return"
        chunks = chunk_python("src/x.py", src, 1.0)
        assert len(chunks) >= 1

    def test_fallback_chunk_type_is_text(self) -> None:
        src = "def broken(\n    return"
        chunks = chunk_python("src/x.py", src, 1.0)
        assert all(c.chunk_type == "text" for c in chunks)


class TestChunkPythonLineNumbers:
    def test_line_start_gte_1(self) -> None:
        src = "def foo():\n    pass\n"
        for c in chunk_python("src/x.py", src, 1.0):
            assert c.line_start >= 1

    def test_line_end_gte_line_start(self) -> None:
        src = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        for c in chunk_python("src/x.py", src, 1.0):
            assert c.line_end >= c.line_start


class TestChunkPythonAttributes:
    def test_language_is_python(self) -> None:
        src = "def foo():\n    pass\n"
        for c in chunk_python("src/x.py", src, 1.0):
            assert c.language == "python"

    def test_mtime_preserved(self) -> None:
        src = "def foo():\n    pass\n"
        mtime = 12345.678
        for c in chunk_python("src/x.py", src, mtime):
            assert c.mtime == mtime

    def test_relative_path_preserved(self) -> None:
        src = "def foo():\n    pass\n"
        for c in chunk_python("src/module.py", src, 1.0):
            assert c.relative_path == "src/module.py"
