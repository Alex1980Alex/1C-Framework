"""R0.2 verify: does tree-sitter-bsl miss queries, or did RMQ modules just lack them?"""
import tree_sitter_bsl as tsbsl
from tree_sitter import Language, Parser
from pathlib import Path

TARGET = Path(
    r"D:\1С-Framework\src\projects\configuration"
    r"\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС"
    r"\src\CommonModules\АдресныйКлассификатор\Ext\Module.bsl"
)

lang = Language(tsbsl.language())
parser = Parser(lang)
src = TARGET.read_bytes()
tree = parser.parse(src)
text = src.decode("utf-8", errors="replace")
lines = text.splitlines()

print(f"File: {TARGET.name}")
print(f"Lines: {len(lines)}")
print(f"Parse error: {tree.root_node.has_error}")

# Count literal ВЫБРАТЬ occurrences in source (ground truth)
literal_count = text.count("ВЫБРАТЬ")
print(f"Literal 'ВЫБРАТЬ' occurrences in source: {literal_count}")

# Walk AST — look for dedicated query-related node types
def walk(n):
    yield n
    for c in n.children:
        yield from walk(c)

query_types = set()
query_node_count = 0
string_with_query = 0
for n in walk(tree.root_node):
    tn = n.type
    if any(kw in tn.lower() for kw in ("query", "select", "выбрать")):
        query_types.add(tn)
        query_node_count += 1
    if tn in ("const_expression", "string_literal"):
        nodetext = src[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
        if "ВЫБРАТЬ" in nodetext:
            string_with_query += 1

print(f"Dedicated query node types found: {query_types or 'NONE'}")
print(f"Query-named nodes in AST: {query_node_count}")
print(f"String literals containing ВЫБРАТЬ: {string_with_query}")

# Show first query literal
for i, line in enumerate(lines, 1):
    if "ВЫБРАТЬ" in line:
        print(f"\nFirst ВЫБРАТЬ at line {i}: {line.strip()[:100]}")
        break
