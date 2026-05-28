"""
ChromaDB-backed knowledge base.  Loaded once at startup from Markdown/text files
in KNOWLEDGE_BASE_DIR.  Each paragraph becomes one chunk with a stable chunk_id
derived from (filename, paragraph_index).
"""
from __future__ import annotations
import hashlib
import os
import re
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from ..config import settings


_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


_embed_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name="supplier_knowledge",
            embedding_function=_embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk_id(source_file: str, idx: int) -> str:
    raw = f"{source_file}::{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _load_documents() -> list[dict]:
    kb_dir = Path(settings.knowledge_base_dir)
    docs = []
    for fpath in sorted(kb_dir.glob("*.md")):
        text = fpath.read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        current_heading = ""
        for idx, para in enumerate(paragraphs):
            # Track the nearest ## heading so each chunk carries its section context
            if para.startswith("#"):
                current_heading = para.lstrip("#").strip()
                continue
            # Prepend the section heading so the LLM knows which entity a chunk belongs to
            content = f"[{current_heading}]\n{para}" if current_heading else para
            docs.append({
                "chunk_id": _chunk_id(fpath.name, idx),
                "content": content,
                "source": fpath.name,
                "paragraph_index": idx,
            })
    return docs


async def build_knowledge_base(force_rebuild: bool = False) -> int:
    """Load documents into ChromaDB.  Skip if already populated (unless forced)."""
    collection = _get_collection()

    if not force_rebuild and collection.count() > 0:
        return collection.count()

    docs = _load_documents()
    if not docs:
        return 0

    batch_size = 50
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        texts = [d["content"] for d in batch]
        ids = [d["chunk_id"] for d in batch]
        metadatas = [{"source": d["source"], "paragraph_index": d["paragraph_index"]} for d in batch]
        # collection already has _embed_fn attached; just pass documents
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)

    return len(docs)
