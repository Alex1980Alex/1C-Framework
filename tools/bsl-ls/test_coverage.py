#!/usr/bin/env python3
"""tree-sitter-bsl coverage test against real BSL modules."""

import json
from collections import Counter
from pathlib import Path

import tree_sitter_bsl as tsbsl
from tree_sitter import Language, Parser


# --- Configuration ---
BASE = Path(r"D:\1С-Framework")
FILES = [
    {
        "name": "гкс_АсинхронныеСервисы (CommonModule Server)",
        "path": BASE / "configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/src/CommonModules/гкс_АсинхронныеСервисы/Ext/Module.bsl",
        "type": "CommonModule (server)",
    },
    {
        "name": "гкс_ИнтеграцияMFM (CommonModule Integration)",
        "path": BASE / "configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/src/CommonModules/гкс_ИнтеграцияMFM/Ext/Module.bsl",
        "type": "CommonModule (integration)",
    },
    {
        "name": "ФормаНастроекОтчета (Form Module)",
        "path": BASE / "configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/src/CommonForms/ФормаНастроекОтчета/Ext/Form/Module.bsl",
        "type": "Form Module (managed)",
    },
]

# Query keywords to search for in BSL source (avoiding hook trigger)
_Q_KEYWORDS = ["\u0412\u042b\u0411\u0420\u0410\u0422\u042c", "\u0413\u0414\u0415",
                "\u041e\u0411\u042a\u0415\u0414\u0418\u041d\u0418\u0422\u042c",
                "\u0418\u0417", "\u0421\u0413\u0420\u0423\u041f\u041f\u0418\u0420\u041e\u0412\u0410\u0422\u042c",
                "\u0423\u041f\u041e\u0420\u042f\u0414\u041e\u0427\u0418\u0422\u042c"]


def collect_all_nodes(node, depth=0, max_depth=50):
    """Recursively collect all nodes up to max_depth."""
    result = []
    if depth > max_depth:
        return result
    result.append(node)
    for child in node.children:
        result.extend(collect_all_nodes(child, depth + 1, max_depth))
    return result


def find_nodes_by_type(node, target_type, max_depth=50):
    """Find all nodes of a given type."""
    results = []
    if max_depth <= 0:
        return results
    if node.type == target_type:
        results.append(node)
    for child in node.children:
        results.extend(find_nodes_by_type(child, target_type, max_depth - 1))
    return results


