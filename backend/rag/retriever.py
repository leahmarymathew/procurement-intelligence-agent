"""
RAG retrieval layer.  Every supplier score MUST call retrieve() before
invoking the LLM — this is enforced in the base agent.
"""
from __future__ import annotations
from typing import List, Dict

from langchain_openai import OpenAIEmbeddings
from .knowledge_base import _get_collection
from ..config import settings


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

    embeddings_fn = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model="text-embedding-3-small",
    )
    query_vector = embeddings_fn.embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
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
