# -*- coding: utf-8 -*-
"""Генератор RLS-ролей залоговых цен: извлекает корневой <object> (с restrictionByCondition)
и <restrictionTemplate> блоки из эталонных ролей байт-в-байт, заменяет только имя объекта.
Временный одноразовый скрипт (GKSTCPLK-2521)."""
import re
import sys

ROLES = "C:\\1С-Framework\\ИБTransportManagementDevelop\\Конфигурация\\src\\Roles\\"

HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Rights xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns="http://v8.1c.ru/8.2/roles" xsi:type="Rights">\n'
    '\t<setForNewObjects>false</setForNewObjects>\n'
    '\t<setForAttributesByDefault>true</setForAttributesByDefault>\n'
    '\t<independentRightsOfChildObjects>false</independentRightsOfChildObjects>\n'
)

REG_OLD = "гкс_СостоянияРегистрации"
REG_NEW = "гкс_ЗалоговыеЦены"
DOC_OLD = "гкс_УстановкаНастроекНазначенияРазгрузки"
DOC_NEW = "гкс_УстановкаЗалоговыхЦен"

RS = "РегистрСведений_"
DOK = "Документ_"
PROS = "Просмотр"
DOBIZM = "ДобавлениеИзменение"

JOBS = [
    ("гкс_" + RS + REG_OLD + "_" + PROS, "гкс_" + RS + REG_NEW + "_" + PROS,
     "InformationRegister." + REG_OLD, REG_OLD, REG_NEW),
    ("гкс_" + RS + REG_OLD + "_" + DOBIZM, "гкс_" + RS + REG_NEW + "_" + DOBIZM,
     "InformationRegister." + REG_OLD, REG_OLD, REG_NEW),
    ("гкс_" + DOK + DOC_OLD + "_" + PROS, "гкс_" + DOK + DOC_NEW + "_" + PROS,
     "Document." + DOC_OLD, DOC_OLD, DOC_NEW),
    ("гкс_" + DOK + DOC_OLD + "_" + DOBIZM, "гкс_" + DOK + DOC_NEW + "_" + DOBIZM,
     "Document." + DOC_OLD, DOC_OLD, DOC_NEW),
]

rc = 0
for src, tgt, fqn, old, new in JOBS:
    srcfile = ROLES + src + "\\Rights.rights"
    with open(srcfile, encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"\t<object>\s*<name>" + re.escape(fqn) + r"</name>.*?</object>", content, re.S)
    if not m:
        print("NO OBJECT:", src)
        rc = 1
        continue
    obj = m.group(0).replace(old, new)
    tpls = re.findall(r"\t<restrictionTemplate>.*?</restrictionTemplate>", content, re.S)
    if not tpls:
        print("NO TEMPLATES:", src)
        rc = 1
        continue
    out = HEADER + obj + "\n" + "\n".join(tpls) + "\n</Rights>\n"
    tgtfile = ROLES + tgt + "\\Rights.rights"
    with open(tgtfile, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("OK:", tgt, "| obj_chars", len(obj), "| templates", len(tpls),
          "| conds", obj.count("<restrictionByCondition>"),
          "| tpl_names", re.findall(r"<restrictionTemplate>\s*<name>([^<(]+)", "\n".join(tpls)))
sys.exit(rc)
