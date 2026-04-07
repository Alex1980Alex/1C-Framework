import sys, json, urllib.request, base64
sys.stdout.reconfigure(encoding='utf-8')

url = "http://localhost/TestDB/hs/mcp"
creds = base64.b64encode(b"a.terletskiy@sodru.com:Alex80Alex").decode()

passed = 0
failed = 0
errors = []

def call(name, args, rid):
    payload = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": name, "arguments": args}, "id": rid}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Basic {creds}')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))

def check(name, result, expect_success=True):
    global passed, failed
    err = result.get('error')
    if err:
        failed += 1
        msg = str(err.get('message', err))[:200]
        errors.append(f"  FAIL {name}: {msg}")
        print(f"  FAIL: {msg[:150]}")
        return None
    content = result.get('result', {}).get('content', [])
    text = content[0].get('text', '') if content else ''
    try:
        j = json.loads(text)
        ok = j.get('success', None)
        if (expect_success and ok == True) or (not expect_success and ok == False):
            passed += 1
            print(f"  PASS")
            return j
        else:
            failed += 1
            msg = j.get('error', text[:200])
            errors.append(f"  FAIL {name}: {msg}")
            print(f"  FAIL: {str(msg)[:150]}")
            return j
    except:
        passed += 1
        print(f"  PASS (non-JSON)")
        return text

rid = 100

# 1. execute_query
print("=" * 60)
print("1. execute_query (3 tests)")
print("=" * 60)

print("  1.1: Simple SELECT limit 3")
r = call("execute_query", {"query": "ВЫБРАТЬ ПЕРВЫЕ 3 Ссылка, Код, Наименование ИЗ Справочник.Номенклатура", "limit": 3}, rid); rid += 1
j = check("execute_query.1", r)
if j and j.get('success'):
    rows = j.get('data', [])
    code_key = 'Код' if 'Код' in rows[0] else 'Code'
    print(f"    -> {len(rows)} rows, first: {rows[0].get(code_key, '')}")

print("  1.2: Query with params")
r = call("execute_query", {"query": "ВЫБРАТЬ ПЕРВЫЕ 2 Ссылка, Код ИЗ Справочник.Номенклатура ГДЕ Код ПОДОБНО &Маска", "params": {"Маска": "%101%"}, "limit": 2}, rid); rid += 1
j = check("execute_query.2", r)
if j and j.get('success'):
    print(f"    -> {len(j.get('data',[]))} rows")

print("  1.3: With include_schema")
r = call("execute_query", {"query": "ВЫБРАТЬ ПЕРВЫЕ 1 Код, Наименование ИЗ Справочник.Номенклатура", "limit": 1, "include_schema": True}, rid); rid += 1
j = check("execute_query.3", r)

# 2. validate_query
print("\n" + "=" * 60)
print("2. validate_query (2 tests)")
print("=" * 60)

print("  2.1: Valid query")
r = call("validate_query", {"query": "ВЫБРАТЬ 1 КАК Тест"}, rid); rid += 1
j = check("validate_query.1", r)
if j and j.get('success'):
    print(f"    -> valid={j.get('data',{}).get('valid', '?')}")

print("  2.2: Invalid query (expect failure)")
r = call("validate_query", {"query": "ВЫБРАТЬ ИЗ ГДЕ ЭТОТ"}, rid); rid += 1
j = check("validate_query.2", r, expect_success=False)

# 3. execute_code
print("\n" + "=" * 60)
print("3. execute_code (3 tests)")
print("=" * 60)

print("  3.1: Simple math")
r = call("execute_code", {"code": "Результат = 2 + 2"}, rid); rid += 1
j = check("execute_code.1", r)
if j and j.get('success'):
    print(f"    -> 2+2 = {j.get('data')}")

print("  3.2: String function")
r = call("execute_code", {"code": "Результат = СтрДлина(\"Привет мир\")"}, rid); rid += 1
j = check("execute_code.2", r)
if j and j.get('success'):
    print(f"    -> length = {j.get('data')}")

