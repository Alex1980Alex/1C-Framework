"""Regenerate ПФ_MXL_ЯрлыкПробы Template with 2-column layout.

Left column: static text labels (e.g., "Дата отбора")
Right column: parameter placeholders (e.g., ДатаОтбора)
Row 0: Организация parameter (left) + "Ярлык пробы" static title (right)
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def cell_text(col_idx, fmt_idx, text):
    """Build <c> cell with static text <tl>."""
    lines = ["\t\t\t<c>"]
    if col_idx is not None:
        lines.append(f"\t\t\t\t<i>{col_idx}</i>")
    lines.append("\t\t\t\t<c>")
    lines.append(f"\t\t\t\t\t<f>{fmt_idx}</f>")
    lines.append("\t\t\t\t\t<tl>")
    lines.append("\t\t\t\t\t\t<v8:item>")
    lines.append("\t\t\t\t\t\t\t<v8:lang>ru</v8:lang>")
    lines.append(f"\t\t\t\t\t\t\t<v8:content>{text}</v8:content>")
    lines.append("\t\t\t\t\t\t</v8:item>")
    lines.append("\t\t\t\t\t</tl>")
    lines.append("\t\t\t\t</c>")
    lines.append("\t\t\t</c>")
    return lines


def cell_param(col_idx, fmt_idx, param_name):
    """Build <c> cell with <parameter> placeholder."""
    lines = ["\t\t\t<c>"]
    if col_idx is not None:
        lines.append(f"\t\t\t\t<i>{col_idx}</i>")
    lines.append("\t\t\t\t<c>")
    lines.append(f"\t\t\t\t\t<f>{fmt_idx}</f>")
    lines.append(f"\t\t\t\t\t<parameter>{param_name}</parameter>")
    lines.append("\t\t\t\t</c>")
    lines.append("\t\t\t</c>")
    return lines


def row(idx, cells):
    """Wrap cells in <rowsItem>."""
    out = ["\t<rowsItem>"]
    out.append(f"\t\t<index>{idx}</index>")
    out.append("\t\t<row>")
    for cell_lines in cells:
        out.extend(cell_lines)
    out.append("\t\t</row>")
    out.append("\t</rowsItem>")
    return out


out = []
out.append('<?xml version="1.0" encoding="UTF-8"?>')
out.append('<document xmlns="http://v8.1c.ru/8.2/data/spreadsheet" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">')

out.append("\t<languageSettings>")
out.append("\t\t<currentLanguage>ru</currentLanguage>")
out.append("\t\t<defaultLanguage>ru</defaultLanguage>")
out.append("\t\t<languageInfo>")
out.append("\t\t\t<id>ru</id>")
out.append("\t\t\t<code>Русский</code>")
out.append("\t\t\t<description>Русский</description>")
out.append("\t\t</languageInfo>")
out.append("\t</languageSettings>")

# Columns: 2 (narrow labels | wide values)
out.append("\t<columns>")
out.append("\t\t<size>2</size>")
out.append("\t\t<columnsItem>")
out.append("\t\t\t<index>0</index>")
out.append("\t\t\t<column><formatIndex>1</formatIndex></column>")
out.append("\t\t</columnsItem>")
out.append("\t\t<columnsItem>")
out.append("\t\t\t<index>1</index>")
out.append("\t\t\t<column><formatIndex>2</formatIndex></column>")
out.append("\t\t</columnsItem>")
out.append("\t</columns>")

# Format indices (1-based):
#   1: column 0 width (labels — narrower)
#   2: column 1 width (values — wider)
#   3: Label style — bold, left
#   4: Value style — plain, left
#   5: Title style — font 14 bold, center (only row 0 right cell)
#   6: Default

# Rows:
# Row 0: Организация (param, col 0, bold Parameter) | "Ярлык пробы" (text, col 1, title style)
# Fmt 7 = Organization value (bold Parameter left)
out.extend(row(0, [cell_param(None, 7, "Организация"), cell_text(None, 5, "Ярлык пробы")]))
# Row 1: "Дата отбора" | ДатаОтбора
out.extend(row(1, [cell_text(None, 3, "Дата отбора"), cell_param(None, 4, "ДатаОтбора")]))
# Row 2: "Накладная №" | НакладнаяНомер
out.extend(row(2, [cell_text(None, 3, "Накладная №"), cell_param(None, 4, "НакладнаяНомер")]))
# Row 3: "Образец номер" | ОбразецНомер
out.extend(row(3, [cell_text(None, 3, "Образец номер"), cell_param(None, 4, "ОбразецНомер")]))
# Row 4: "Сырье" | Сырье
out.extend(row(4, [cell_text(None, 3, "Сырье"), cell_param(None, 4, "Сырье")]))
# Row 5: "Поставщик" | Поставщик
out.extend(row(5, [cell_text(None, 3, "Поставщик"), cell_param(None, 4, "Поставщик")]))
# Row 6: "№ тр средства (склада, силоса)" | НомерТС
out.extend(row(6, [cell_text(None, 3, "№ тр средства (склада, силоса)"), cell_param(None, 4, "НомерТС")]))
# Row 7: "Комментарий" | Комментарий
out.extend(row(7, [cell_text(None, 3, "Комментарий"), cell_param(None, 4, "Комментарий")]))
# Row 8: "Масса партии (груза)" | МассаПартии
out.extend(row(8, [cell_text(None, 3, "Масса партии (груза)"), cell_param(None, 4, "МассаПартии")]))
# Row 9: "Подпись лица, отобравшего пробу" | ПодписьЛаборанта
out.extend(row(9, [cell_text(None, 3, "Подпись лица, отобравшего пробу"), cell_param(None, 4, "ПодписьЛаборанта")]))

out.append("\t<templateMode>true</templateMode>")
out.append("\t<defaultFormatIndex>6</defaultFormatIndex>")
out.append("\t<height>10</height>")
out.append("\t<vgRows>10</vgRows>")

# Named areas (all cover both columns — <beginColumn>-1</beginColumn> = all columns)
areas = [
    ("Шапка", 0, 0),
    ("Основное", 1, 6),
    ("Подвал", 7, 9),
]
for name, br, er in areas:
    out.append('\t<namedItem xsi:type="NamedItemCells">')
    out.append(f"\t\t<name>{name}</name>")
    out.append("\t\t<area>")
    out.append("\t\t\t<type>Rows</type>")
    out.append(f"\t\t\t<beginRow>{br}</beginRow>")
    out.append(f"\t\t\t<endRow>{er}</endRow>")
    out.append("\t\t\t<beginColumn>-1</beginColumn>")
    out.append("\t\t\t<endColumn>-1</endColumn>")
    out.append("\t\t</area>")
    out.append("\t</namedItem>")

out.append('\t<line width="1" gap="false">')
out.append('\t\t<v8ui:style xsi:type="v8ui:SpreadsheetDocumentDrawingLineType">None</v8ui:style>')
out.append("\t</line>")

# Fonts (all 1-based): 0=Arial 9 bold, 1=Arial 10 bold, 2=Arial 10, 3=Arial 14 bold
out.append('\t<font faceName="Arial" height="9" bold="true" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')
out.append('\t<font faceName="Arial" height="10" bold="true" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')
out.append('\t<font faceName="Arial" height="10" bold="false" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')
out.append('\t<font faceName="Arial" height="14" bold="true" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')

# Formats (1-based per 1C convention — no placeholder):
# 1: column 0 width (labels, narrower)
out.append("\t<format><width>80</width></format>")
# 2: column 1 width (values, wider)
out.append("\t<format><width>120</width></format>")
# 3: Label style — bold Arial 10, left align, text fill
out.append("\t<format><font>1</font><horizontalAlignment>Left</horizontalAlignment><verticalAlignment>Top</verticalAlignment><fillType>Text</fillType></format>")
# 4: Value style — plain Arial 10, left align, Parameter fill
out.append("\t<format><font>2</font><horizontalAlignment>Left</horizontalAlignment><verticalAlignment>Top</verticalAlignment><fillType>Parameter</fillType></format>")
# 5: Title style — Arial 14 bold, center, text fill (only "Ярлык пробы")
out.append("\t<format><font>3</font><horizontalAlignment>Center</horizontalAlignment><verticalAlignment>Center</verticalAlignment><fillType>Text</fillType></format>")
# 6: Default
out.append("\t<format><verticalAlignment>Top</verticalAlignment><backColor>style:FieldBackColor</backColor></format>")

out.append("</document>")
out.append("")

content = "\n".join(out)

# Write to both submodule and EDT
submodule = (
    "D:/1С-Framework/src/projects/configuration/"
    "260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/"
    "src/DataProcessors/\u0433\u043a\u0441_\u041f\u0435\u0447\u0430\u0442\u044c\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430"
    "\u041b\u0430\u0431\u043e\u0440\u0430\u0442\u043e\u0440\u043d\u044b\u0439\u0410\u043d\u0430\u043b\u0438\u0437/"
    "Templates/\u041f\u0424_MXL_\u042f\u0440\u043b\u044b\u043a\u041f\u0440\u043e\u0431\u044b/Ext/Template.xml"
)
with open(submodule, "wb") as f:
    f.write(b"\xef\xbb\xbf")
    f.write(content.encode("utf-8"))

edt = (
    "D:/WorkSpace/\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043e\u043c\u041d\u0430\u041f\u041b\u041a/"
    "\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043e\u043c\u041d\u0430\u041f\u041b\u041a/"
    "src/DataProcessors/\u0433\u043a\u0441_\u041f\u0435\u0447\u0430\u0442\u044c\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430"
    "\u041b\u0430\u0431\u043e\u0440\u0430\u0442\u043e\u0440\u043d\u044b\u0439\u0410\u043d\u0430\u043b\u0438\u0437/"
    "Templates/\u041f\u0424_MXL_\u042f\u0440\u043b\u044b\u043a\u041f\u0440\u043e\u0431\u044b/Template.mxlx"
)
with open(edt, "wb") as f:
    f.write(content.encode("utf-8"))

print(f"Regenerated: {len(content.splitlines())} lines")
print(f"  submodule: {submodule[-60:]}")
print(f"  edt: {edt[-60:]}")
