"""Extended A/B testing — A1 chunker / C1 whitening / BM25-sparse hypotheses."""
import sys, re, statistics, time
import numpy as np
import httpx
from qdrant_client import QdrantClient
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

QI = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "

QUERIES = [
    "обработка проведения документа", "контроль остатков при проведении",
    "формирование запроса к базе данных", "отправка email уведомления",
    "регистрация изменений для обмена", "проверка прав доступа пользователя",
    "формирование табличного документа отчёта", "загрузка данных из Excel файла",
    "обработчик перед записью документа", "удаление помеченных объектов",
    "поиск элемента справочника по коду", "обработка проверки заполнения реквизита",
    "получение настроек хранилища значений", "движение по регистрам накопления",
    "получение представления ссылки объекта", "формирование структуры параметров команды",
    "обработчик события создания на сервере формы", "загрузка XML файла с данными обмена",
    "проведение по бухгалтерскому учёту", "проверка существования объекта метаданных",
]

c = QdrantClient(url="http://localhost:6333", timeout=60)
http = httpx.Client(timeout=120)
COLL = "bsl_code_v4_late"

def embed_q(q, with_instr=True):
    text = (QI + q) if with_instr else q
    r = http.post("http://localhost:8080/embed", json={"inputs": [text], "normalize": True, "truncate": True})
    d = r.json()
    if isinstance(d, dict) and "embeddings" in d: d = d["embeddings"]
    return np.array(d[0], dtype=np.float32)

def short(s):
    if not s: return "?"
    return "/".join(s.replace("/", "\\").split("\\")[-2:])

t_start = time.time()

print("="*100)
print("SETUP: scrolling 2000 points from bsl_code_v4_late")
print("="*100)
t0 = time.time()
scroll = c.scroll(collection_name=COLL, limit=2000, with_vectors=True, with_payload=True)
points = scroll[0]
print(f"Scrolled {len(points)} points in {time.time()-t0:.1f}s")
V = np.array([p.vector for p in points], dtype=np.float32)
print(f"V shape: {V.shape}, L2 mean={np.linalg.norm(V, axis=1).mean():.4f}")

print("\n" + "="*100)
print("TEST 1: BASELINE METRICS")
print("="*100)
def anisotropy(M, n_pairs=2000):
    rng = np.random.default_rng(42)
    idx_a = rng.integers(0, len(M), n_pairs)
    idx_b = rng.integers(0, len(M), n_pairs)
    valid = idx_a != idx_b
    cos = np.sum(M[idx_a[valid]] * M[idx_b[valid]], axis=1) / (
        np.linalg.norm(M[idx_a[valid]], axis=1) * np.linalg.norm(M[idx_b[valid]], axis=1)
    )
    return float(cos.mean())

def effective_rank(M, n=200):
    sub = M[:n]
    _, s, _ = np.linalg.svd(sub, full_matrices=False)
    p = s / s.sum()
    ent = -np.sum(p * np.log(p + 1e-12))
    return float(np.exp(ent))

ani_base = anisotropy(V)
rank_base = effective_rank(V, 200)
print(f"Baseline anisotropy mean cos: {ani_base:.4f}  (>0.5 = collapsed)")
print(f"Baseline effective rank:      {rank_base:.1f}/200  ({rank_base/200*100:.1f}%)")

print("\n" + "="*100)
print("TEST 2: C1 WHITENING (Mu and Viswanath 2018)")
print("="*100)
t0 = time.time()
mu = V.mean(axis=0)
V_centered = V - mu
U, S, Vt = np.linalg.svd(V_centered, full_matrices=False)
K = min(1024, V_centered.shape[0])
W = Vt[:K].T @ np.diag(1.0 / (S[:K] + 1e-6)) @ Vt[:K]
V_white = V_centered @ W
V_white = V_white / (np.linalg.norm(V_white, axis=1, keepdims=True) + 1e-12)
print(f"Whitening computed in {time.time()-t0:.1f}s")

ani_white = anisotropy(V_white)
rank_white = effective_rank(V_white, 200)
print(f"Whitened anisotropy mean cos: {ani_white:.4f}  (delta={ani_white-ani_base:+.4f})")
print(f"Whitened effective rank:      {rank_white:.1f}/200  (delta={rank_white-rank_base:+.1f})")

