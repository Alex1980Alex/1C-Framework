"""Fix format index off-by-one in ПФ_MXL_ЯрлыкПробы Template.mxlx.

Problem: my template has <format/> as first format (index 0), but 1C uses
1-based format indexing. So rows with <f>3</f> reference format 3 =
<width>125</width> (column width, NOT Parameter fillType).

Fix: remove empty <format/> placeholder. All remaining formats naturally
shift to correct 1-based positions:
  1: <width>168</width>
  2: <width>125</width>
  3: Title (Parameter)  <- <f>3</f> will correctly point here
  4: Right-align (Parameter)
  ...
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def fix(path, has_bom):
    with open(path, "rb") as f:
        raw = f.read()
    bom = b""
    if raw.startswith(b"\xef\xbb\xbf"):
        bom = b"\xef\xbb\xbf"
        raw = raw[3:]
    text = raw.decode("utf-8")
    # Remove the standalone empty <format/> placeholder (first occurrence,
    # which is at index 0 in our generator output)
    marker = "\t<format/>\n"
    if marker in text:
        new_text = text.replace(marker, "", 1)
        print(f"Removed placeholder in {path}")
    else:
        # Try alternate with CRLF
        marker_crlf = "\t<format/>\r\n"
        if marker_crlf in text:
            new_text = text.replace(marker_crlf, "", 1)
            print(f"Removed placeholder (CRLF) in {path}")
        else:
            print(f"  WARN: placeholder not found in {path}")
            return
    with open(path, "wb") as f:
        if has_bom:
            f.write(bom)
        f.write(new_text.encode("utf-8"))


# Submodule Template.xml (Designer format)
SUB = (
    "D:/1С-Framework/src/projects/configuration/"
    "260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС/"
    "src/DataProcessors/\u0433\u043a\u0441_\u041f\u0435\u0447\u0430\u0442\u044c\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430"
    "\u041b\u0430\u0431\u043e\u0440\u0430\u0442\u043e\u0440\u043d\u044b\u0439\u0410\u043d\u0430\u043b\u0438\u0437/"
    "Templates/\u041f\u0424_MXL_\u042f\u0440\u043b\u044b\u043a\u041f\u0440\u043e\u0431\u044b/Ext/Template.xml"
)
fix(SUB, has_bom=True)

# EDT Template.mxlx
EDT = (
    "D:/WorkSpace/\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435"
    "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043e\u043c\u041d\u0430\u041f\u041b\u041a/"
    "\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435"
    "\u0422\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043e\u043c\u041d\u0430\u041f\u041b\u041a/"
    "src/DataProcessors/\u0433\u043a\u0441_\u041f\u0435\u0447\u0430\u0442\u044c\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430"
    "\u041b\u0430\u0431\u043e\u0440\u0430\u0442\u043e\u0440\u043d\u044b\u0439\u0410\u043d\u0430\u043b\u0438\u0437/"
    "Templates/\u041f\u0424_MXL_\u042f\u0440\u043b\u044b\u043a\u041f\u0440\u043e\u0431\u044b/Template.mxlx"
)
fix(EDT, has_bom=False)

print("Done.")
