"""
RAG retrieval layer.  Every supplier score MUST call retrieve() before
invoking the LLM — this is enforced in the base agent.
"""
from __future__ import annotations
from typing import List, Dict

from .knowledge_base import _get_collection


async def retrieve_supplier_chunks(
    query: str,
    top_k: int = 10,
) -> List[Dict]:
    """
    Returns up to top_k chunks most relevant to query.
    Each chunk: {chunk_id, content, source, score}
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    # collection embeds the query automatically using SentenceTransformer
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunk_id = results["ids"][0][len(chunks)]
        chunks.append({
            "chunk_id": chunk_id,
            "content": doc,
            "source": meta.get("source", "unknown"),
            "score": round(1 - dist, 4),  # cosine similarity
        })

    return chunks