rng = np.random.default_rng(42)
sample_idx = rng.choice(len(V), size=50, replace=False)
correct_base = 0
correct_white = 0
for i in sample_idx:
    sims = V @ V[i]
    if np.argmax(sims) == i: correct_base += 1
    sims_w = V_white @ V_white[i]
    if np.argmax(sims_w) == i: correct_white += 1
print(f"Self-recall@1 baseline:  {correct_base}/50 = {correct_base/50:.3f}")
print(f"Self-recall@1 whitened:  {correct_white}/50 = {correct_white/50:.3f}")

print("\n--- Whitening A/B on 4 problematic queries ---")
test_queries_idx = [3, 11, 2, 0]
for idx in test_queries_idx:
    q = QUERIES[idx]
    qv = embed_q(q)
    qv_w = (qv - mu)
    qv_w = qv_w @ W
    qv_w = qv_w / (np.linalg.norm(qv_w) + 1e-12)
    sims_v = V @ qv
    sims_w = V_white @ qv_w
    top_v = np.argsort(-sims_v)[:5]
    top_w = np.argsort(-sims_w)[:5]
    print(f"\n[Q] {q!r}")
    pv = points[top_v[0]].payload
    pw = points[top_w[0]].payload
    print(f"   VEC top-1: {(pv.get('name','?') or '?')[:30]:30s} @ {short(pv.get('module_path',''))}")
    print(f"   WHT top-1: {(pw.get('name','?') or '?')[:30]:30s} @ {short(pw.get('module_path',''))}")
    overlap = len(set(top_v.tolist()) & set(top_w.tolist()))
    print(f"   top-5 overlap: {overlap}/5")

print("\n" + "="*100)
print("TEST 3: A1 CHUNKER (simulate larger chunks via module-level aggregation)")
print("="*100)
modules = defaultdict(list)
for p in points:
    mod = p.payload.get('module_path', '?')
    content = p.payload.get('content', '') or ''
    if content:
        modules[mod].append(content[:600])

big_modules = sorted(modules.items(), key=lambda kv: -len(kv[1]))[:50]
print(f"Top-50 modules: avg chunks/mod = {sum(len(c) for _, c in big_modules)/50:.1f}")

agg_texts = []
for mod, contents in big_modules:
    agg = " ".join(contents[:3])[:1800]
    agg_texts.append(agg)

print(f"Embedding {len(agg_texts)} aggregated chunks via TEI...")
t0 = time.time()
agg_vectors = []
BATCH = 16
for i in range(0, len(agg_texts), BATCH):
    batch = agg_texts[i:i+BATCH]
    r = http.post("http://localhost:8080/embed", json={"inputs": batch, "normalize": True, "truncate": True})
    d = r.json()
    if isinstance(d, dict) and "embeddings" in d: d = d["embeddings"]
    agg_vectors.extend(d)
agg_V = np.array(agg_vectors, dtype=np.float32)
print(f"Aggregated chunks embedded in {time.time()-t0:.1f}s")

ani_agg = anisotropy(agg_V)
rank_agg = effective_rank(agg_V, min(50, len(agg_V)))
print(f"Aggregated anisotropy:     {ani_agg:.4f}  (vs base {ani_base:.4f}, delta={ani_agg-ani_base:+.4f})")
print(f"Aggregated eff_rank:       {rank_agg:.1f}/{min(50, len(agg_V))} = {rank_agg/min(50, len(agg_V))*100:.1f}%")
print(f"(baseline rank ratio: {rank_base/200*100:.1f}%)")

print("\n" + "="*100)
print("TEST 4: BM25 SPARSE (TF-IDF with sublinear_tf, sklearn)")
print("="*100)
from sklearn.feature_extraction.text import TfidfVectorizer

def tokenize(text):
    return re.findall(r"[\wа-яА-Я]+", text.lower(), flags=re.UNICODE)

doc_texts = []
doc_payloads = []
for p in points:
    text = ((p.payload.get('content', '') or '') + " " + (p.payload.get('name', '') or ''))[:2000]
    if text.strip():
        doc_texts.append(text)
        doc_payloads.append(p)

print(f"Building TF-IDF on {len(doc_texts)} chunks...")
t0 = time.time()
vectorizer = TfidfVectorizer(
    tokenizer=tokenize, lowercase=False, token_pattern=None,
    max_features=20000, sublinear_tf=True,
)
tfidf_matrix = vectorizer.fit_transform(doc_texts)
print(f"TF-IDF built in {time.time()-t0:.1f}s, vocab={len(vectorizer.vocabulary_)}")