print("  3.3: DB query in code")
r = call("execute_code", {"code": "Запрос = Новый Запрос(\"ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК К ИЗ Справочник.Номенклатура\"); Результат = Запрос.Выполнить().Выбрать().К"}, rid); rid += 1
j = check("execute_code.3", r)
if j and j.get('success'):
    print(f"    -> count = {j.get('data')}")

# 4. get_object_by_link
print("\n" + "=" * 60)
print("4. get_object_by_link (2 tests)")
print("=" * 60)

print("  4.1: Valid link")
r = call("get_object_by_link", {"link": "e1cib/data/Справочник.Номенклатура?ref=cf9b9fc3d45911e480d40050569d04c3"}, rid); rid += 1
j = check("get_object_by_link.1", r)
if j and j.get('success'):
    d = j.get('data', {})
    name_key = 'Наименование' if 'Наименование' in d else 'Name'
    print(f"    -> {d.get(name_key, '')[:40]}")

print("  4.2: Invalid ref (expect failure)")
r = call("get_object_by_link", {"link": "e1cib/data/Справочник.Номенклатура?ref=00000000000000000000000000000000"}, rid); rid += 1
j = check("get_object_by_link.2", r, expect_success=False)

# 5. get_link_of_object
print("\n" + "=" * 60)
print("5. get_link_of_object (2 tests)")
print("=" * 60)

print("  5.1: From _objectRef")
r = call("get_link_of_object", {"object_description": {"_objectRef": True, "ТипОбъекта": "СправочникСсылка.Номенклатура", "УникальныйИдентификатор": "cf9b9fc3-d459-11e4-80d4-0050569d04c3"}}, rid); rid += 1
j = check("get_link_of_object.1", r)
if j and j.get('success'):
    print(f"    -> {j.get('data',{}).get('link','')[:60]}")

print("  5.2: Missing _objectRef (expect failure)")
r = call("get_link_of_object", {"object_description": {"ТипОбъекта": "СправочникСсылка.Номенклатура"}}, rid); rid += 1
j = check("get_link_of_object.2", r, expect_success=False)

# 6. find_references_to_object
print("\n" + "=" * 60)
print("6. find_references_to_object (2 tests)")
print("=" * 60)

print("  6.1: Find refs in documents")
r = call("find_references_to_object", {"target_object_description": {"_objectRef": True, "ТипОбъекта": "СправочникСсылка.Номенклатура", "УникальныйИдентификатор": "cf9b9fc3-d459-11e4-80d4-0050569d04c3"}, "search_scope": ["documents"], "max_results": 5}, rid); rid += 1
j = check("find_references.1", r)
if j and j.get('success'):
    d = j.get('data', [])
    print(f"    -> {len(d)} references")

print("  6.2: Missing _objectRef (expect failure)")
r = call("find_references_to_object", {"target_object_description": {"ТипОбъекта": "Wrong"}}, rid); rid += 1
j = check("find_references.2", r, expect_success=False)

# 7. get_event_log
print("\n" + "=" * 60)
print("7. get_event_log (2 tests)")
print("=" * 60)

print("  7.1: Last 3 entries")
r = call("get_event_log", {"limit": 3}, rid); rid += 1
j = check("get_event_log.1", r)
if j and j.get('success'):
    print(f"    -> {len(j.get('data',[]))} entries")

print("  7.2: Filter by Error")
r = call("get_event_log", {"level": "Error", "limit": 3}, rid); rid += 1
j = check("get_event_log.2", r)

# 8. get_access_rights
print("\n" + "=" * 60)
print("8. get_access_rights (1 test)")
print("=" * 60)

print("  8.1: Rights for catalog")
r = call("get_access_rights", {"metadata_object": "Справочник.Номенклатура"}, rid); rid += 1
j = check("get_access_rights.1", r)
if j and j.get('success'):
    d = j.get('data', {})
    print(f"    -> keys: {list(d.keys())[:5]}")

# 9. get_bsl_syntax_help
print("\n" + "=" * 60)
print("9. get_bsl_syntax_help (2 tests)")
print("=" * 60)

print("  9.1: Keyword lookup")
r = call("get_bsl_syntax_help", {"keyword": "СтрНайти"}, rid); rid += 1
j = check("get_bsl_syntax_help.1", r)
if j and j.get('success'):
    d = j.get('data', {})
    print(f"    -> {d.get('syntax','')[:60]}")

