import sys,xml.dom.minidom as M
try:
    M.parse(sys.argv[1])
    print("EXPAT OK (well-formed)")
except Exception as e:
    print("EXPAT ERROR:", e)