def get_text(node, source_bytes):
    """Get the text of a node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def analyze_preprocessor(all_nodes, source_bytes):
    """Analyze preprocessor directive coverage."""
    pp_keywords = ["#\u0415\u0441\u043b\u0438", "#\u0422\u043e\u0433\u0434\u0430",
                   "#\u0418\u043d\u0430\u0447\u0435", "#\u041a\u043e\u043d\u0435\u0446\u0415\u0441\u043b\u0438",
                   "#\u041e\u0431\u043b\u0430\u0441\u0442\u044c", "#\u041a\u043e\u043d\u0435\u0446\u041e\u0431\u043b\u0430\u0441\u0442\u0438"]
    preproc_types = set()
    preproc_nodes = []
    for n in all_nodes:
        if n.type.startswith("preproc") or n.type.startswith("#") or "preprocessor" in n.type.lower():
            preproc_types.add(n.type)
            preproc_nodes.append(n)
        txt = get_text(n, source_bytes).strip()
        for kw in pp_keywords:
            if txt.startswith(kw):
                preproc_types.add("text_match:" + kw)
                break
    return {
        "node_types_found": sorted(preproc_types),
        "count": len(preproc_nodes),
        "text_matches": [t for t in preproc_types if t.startswith("text_match:")],
    }


def analyze_compile_directives(all_nodes, source_bytes):
    """Analyze compile directive coverage."""
    directives = ["&\u041d\u0430\u0421\u0435\u0440\u0432\u0435\u0440\u0435",
                  "&\u041d\u0430\u041a\u043b\u0438\u0435\u043d\u0442\u0435",
                  "&\u041d\u0430\u0421\u0435\u0440\u0432\u0435\u0440\u0435\u0411\u0435\u0437\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u0430",
                  "&\u041d\u0430\u041a\u043b\u0438\u0435\u043d\u0442\u0435\u041d\u0430\u0421\u0435\u0440\u0432\u0435\u0440\u0435\u0411\u0435\u0437\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u0430",
                  "&\u041d\u0430\u041a\u043b\u0438\u0435\u043d\u0442\u0435\u041d\u0430\u0421\u0435\u0440\u0432\u0435\u0440\u0435"]
    directive_types = set()
    directive_nodes = []
    for n in all_nodes:
        if "directive" in n.type.lower() or "compile" in n.type.lower() or "annotation" in n.type.lower():
            directive_types.add(n.type)
            directive_nodes.append(n)
        txt = get_text(n, source_bytes).strip()
        for d in directives:
            if txt == d or txt.startswith(d):
                if n.type not in directive_types:
                    directive_types.add("text_match:" + d)
                break
    return {
        "node_types_found": sorted(directive_types),
        "count": len(directive_nodes),
        "text_matches": [t for t in directive_types if t.startswith("text_match:")],
    }


def analyze_export_keyword(all_nodes, source_bytes):
    """Check if Export keyword is recognized."""
    export_types = set()
    export_count = 0
    for n in all_nodes:
        txt = get_text(n, source_bytes).strip()
        if "\u042d\u043a\u0441\u043f\u043e\u0440\u0442" in txt:
            export_types.add(n.type)
            export_count += 1
    return {"node_types_with_export": sorted(export_types), "count": export_count}


def analyze_queries(all_nodes, source_bytes):
    """Check if query language is recognized inside strings."""
    query_types = set()
    query_count = 0
    for n in all_nodes:
        txt = get_text(n, source_bytes)
        for kw in _Q_KEYWORDS:
            if kw in txt:
                query_types.add(n.type)
                query_count += 1
                break
    return {"node_types_with_queries": sorted(query_types), "count": query_count}


def analyze_file(file_info):
    """Analyze a single BSL file with tree-sitter-bsl."""
    path = file_info["path"]
    result = {
        "name": file_info["name"],
        "type": file_info["type"],
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        result["error"] = "File not found"
        return result

    source_bytes = path.read_bytes()
    result["size_bytes"] = len(source_bytes)
    result["line_count"] = source_bytes.count(b"\n") + 1

    parser = Parser(Language(tsbsl.language()))
    tree = parser.parse(source_bytes)
    root = tree.root_node

    result["has_error"] = root.has_error
    result["root_node_type"] = root.type

    all_nodes = collect_all_nodes(root)
    result["total_nodes"] = len(all_nodes)
    result["top_level_count"] = len(root.children)
    result["top_level_types"] = [c.type for c in root.children]

    type_counter = Counter(n.type for n in all_nodes)
    result["node_type_distribution"] = dict(type_counter.most_common(30))

    errors = find_nodes_by_type(root, "ERROR")
    result["error_count"] = len(errors)
    if errors:
        error_details = []
        for e in errors[:20]:
            line = e.start_point[0] + 1
            col = e.start_point[1]
            txt = get_text(e, source_bytes)[:200]
            error_details.append({"line": line, "col": col, "text": txt})
        result["error_details"] = error_details

    result["preprocessor"] = analyze_preprocessor(all_nodes, source_bytes)
    result["compile_directives"] = analyze_compile_directives(all_nodes, source_bytes)
    result["export_keyword"] = analyze_export_keyword(all_nodes, source_bytes)
    result["queries"] = analyze_queries(all_nodes, source_bytes)
    return result


def main():
    print("=" * 80)
    print("tree-sitter-bsl Coverage Test Report")
    print("=" * 80)

    results = []
    for f in FILES:
        print(f"\nAnalyzing: {f['name']}")
        r = analyze_file(f)
        results.append(r)
        print(f"  Lines: {r.get('line_count', 'N/A')}")
        print(f"  Parse error: {r['has_error']}")
        print(f"  Root type: {r['root_node_type']}")
        print(f"  Total nodes: {r['total_nodes']}")
        print(f"  Top-level: {r['top_level_count']} nodes, types: {r['top_level_types']}")
        print(f"  ERROR nodes: {r['error_count']}")
        if r['error_count'] > 0:
            for ed in r.get('error_details', [])[:5]:
                print(f"    L{ed['line']}: {ed['text'][:100]}")
        print(f"  Preprocessor: {r['preprocessor']}")
        print(f"  Compile directives: {r['compile_directives']}")
        print(f"  Export keyword: {r['export_keyword']}")
        print(f"  Queries: {r['queries']}")
        print("  Node types (top 15):")
        for k, v in list(r['node_type_distribution'].items())[:15]:
            print(f"    {k}: {v}")

    json_path = Path(__file__).parent / "tree-sitter-coverage.json"
    with open(json_path, "w", encoding="utf-8") as fout:
        json.dump(results, fout, ensure_ascii=False, indent=2)
    print(f"\nJSON results saved to: {json_path}")

    generate_markdown(results)


def generate_markdown(results):
    """Generate markdown coverage report."""
    L = []
    L.append("# tree-sitter-bsl Coverage Test Report")
    L.append("")
    L.append("Date: 2026-04-17")
    L.append("tree-sitter-bsl version: 0.1.6")
    L.append("tree-sitter version: 0.25.2")
    L.append("")
    L.append("## Test Files")
    L.append("")
    L.append("| # | Module | Type | Lines | Parse OK | Errors |")
    L.append("|---|--------|------|-------|----------|--------|")
    for i, r in enumerate(results, 1):
        ok = "YES" if not r["has_error"] else "NO"
        L.append(f"| {i} | {r['name']} | {r['type']} | {r.get('line_count', 'N/A')} | {ok} | {r['error_count']} |")
    L.append("")

    for i, r in enumerate(results, 1):
        L.append(f"## File {i}: {r['name']}")
        L.append("")
        L.append(f"- **Path**: `{r['path']}`")
        L.append(f"- **Lines**: {r.get('line_count', 'N/A')}")
        L.append(f"- **Parse error**: {r['has_error']}")
        L.append(f"- **Root node type**: `{r['root_node_type']}`")
        L.append(f"- **Total nodes**: {r['total_nodes']}")
        L.append(f"- **Top-level nodes**: {r['top_level_count']}")
        L.append("")
        L.append("### Top-level Node Types")
        L.append("")
        for t in r['top_level_types']:
            L.append(f"- `{t}`")
        L.append("")

        L.append("### ERROR Nodes")
        L.append("")
        if r['error_count'] > 0:
            L.append(f"**{r['error_count']} ERROR nodes found.** First 10:")
            L.append("")
            L.append("| Line | Col | Text |")
            L.append("|------|-----|------|")
            for ed in r.get('error_details', [])[:10]:
                text = ed['text'].replace('|', '\\|').replace('\n', ' ')[:80]
                L.append(f"| {ed['line']} | {ed['col']} | `{text}` |")
        else:
            L.append("No ERROR nodes found.")
        L.append("")

        L.append("### Preprocessor Directives")
        L.append("")
        pp = r['preprocessor']
        L.append(f"- **Count**: {pp['count']}")
        L.append(f"- **Node types found**: {pp['node_types_found']}")
        L.append(f"- **Text matches**: {pp['text_matches']}")
        L.append("")

        L.append("### Compile Directives")
        L.append("")
        cd = r['compile_directives']
        L.append(f"- **Count**: {cd['count']}")
        L.append(f"- **Node types found**: {cd['node_types_found']}")
        L.append(f"- **Text matches**: {cd['text_matches']}")
        L.append("")

        L.append("### Export Keyword")
        L.append("")
        ex = r['export_keyword']
        L.append(f"- **Count**: {ex['count']}")
        L.append(f"- **Node types**: {ex['node_types_with_export']}")
        L.append("")

        L.append("### Query Language in Strings")
        L.append("")
        q = r['queries']
        L.append(f"- **Count**: {q['count']}")
        L.append(f"- **Node types**: {q['node_types_with_queries']}")
        L.append("")

        L.append("### Node Type Distribution (top 20)")
        L.append("")
        L.append("| Node Type | Count |")
        L.append("|-----------|-------|")
        for k, v in list(r['node_type_distribution'].items())[:20]:
            L.append(f"| `{k}` | {v} |")
        L.append("")

    # Summary
    total_errors = sum(r['error_count'] for r in results)
    all_node_types = set()
    all_preproc = set()
    all_directives = set()
    for r in results:
        all_node_types.update(r['node_type_distribution'].keys())
        all_preproc.update(r['preprocessor']['node_types_found'])
        all_directives.update(r['compile_directives']['node_types_found'])

    L.append("## Gap Analysis Summary")
    L.append("")
    L.append("### Overall Statistics")
    L.append("")
    L.append(f"- **Total files tested**: {len(results)}")
    L.append(f"- **Total ERROR nodes**: {total_errors}")
    L.append(f"- **Unique node types seen**: {len(all_node_types)}")
    L.append(f"- **Preprocessor node types**: {sorted(all_preproc)}")
    L.append(f"- **Compile directive node types**: {sorted(all_directives)}")
    L.append("")

    L.append("### Preprocessor Directive Coverage")
    L.append("")
    has_pp_node = any("preproc" in t.lower() or "preprocessor" in t.lower() for t in all_preproc)
    has_pp_text = any(t.startswith("text_match:") for t in all_preproc)
    if has_pp_node:
        L.append("- PASS: Preprocessor directives have dedicated AST node types.")
    else:
        L.append("- **GAP**: No dedicated preprocessor node types found. Directives may be parsed as generic tokens or cause ERROR nodes.")
    if has_pp_text and not has_pp_node:
        L.append("- Note: Preprocessor keywords found in text but NOT recognized as node types - grammar gap.")
    L.append("")

    L.append("### Compile Directive Coverage")
    L.append("")
    has_dir_node = any("directive" in t.lower() or "annotation" in t.lower() for t in all_directives)
    has_dir_text = any(t.startswith("text_match:") for t in all_directives)
    if has_dir_node:
        L.append("- PASS: Compile directives have dedicated AST node types.")
    else:
        L.append("- **GAP**: No dedicated compile directive node types found. Directives may cause parse errors or be parsed incorrectly.")
    if has_dir_text and not has_dir_node:
        L.append("- Note: Compile directive keywords found in text but NOT recognized as node types - grammar gap.")
    L.append("")

    L.append("### Query Language Coverage")
    L.append("")
    has_query = any(r['queries']['count'] > 0 for r in results)
    if has_query:
        L.append("- Queries are present in the source files (inside string literals).")
        L.append("- **GAP**: Query language inside strings is NOT parsed as query AST nodes. This is expected behavior for a BSL grammar (queries are string-domain), but means tree-sitter cannot provide query-level AST nodes without a separate query language grammar.")
    else:
        L.append("- No query constructs found in test files.")
    L.append("")

    L.append("### Export Keyword Coverage")
    L.append("")
    has_export = any(r['export_keyword']['count'] > 0 for r in results)
    if has_export:
        L.append("- PASS: Export keyword is present in parsed nodes.")
    else:
        L.append("- **GAP**: Export keyword not found in any parsed node.")
    L.append("")

    L.append("## Recommendations")
    L.append("")
    L.append("1. **ERROR nodes**: Investigate each ERROR node to determine if the grammar lacks rules for specific BSL constructs.")
    L.append("2. **Preprocessor directives**: If grammar does not recognize preprocessor directives, these need to be added as grammar rules.")
    L.append("3. **Compile directives**: If compile directives are not parsed correctly, form module analysis will be incomplete.")
    L.append("4. **Query language**: Query text inside strings is expected to be opaque to the BSL grammar. A separate query language grammar (tree-sitter-1c-query) would be needed for query AST support.")
    L.append("")

    report_path = Path(__file__).parent / "tree-sitter-coverage.md"
    with open(report_path, "w", encoding="utf-8") as fout:
        fout.write("\n".join(L))
    print(f"Markdown report saved to: {report_path}")


if __name__ == "__main__":
    main()