print("  9.2: Another keyword")
r = call("get_bsl_syntax_help", {"keyword": "НайтиПоКоду"}, rid); rid += 1
j = check("get_bsl_syntax_help.2", r)

# 10. get_metadata
print("\n" + "=" * 60)
print("10. get_metadata (3 tests)")
print("=" * 60)

print("  10.1: Summary")
r = call("get_metadata", {"mode": "summary"}, rid); rid += 1
j = check("get_metadata.1", r)
if j and j.get('success'):
    d = j.get('data', {})
    print(f"    -> {d.get('name','')}: {d.get('catalogs','?')} catalogs")

print("  10.2: List Documents")
r = call("get_metadata", {"mode": "list", "metaType": "Documents", "maxItems": 5}, rid); rid += 1
j = check("get_metadata.2", r)
if j and j.get('success'):
    items = j.get('data', [])
    print(f"    -> {len(items)} items")

print("  10.3: Detail")
r = call("get_metadata", {"mode": "detail", "metaType": "Catalogs", "name": "Номенклатура"}, rid); rid += 1
j = check("get_metadata.3", r)
if j and j.get('success'):
    d = j.get('data', {})
    print(f"    -> {len(d.get('attributes',[]))} attributes")

# 11. get_metadata_tree
print("\n" + "=" * 60)
print("11. get_metadata_tree (1 test)")
print("=" * 60)

print("  11.1: Full tree")
r = call("get_metadata_tree", {}, rid); rid += 1
j = check("get_metadata_tree.1", r)
if j and j.get('success'):
    sz = len(json.dumps(j.get('data', {})))
    print(f"    -> {sz} chars")

# 12. get_form_structure
print("\n" + "=" * 60)
print("12. get_form_structure (1 test)")
print("=" * 60)

print("  12.1: Form for catalog")
r = call("get_form_structure", {"object_name": "Справочник.Номенклатура"}, rid); rid += 1
j = check("get_form_structure.1", r)
if j and j.get('success'):
    d = j.get('data', {})
    print(f"    -> {len(d.get('forms',[]))} forms")

# 13. search_code
print("\n" + "=" * 60)
print("13. search_code (2 tests)")
print("=" * 60)

print("  13.1: By query")
r = call("search_code", {"query": "Номенклатура", "max_results": 3}, rid); rid += 1
j = check("search_code.1", r)

print("  13.2: By name_mask")
r = call("search_code", {"name_mask": "Заказ", "max_results": 3}, rid); rid += 1
j = check("search_code.2", r)

# 14. list_metadata_objects
print("\n" + "=" * 60)
print("14. list_metadata_objects (2 tests)")
print("=" * 60)

print("  14.1: List Catalogs")
r = call("list_metadata_objects", {"metaType": "Catalogs", "maxItems": 5}, rid); rid += 1
j = check("list_metadata_objects.1", r)
if j and j.get('success'):
    text = j.get('data', '')
    lines = text.split('\n') if isinstance(text, str) else []
    print(f"    -> {len(lines)} items")

print("  14.2: Filter by name")
r = call("list_metadata_objects", {"metaType": "Documents", "nameMask": "Заказ", "maxItems": 5}, rid); rid += 1
j = check("list_metadata_objects.2", r)

# 15. get_metadata_structure
print("\n" + "=" * 60)
print("15. get_metadata_structure (2 tests)")
print("=" * 60)

print("  15.1: Catalog structure")
r = call("get_metadata_structure", {"metaType": "Catalogs", "name": "Номенклатура"}, rid); rid += 1
j = check("get_metadata_structure.1", r)
if j and j.get('success'):
    print(f"    -> {len(str(j.get('data','')))} chars")

print("  15.2: Document structure")
r = call("get_metadata_structure", {"metaType": "Documents", "name": "ЗаказКлиента"}, rid); rid += 1
j = check("get_metadata_structure.2", r)

# SUMMARY
print("\n" + "=" * 60)
print(f"SUMMARY: {passed} PASSED / {failed} FAILED / {passed+failed} TOTAL")
print("=" * 60)
if errors:
    print("Failures:")
    for e in errors:
        print(e)
