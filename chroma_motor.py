"""
CRT ChromaDB Motor v0.7 – vektoros hasonlóság-keresés
  crt_raw   – nyers sorok (azonosítás előtt, DB1)
  crt_clean – tisztított cikktörzs tételek (DB2)
Embedding: paraphrase-multilingual-MiniLM-L12-v2 (hu-HU támogatott)
"""
import logging, os
from typing import Optional

log = logging.getLogger("CRT.chroma")

EMBED_MODEL  = "paraphrase-multilingual-MiniLM-L12-v2"
_CHROMA_HOST = os.environ.get("CRT_CHROMA_HOST", "localhost")
_CHROMA_PORT = int(os.environ.get("CRT_CHROMA_PORT", "8001"))

_client: Optional[object] = None
_ef:     Optional[object] = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.HttpClient(host=_CHROMA_HOST, port=_CHROMA_PORT)
    return _client


def _get_ef():
    global _ef
    if _ef is None:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        _ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return _ef


def _col(name: str):
    return _get_client().get_or_create_collection(
        name=name,
        embedding_function=_get_ef(),
        metadata={"hnsw:space": "cosine"},
    )


# ── ÍRÁS ──────────────────────────────────────────────────────

def add_raw(texts: list, ids: list, metadatas: list | None = None) -> bool:
    """
    Nyers sorok indexelése DB1-be (feltöltés / azonosítás előtt).
    ids: egyedi string azonosítók (pl. upload_id + sorszám)
    """
    try:
        col = _col("crt_raw")
        col.upsert(
            documents=texts,
            ids=ids,
            metadatas=metadatas or [{} for _ in texts],
        )
        log.info("ChromaDB raw: %d tétel indexelve", len(texts))
        return True
    except Exception as e:
        log.warning("ChromaDB add_raw hiba: %s", e)
        return False


def add_clean(items: list) -> bool:
    """
    Azonosított/jóváhagyott cikkek indexelése DB2-be.
    Minden item: {item_id, name, manufacturer?, category?, unit?}
    """
    try:
        col = _col("crt_clean")
        docs, ids, metas = [], [], []
        for it in items:
            text = " ".join(filter(None, [
                it.get("name", ""),
                it.get("manufacturer") or "",
                it.get("category") or "",
            ]))
            docs.append(text)
            ids.append(str(it["item_id"]))
            metas.append({
                "name":         it.get("name", ""),
                "manufacturer": it.get("manufacturer") or "",
                "category":     it.get("category") or "",
                "unit":         it.get("unit") or "",
            })
        col.upsert(documents=docs, ids=ids, metadatas=metas)
        log.info("ChromaDB clean: %d cikk indexelve", len(items))
        return True
    except Exception as e:
        log.warning("ChromaDB add_clean hiba: %s", e)
        return False


# ── KERESÉS ───────────────────────────────────────────────────

def search(query: str, collection: str = "crt_clean", n_results: int = 5) -> list:
    """
    Szöveges lekérdezés alapján hasonló tételek keresése.
    Visszatér: [{id, document, metadata, distance, score}, ...]
    score: 1.0 = tökéletes egyezés (cosine)
    """
    col   = _col(collection)
    count = col.count()
    if count == 0:
        return []

    res  = col.query(query_texts=[query], n_results=min(n_results, count))
    out  = []
    ids_       = res["ids"][0]
    docs_      = res["documents"][0]
    metas_     = res["metadatas"][0]
    distances_ = res["distances"][0]

    for i, _id in enumerate(ids_):
        out.append({
            "id":       _id,
            "document": docs_[i],
            "metadata": metas_[i],
            "distance": round(distances_[i], 4),
            "score":    round(1.0 - distances_[i], 4),
        })
    return out


def search_clean(query: str, n_results: int = 5) -> list:
    """Tisztított cikktörzsben keres (crt_clean, DB2)."""
    return search(query, "crt_clean", n_results)


def search_raw(query: str, n_results: int = 5) -> list:
    """Nyers feltöltések közt keres (crt_raw, DB1)."""
    return search(query, "crt_raw", n_results)


# ── STÁTUSZ ───────────────────────────────────────────────────

def stats() -> dict:
    try:
        raw_count   = _col("crt_raw").count()
        clean_count = _col("crt_clean").count()
        return {
            "status":      "ok",
            "raw_count":   raw_count,
            "clean_count": clean_count,
            "embed_model": EMBED_MODEL,
            "host":        f"{_CHROMA_HOST}:{_CHROMA_PORT}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def is_available() -> bool:
    try:
        _get_client().heartbeat()
        return True
    except Exception:
        return False
