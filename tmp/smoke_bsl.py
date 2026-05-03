import asyncio, os, sys, time, traceback
sys.stdout.reconfigure(encoding="utf-8")
from src.bsl.semantic_search import mcp as m
fn = m.bsl_search
under = getattr(fn, "fn", None) or getattr(fn, "func", None) or fn
print(f"type={type(fn).__name__} under={type(under).__name__}", flush=True)
q = os.environ.get("Q", "document posting")
async def main():
    t = time.time()
    r = under(query=q, limit=3, mode="semantic")
    if asyncio.iscoroutine(r): r = await asyncio.wait_for(r, timeout=45)
    print(f"OK {time.time()-t:.2f}s len={len(str(r))}\n{str(r)[:1200]}", flush=True)
try: asyncio.run(main())
except Exception: traceback.print_exc(); sys.exit(2)
