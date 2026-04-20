"""Generate ПФ_MXL_ЯрлыкПробы/Ext/Template.xml for GKSTCPLK-2400."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

lines = []
lines.append('<?xml version="1.0" encoding="UTF-8"?>')
lines.append('<document xmlns="http://v8.1c.ru/8.2/data/spreadsheet" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">')

lines.append("\t<languageSettings>")
lines.append("\t\t<currentLanguage>ru</currentLanguage>")
lines.append("\t\t<defaultLanguage>ru</defaultLanguage>")
lines.append("\t\t<languageInfo>")
lines.append("\t\t\t<id>ru</id>")
lines.append("\t\t\t<code>Русский</code>")
lines.append("\t\t\t<description>Русский</description>")
lines.append("\t\t</languageInfo>")
lines.append("\t</languageSettings>")

lines.append("\t<columns>")
lines.append("\t\t<size>2</size>")
lines.append("\t\t<columnsItem>")
lines.append("\t\t\t<index>0</index>")
lines.append("\t\t\t<column><formatIndex>1</formatIndex></column>")
lines.append("\t\t</columnsItem>")
lines.append("\t\t<columnsItem>")
lines.append("\t\t\t<index>1</index>")
lines.append("\t\t\t<column><formatIndex>2</formatIndex></column>")
lines.append("\t\t</columnsItem>")
lines.append("\t</columns>")


def row_param(idx, param_name, format_idx):
    out = ["\t<rowsItem>"]
    out.append(f"\t\t<index>{idx}</index>")
    out.append("\t\t<row>")
    out.append("\t\t\t<c>")
    out.append("\t\t\t\t<c>")
    out.append(f"\t\t\t\t\t<f>{format_idx}</f>")
    out.append(f"\t\t\t\t\t<parameter>{param_name}</parameter>")
    out.append("\t\t\t\t</c>")
    out.append("\t\t\t</c>")
    out.append("\t\t</row>")
    out.append("\t</rowsItem>")
    return out


def row_empty(idx, row_format_idx):
    out = ["\t<rowsItem>"]
    out.append(f"\t\t<index>{idx}</index>")
    out.append("\t\t<row>")
    out.append(f"\t\t\t<formatIndex>{row_format_idx}</formatIndex>")
    out.append("\t\t\t<c><c><f>0</f></c></c>")
    out.append("\t\t</row>")
    out.append("\t</rowsItem>")
    return out


# Area Шапка: rows 0-1
lines.extend(row_param(0, "Организация", 3))
lines.extend(row_param(1, "ДатаОтбора", 4))
# Area Основное: rows 2-6
lines.extend(row_param(2, "НакладнаяНомер", 5))
lines.extend(row_param(3, "ОбразецНомер", 6))
lines.extend(row_param(4, "Сырье", 5))
lines.extend(row_param(5, "Поставщик", 7))
lines.extend(row_param(6, "НомерТС", 5))
# Area Подвал: rows 7-10
lines.extend(row_param(7, "Комментарий", 5))
lines.extend(row_param(8, "МассаПартии", 4))
lines.extend(row_empty(9, 8))
lines.extend(row_param(10, "ПодписьЛаборанта", 5))

lines.append("\t<templateMode>true</templateMode>")
lines.append("\t<defaultFormatIndex>9</defaultFormatIndex>")
lines.append("\t<height>6</height>")
lines.append("\t<vgRows>6</vgRows>")

for r in range(11):
    lines.append("\t<merge>")
    lines.append(f"\t\t<r>{r}</r>")
    lines.append("\t\t<c>0</c>")
    lines.append("\t\t<w>1</w>")
    lines.append("\t</merge>")

areas = [
    ("Шапка", 0, 1),
    ("Основное", 2, 6),
    ("Подвал", 7, 10),
]
for name, br, er in areas:
    lines.append('\t<namedItem xsi:type="NamedItemCells">')
    lines.append(f"\t\t<name>{name}</name>")
    lines.append("\t\t<area>")
    lines.append("\t\t\t<type>Rows</type>")
    lines.append(f"\t\t\t<beginRow>{br}</beginRow>")
    lines.append(f"\t\t\t<endRow>{er}</endRow>")
    lines.append("\t\t\t<beginColumn>-1</beginColumn>")
    lines.append("\t\t\t<endColumn>-1</endColumn>")
    lines.append("\t\t</area>")
    lines.append("\t</namedItem>")

lines.append('\t<line width="1" gap="false">')
lines.append('\t\t<v8ui:style xsi:type="v8ui:SpreadsheetDocumentDrawingLineType">None</v8ui:style>')
lines.append("\t</line>")

# Fonts
lines.append('\t<font faceName="Arial" height="9" bold="true" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')
lines.append('\t<font faceName="Arial" height="14" bold="true" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')
lines.append('\t<font faceName="Arial" height="9" bold="false" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')
lines.append('\t<font faceName="Arial" height="12" bold="true" italic="false" underline="false" strikeout="false" kind="Absolute" scale="100"/>')

# Formats
lines.append("\t<format/>")
lines.append("\t<format><width>168</width></format>")
lines.append("\t<format><width>125</width></format>")
lines.append("\t<format><font>1</font><horizontalAlignment>Center</horizontalAlignment><fillType>Parameter</fillType></format>")
lines.append("\t<format><font>2</font><horizontalAlignment>Right</horizontalAlignment><fillType>Parameter</fillType></format>")
lines.append("\t<format><font>2</font><fillType>Parameter</fillType></format>")
lines.append("\t<format><font>3</font><horizontalAlignment>Center</horizontalAlignment><fillType>Parameter</fillType></format>")
lines.append("\t<format><font>2</font><fillType>Parameter</fillType></format>")
lines.append("\t<format><height>6</height></format>")
lines.append('\t<format><verticalAlignment>Top</verticalAlignment><backColor>style:FieldBackColor</backColor></format>')

lines.append("</document>")
lines.append("")

content = "\n".join(lines)

path = (
    "D:/1С-Framework/src/projects/configuration/"
    "260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/"
    "src/DataProcessors/гкс_ПечатьДокументаЛабораторныйАнализ/Templates/"
    "ПФ_MXL_ЯрлыкПробы/Ext/Template.xml"
)
with open(path, "wb") as f:
    f.write(b"\xef\xbb\xbf")
    f.write(content.encode("utf-8"))

print(f"Template.xml created: {len(lines)} lines")
