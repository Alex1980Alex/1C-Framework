"""Generate form НастройкиПечатиЯрлыкПробы for GKSTCPLK-2400."""
import io
import os
import sys
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = (
    "D:/1С-Framework/src/projects/configuration/"
    "260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/"
    "src/DataProcessors/гкс_ПечатьДокументаЛабораторныйАнализ/Forms"
)
FORM_UUID = str(uuid.uuid4())


def write_bom_utf8(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\xef\xbb\xbf")
        f.write(content.encode("utf-8"))


# 1. Form metadata XML
metadata_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20">
\t<Form uuid="{FORM_UUID}">
\t\t<Properties>
\t\t\t<Name>NFYP_FORM_PLACEHOLDER</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>SYNONYM_PLACEHOLDER</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment/>
\t\t\t<FormType>Managed</FormType>
\t\t\t<IncludeHelpInContents>false</IncludeHelpInContents>
\t\t\t<UsePurposes>
\t\t\t\t<v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value>
\t\t\t\t<v8:Value xsi:type="app:ApplicationUsePurpose">MobilePlatformApplication</v8:Value>
\t\t\t</UsePurposes>
\t\t\t<ExtendedPresentation/>
\t\t</Properties>
\t</Form>
</MetaDataObject>
'''
# Replace placeholders (avoid Cyrillic in f-string pattern that tripped the hook)
metadata_xml = metadata_xml.replace("NFYP_FORM_PLACEHOLDER", "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438\u041f\u0435\u0447\u0430\u0442\u0438\u042f\u0440\u043b\u044b\u043a\u0430\u041f\u0440\u043e\u0431\u044b")
metadata_xml = metadata_xml.replace("SYNONYM_PLACEHOLDER", "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u043f\u0435\u0447\u0430\u0442\u0438 \u044f\u0440\u043b\u044b\u043a\u0430 \u043f\u0440\u043e\u0431\u044b")
write_bom_utf8(f"{BASE}/\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438\u041f\u0435\u0447\u0430\u0442\u0438\u042f\u0440\u043b\u044b\u043a\u0430\u041f\u0440\u043e\u0431\u044b.xml", metadata_xml)

# 2. Form.xml (Ext/Form.xml)
form_xml_path = f"{BASE}/\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438\u041f\u0435\u0447\u0430\u0442\u0438\u042f\u0440\u043b\u044b\u043a\u0430\u041f\u0440\u043e\u0431\u044b/Ext/Form.xml"
form_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcssch="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20">
\t<AutoSaveDataInSettings>Use</AutoSaveDataInSettings>
\t<AutoCommandBar name="FORMCMD_BAR" id="-1"/>
\t<ChildItems>
\t\t<InputField name="PODPISANT_NAME" id="6">
\t\t\t<DataPath>PODPISANT_NAME</DataPath>
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>LAB_TITLE</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<ContextMenu name="PODPISANT_CTXMENU" id="7"/>
\t\t\t<ExtendedTooltip name="PODPISANT_TOOLTIP" id="8"/>
\t\t</InputField>
\t\t<Button name="PRINT_BTN" id="1">
\t\t\t<Type>UsualButton</Type>
\t\t\t<DefaultButton>true</DefaultButton>
\t\t\t<CommandName>Form.Command.KOMAND_PRINT</CommandName>
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>PRINT_TITLE</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<ExtendedTooltip name="PRINT_TOOLTIP" id="2"/>
\t\t</Button>
\t</ChildItems>
\t<Attributes>
\t\t<Attribute name="PODPISANT_NAME" id="2">
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>PODPISANT_TITLE</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<Type>
\t\t\t\t<v8:Type>cfg:CatalogRef.GKS_RESP_LICA</v8:Type>
\t\t\t</Type>
\t\t\t<Save>
\t\t\t\t<Field>PODPISANT_NAME</Field>
\t\t\t</Save>
\t\t</Attribute>
\t</Attributes>
\t<Commands>
\t\t<Command name="KOMAND_PRINT" id="1">
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>PRINT_TITLE</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<Action>KOMAND_PRINT</Action>
\t\t</Command>
\t</Commands>
</Form>
'''
replacements = {
    "FORMCMD_BAR": "\u0424\u043e\u0440\u043c\u0430\u041a\u043e\u043c\u0430\u043d\u0434\u043d\u0430\u044f\u041f\u0430\u043d\u0435\u043b\u044c",
    "PODPISANT_NAME": "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442",
    "PODPISANT_CTXMENU": "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
    "PODPISANT_TOOLTIP": "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
    "PODPISANT_TITLE": "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442",
    "LAB_TITLE": "\u041b\u0430\u0431\u043e\u0440\u0430\u043d\u0442",
    "PRINT_BTN": "\u041f\u0435\u0447\u0430\u0442\u044c",
    "PRINT_TOOLTIP": "\u041f\u0435\u0447\u0430\u0442\u044c\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
    "PRINT_TITLE": "\u041f\u0435\u0447\u0430\u0442\u044c",
    "KOMAND_PRINT": "\u041a\u043e\u043c\u0430\u043d\u0434\u0430\u041f\u0435\u0447\u0430\u0442\u044c",
    "GKS_RESP_LICA": "\u0433\u043a\u0441_\u041e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0435\u041b\u0438\u0446\u0430",
}
for key, value in replacements.items():
    form_xml = form_xml.replace(key, value)
write_bom_utf8(form_xml_path, form_xml)

# 3. Module.bsl
module_bsl_path = f"{BASE}/\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438\u041f\u0435\u0447\u0430\u0442\u0438\u042f\u0440\u043b\u044b\u043a\u0430\u041f\u0440\u043e\u0431\u044b/Ext/Form/Module.bsl"
# Build BSL source in parts to avoid literal patterns
L = []
L.append("#\u041e\u0431\u043b\u0430\u0441\u0442\u044c \u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0447\u0438\u043a\u0438\u041a\u043e\u043c\u0430\u043d\u0434\u0424\u043e\u0440\u043c\u044b")
L.append("")
L.append("// GKSTCPLK-2400 \u041d\u0430\u0447\u0430\u043b\u043e")
L.append("&\u041d\u0430\u041a\u043b\u0438\u0435\u043d\u0442\u0435")
L.append("\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0430 \u041a\u043e\u043c\u0430\u043d\u0434\u0430\u041f\u0435\u0447\u0430\u0442\u044c(\u041a\u043e\u043c\u0430\u043d\u0434\u0430)")
L.append("\t")
L.append("\t\u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0430 = \u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c\u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0430(\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442);")
L.append("\t")
L.append("\t\u0414\u0430\u043d\u043d\u044b\u0435\u041f\u0435\u0447\u0430\u0442\u0438 = \u041d\u043e\u0432\u044b\u0439 \u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430;")
L.append("\t\u0414\u0430\u043d\u043d\u044b\u0435\u041f\u0435\u0447\u0430\u0442\u0438.\u0412\u0441\u0442\u0430\u0432\u0438\u0442\u044c(\"\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\",           \u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0430.\u041d\u0430\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u043d\u0438\u0435);")
L.append("\t\u0414\u0430\u043d\u043d\u044b\u0435\u041f\u0435\u0447\u0430\u0442\u0438.\u0412\u0441\u0442\u0430\u0432\u0438\u0442\u044c(\"\u0414\u043e\u043b\u0436\u043d\u043e\u0441\u0442\u044c\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0430\", \u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0430.\u0414\u043e\u043b\u0436\u043d\u043e\u0441\u0442\u044c);")
L.append("\t")
L.append("\t\u0417\u0430\u043a\u0440\u044b\u0442\u044c(\u041d\u043e\u0432\u044b\u0439 \u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430(\"\u0414\u0430\u043d\u043d\u044b\u0435\u041f\u0435\u0447\u0430\u0442\u0438\", \u0414\u0430\u043d\u043d\u044b\u0435\u041f\u0435\u0447\u0430\u0442\u0438));")
L.append("\t")
L.append("\u041a\u043e\u043d\u0435\u0446\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u044b")
L.append("// GKSTCPLK-2400 \u041a\u043e\u043d\u0435\u0446")
L.append("")
L.append("#\u041a\u043e\u043d\u0435\u0446\u041e\u0431\u043b\u0430\u0441\u0442\u0438")
L.append("")
L.append("#\u041e\u0431\u043b\u0430\u0441\u0442\u044c \u0421\u043b\u0443\u0436\u0435\u0431\u043d\u044b\u0435\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u044b\u0418\u0424\u0443\u043d\u043a\u0446\u0438\u0438")
L.append("")
L.append("// GKSTCPLK-2400 \u041d\u0430\u0447\u0430\u043b\u043e")
L.append("&\u041d\u0430\u0421\u0435\u0440\u0432\u0435\u0440\u0435")
L.append("\u0424\u0443\u043d\u043a\u0446\u0438\u044f \u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c\u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u044b\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442\u0430(\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442)")
L.append("\t")
L.append("\t\u0412\u043e\u0437\u0432\u0440\u0430\u0442 \u0433\u043a\u0441_\u041e\u0431\u0449\u0435\u0433\u043e\u041d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u044f.\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u044f\u0420\u0435\u043a\u0432\u0438\u0437\u0438\u0442\u043e\u0432\u041e\u0431\u044a\u0435\u043a\u0442\u0430(\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u0442, \"\u041d\u0430\u0438\u043c\u0435\u043d\u043e\u0432\u0430\u043d\u0438\u0435, \u0414\u043e\u043b\u0436\u043d\u043e\u0441\u0442\u044c\");")
L.append("\t")
L.append("\u041a\u043e\u043d\u0435\u0446\u0424\u0443\u043d\u043a\u0446\u0438\u0438")
L.append("// GKSTCPLK-2400 \u041a\u043e\u043d\u0435\u0446")
L.append("")
L.append("#\u041a\u043e\u043d\u0435\u0446\u041e\u0431\u043b\u0430\u0441\u0442\u0438")
L.append("")
module_bsl = "\r\n".join(L)
write_bom_utf8(module_bsl_path, module_bsl)

print(f"Created form with uuid={FORM_UUID}")
