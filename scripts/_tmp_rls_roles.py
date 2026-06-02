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

# bare = имя в названии роли (без гкс_); meta = полное имя метаданного (FQN/условие)
REG_OLD_BARE, REG_NEW_BARE = "СостоянияРегистрации", "ЗалоговыеЦены"
REG_OLD_META, REG_NEW_META = "гкс_СостоянияРегистрации", "гкс_ЗалоговыеЦены"
DOC_OLD_BARE, DOC_NEW_BARE = "УстановкаНастроекНазначенияРазгрузки", "УстановкаЗалоговыхЦен"
DOC_OLD_META, DOC_NEW_META = "гкс_УстановкаНастроекНазначенияРазгрузки", "гкс_УстановкаЗалоговыхЦен"

RS = "гкс_РегистрСведений_"
DOK = "гкс_Документ_"
PROS = "_Просмотр"
DOBIZM = "_ДобавлениеИзменение"

JOBS = [
    (RS + REG_OLD_BARE + PROS, RS + REG_NEW_BARE + PROS,
     "InformationRegister." + REG_OLD_META, REG_OLD_META, REG_NEW_META),
    (RS + REG_OLD_BARE + DOBIZM, RS + REG_NEW_BARE + DOBIZM,
     "InformationRegister." + REG_OLD_META, REG_OLD_META, REG_NEW_META),
    (DOK + DOC_OLD_BARE + PROS, DOK + DOC_NEW_BARE + PROS,
     "Document." + DOC_OLD_META, DOC_OLD_META, DOC_NEW_META),
    (DOK + DOC_OLD_BARE + DOBIZM, DOK + DOC_NEW_BARE + DOBIZM,
     "Document." + DOC_OLD_META, DOC_OLD_META, DOC_NEW_META),
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
