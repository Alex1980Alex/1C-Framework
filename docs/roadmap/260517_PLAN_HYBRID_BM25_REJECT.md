# §4.1.16 — Hybrid Dense+BM25 RRF Bench (REJECT verdict, 2026-05-17)

> **Статус:** ATTEMPTED, REJECT — gives -14.6% NDCG vs dense-only на PDF corpus. Script готов для retry с разными параметрами.

## Why

Hybrid retrieval (dense + BM25 sparse, RRF fusion) — стандартный pattern для production retrieval systems. Гипотеза: дополнит dense semantic с lexical exact-match recall для technical identifiers.

## Implementation

[`scripts/bench_hybrid_pdf_documents.py`](../../../scripts/bench_hybrid_pdf_documents.py):
1. Recreate `pdf_documents_hybrid` с named vectors `dense` (1024d Qwen3 MRL cosine + SQ int8) + `bm25` (sparse, IDF modifier)
2. Scroll `pdf_documents_4096_backup` (830 pts × 4096d) → truncate dense to 1024d + BM25 sparse через `fastembed` `Qdrant/bm25` model
3. Upsert 830 pts в 2.2s
4. Bench: 18 grounded PDF queries → dense-only vs RRF fusion (default k=60)

## Results

| Mode | NDCG@10 | Δ vs dense-only | Verdict |
|---|---|---|---|
| dense-only (current production) | 0.4220 | — | baseline |
| Hybrid RRF (default k=60) | **0.3605** | **−14.6%** | ❌ REJECT |

## Why REJECT

**Hybrid не free win — добавляет noise если dense уже сильный.**

1. **Dense quality высокое:** Qwen3-Embedding-8B + MRL truncation дают NDCG 0.42 на PDF — robust semantic retrieval
2. **BM25 noise:** PDF chunks = page text via PyMuPDF — содержат headers/footers/page numbers. BM25 цепляется за keyword matches с irrelevant chunks
3. **RRF dilution:** при k=60 sparse и dense получают равный вес. Если sparse приносит больше шума чем signal — RRF разбавляет хорошее ранжирование
4. **Cyrillic tokenization:** BM25 `Qdrant/bm25` использует standard tokenization — может не оптимально для русского технического текста

## Когда hybrid выигрывает (literature)

- Dense baseline weak (NDCG < 0.3) — sparse spotlight'ит exact-match признаки
- Query distribution содержит много identifier lookup (`find class XyzManager`)
- Corpus имеет много короткий технических chunks где BM25 точнее

Для нашей текущей setup (NDCG 0.42+ dense) hybrid не оправдан без тюнинга:

## Future tuning options (если retry)

1. **Lower BM25 weight:** RRF `k=60` → `k=120-200` (уменьшит влияние sparse)
2. **Russian BM25 tokenizer:** custom через PyMorphy2 lemmatization
3. **Filter chunks:** skip BM25 на chunks без unique identifiers (only embed pure text via dense)
4. **Try other corpora:** maybe `framework_code_v1` где Python identifiers могут лучше работать с BM25

## Action taken

- Dropped `pdf_documents_hybrid` (failed proof collection)
- `pdf_documents` alias остаётся на `pdf_documents_mrl_1024` (dense-only, 1024d MRL + SQ int8)
- Script сохранён для будущего retry с разными параметрами

## Files

- [`scripts/bench_hybrid_pdf_documents.py`](../../../scripts/bench_hybrid_pdf_documents.py) — recreate + bench script