def vec_search_local(qv, k=5):
    sims = V @ qv
    return np.argsort(-sims)[:k]

def bm25_search_local(q, k=5):
    qvec = vectorizer.transform([q])
    sims = (tfidf_matrix @ qvec.T).toarray().flatten()
    return np.argsort(-sims)[:k]

def rrf_local(v_ranks, b_ranks, top=5, k_rank=60):
    score = defaultdict(float)
    for r, idx in enumerate(v_ranks, 1): score[int(idx)] += 1.0/(k_rank + r)
    for r, idx in enumerate(b_ranks, 1): score[int(idx)] += 1.0/(k_rank + r)
    return [pid for pid, _ in sorted(score.items(), key=lambda kv: -kv[1])[:top]]

print("\n--- 20-query A/B: Vector / BM25 / RRF-Hybrid ---")
v_top1, b_top1, h_top1 = [], [], []
v_b_overlap = []
for q in QUERIES:
    qv = embed_q(q)
    vr = vec_search_local(qv, 5)
    br = bm25_search_local(q, 5)
    hr = rrf_local(vr, br, top=5)
    v_top1.append(int(vr[0]))
    b_top1.append(int(br[0]))
    h_top1.append(int(hr[0]))
    v_b_overlap.append(len(set(vr.tolist()) & set(br.tolist())))

print(f"Vector top-1 unique modules: {len(set(v_top1))}/20")
print(f"BM25   top-1 unique modules: {len(set(b_top1))}/20")
print(f"RRF    top-1 unique modules: {len(set(h_top1))}/20")
print(f"V<->BM25 top-5 mean overlap: {statistics.fmean(v_b_overlap):.2f}/5")
print(f"V<->BM25 same top-1: {sum(1 for v,b in zip(v_top1, b_top1) if v==b)}/20")
print(f"V<->RRF same top-1:  {sum(1 for v,h in zip(v_top1, h_top1) if v==h)}/20")
print(f"BM25<->RRF same top-1: {sum(1 for b,h in zip(b_top1, h_top1) if b==h)}/20")

print("\n--- Detailed top-1 comparison (5 critical queries) ---")
critical_idx = [3, 11, 14, 6, 7]
for idx in critical_idx:
    q = QUERIES[idx]
    print(f"\n[{idx+1:2d}] {q!r}")
    pv = doc_payloads[v_top1[idx]].payload
    pb = doc_payloads[b_top1[idx]].payload
    ph = doc_payloads[h_top1[idx]].payload
    print(f"   V :  {(pv.get('name','?') or '?')[:32]:32s} @ {short(pv.get('module_path',''))}")
    print(f"   BM:  {(pb.get('name','?') or '?')[:32]:32s} @ {short(pb.get('module_path',''))}")
    print(f"   H :  {(ph.get('name','?') or '?')[:32]:32s} @ {short(ph.get('module_path',''))}")

print("\n" + "="*100)
print("SYNTHESIS")
print("="*100)
print(f"Total time: {time.time()-t_start:.1f}s\n")
print(f"## C1 WHITENING")
print(f"   anisotropy:  {ani_base:.4f} -> {ani_white:.4f}  ({(ani_white-ani_base)/ani_base*100:+.1f}%)")
print(f"   eff_rank:    {rank_base:.1f} -> {rank_white:.1f}")
print(f"   self-recall: {correct_base}/50 -> {correct_white}/50")
print()
print(f"## A1 LARGER CHUNKS (50 modules, ~1800 chars each)")
print(f"   anisotropy: {ani_agg:.4f}  (vs base {ani_base:.4f})")
print(f"   eff_rank:   {rank_agg/min(50,len(agg_V))*100:.1f}%  (vs base {rank_base/200*100:.1f}%)")
print()
print(f"## BM25 SPARSE (TF-IDF sublinear_tf)")
print(f"   Vector and BM25 agree on top-1: {sum(1 for v,b in zip(v_top1, b_top1) if v==b)}/20")
print(f"   Vector-BM25 top-5 overlap: {statistics.fmean(v_b_overlap):.2f}/5")
print(f"   Unique top-1 modules: V={len(set(v_top1))}, BM25={len(set(b_top1))}, RRF={len(set(h_top1))}")
