import sys, re
path = sys.argv[1]
delete = sorted(set(int(x) for x in sys.argv[2].split(",")))
with open(path, "rb") as f:
    s = f.read().decode("utf-8")
def shift0(r):
    return r - sum(1 for d in delete if d < r)
def repl_row(m):
    idx = int(m.group(1))
    if idx in delete:
        return ""
    block = m.group(0)
    ni = shift0(idx)
    if ni != idx:
        block = re.sub(r"<index>\d+</index>", "<index>%d</index>" % ni, block, count=1)
    return block
s = re.sub(r"\s*<rowsItem>\s*<index>(\d+)</index>.*?</rowsItem>", repl_row, s, flags=re.S)
def repl_merge(m):
    r = int(m.group(1))
    if r in delete:
        return ""
    block = m.group(0)
    nr = shift0(r)
    if nr != r:
        block = re.sub(r"<r>\d+</r>", "<r>%d</r>" % nr, block, count=1)
    return block
s = re.sub(r"\s*<merge>\s*<r>(\d+)</r>.*?</merge>", repl_merge, s, flags=re.S)
def shift1(R):
    return R - sum(1 for d in delete if d < R-1)
s = re.sub(r"<beginRow>(\d+)</beginRow>", lambda m: "<beginRow>%d</beginRow>" % shift1(int(m.group(1))), s)
s = re.sub(r"<endRow>(\d+)</endRow>", lambda m: "<endRow>%d</endRow>" % shift1(int(m.group(1))), s)
with open(path, "wb") as f:
    f.write(s.encode("utf-8"))
print("OK reindexed; deleted " + str(delete))
