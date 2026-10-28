"""
Semantic search over the clinician knowledge library.

Indexes validated Q&A tickets and captured knowledge nodes. Uses embedding
similarity when GITHUB_TOKEN is configured; falls back to weighted keyword
scoring otherwise.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.storage.data_paths import subdir
from backend.ai.evipedia_refs import search_evipedia
from backend.storage.knowledge_store import CapturedNode, KnowledgeTicket, list_nodes, list_tickets
from backend.rules.protocol_library import list_protocol_catalog, protocol_record_text

_INDEX_FILE = subdir("knowledge") / "search_index.json"
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


@dataclass
class SearchHit:
    id: str
    kind: str  # node | qa | evipedia
    title: str
    snippet: str
    category: str
    score: float
    source: str
    created_at: str
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "snippet": self.snippet,
            "category": self.category,
            "score": round(self.score, 4),
            "source": self.source,
            "created_at": self.created_at,
            **self.meta,
        }


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _snippet(text: str, limit: int = 220) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _node_text(node: CapturedNode) -> str:
    parts = [node.title, node.category, node.summary]
    for passage in node.passages or []:
        parts.append(passage.get("excerpt", ""))
        parts.append(passage.get("locator", ""))
    if node.member_context:
        parts.append(node.member_context[:600])
    parts.extend(node.tags or [])
    return "\n".join(p for p in parts if p)


def _ticket_text(ticket: KnowledgeTicket) -> str:
    return "\n".join(
        p
        for p in [
            ticket.question,
            ticket.draft_answer,
            ticket.category,
            ticket.from_name,
            ticket.validated_by,
        ]
        if p
    )


def _collect_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []

    for protocol in list_protocol_catalog():
        body = protocol_record_text(protocol)
        docs.append(
            {
                "id": f"protocol:{protocol['key']}",
                "kind": "protocol",
                "title": protocol["title"],
                "snippet": _snippet(protocol.get("description") or body),
                "category": (
                    "Condition protocol"
                    if protocol.get("kind") == "condition_protocol"
                    else "Training template"
                ),
                "source": protocol.get("source") or "AYUN protocol library",
                "created_at": "",
                "text": body,
            }
        )

    for node in list_nodes(limit=500):
        body = _node_text(node)
        docs.append(
            {
                "id": f"node:{node.id}",
                "kind": "node",
                "title": node.title,
                "snippet": _snippet(node.summary or body),
                "category": node.category,
                "source": node.source,
                "created_at": node.created_at,
                "text": body,
                "captured_by": node.captured_by,
            }
        )

    for ticket in list_tickets(limit=500):
        if ticket.status != "validated" or not ticket.draft_answer.strip():
            continue
        body = _ticket_text(ticket)
        docs.append(
            {
                "id": f"qa:{ticket.id}",
                "kind": "qa",
                "title": ticket.question,
                "snippet": _snippet(ticket.draft_answer),
                "category": ticket.category,
                "source": ticket.source,
                "created_at": ticket.updated_at or ticket.created_at,
                "text": body,
                "validated_by": ticket.validated_by,
                "from_name": ticket.from_name,
            }
        )

    return docs


def _content_hash(docs: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        [{"id": d["id"], "text": d["text"]} for d in docs],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _keyword_score(query: str, doc: dict[str, Any]) -> float:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0

    title_tokens = _tokenize(doc.get("title", ""))
    category_tokens = _tokenize(doc.get("category", ""))
    body_tokens = _tokenize(doc.get("text", ""))

    score = 0.0
    for token in q_tokens:
        if token in title_tokens:
            score += 3.0
        if token in category_tokens:
            score += 2.0
        if token in body_tokens:
            score += 1.0
        # Partial matches help with compound clinical terms
        for bt in body_tokens | title_tokens:
            if token in bt or bt in token:
                score += 0.25
    return score


def _embed_texts(texts: list[str]) -> list[list[float]] | None:
    from backend.ai import chatbot as cb

    return cb.embed_texts(texts)


def _load_index() -> dict[str, Any] | None:
    if not _INDEX_FILE.exists():
        return None
    try:
        return json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_index(index: dict[str, Any]) -> None:
    _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def _build_index(docs: list[dict[str, Any]]) -> dict[str, Any]:
    content_hash = _content_hash(docs)
    existing = _load_index()
    if existing and existing.get("content_hash") == content_hash:
        return existing

    indexed: list[dict[str, Any]] = []
    texts = [d["text"] for d in docs]
    embeddings = _embed_texts(texts) if texts else None

    for i, doc in enumerate(docs):
        row = {
            "id": doc["id"],
            "kind": doc["kind"],
            "title": doc["title"],
            "snippet": doc["snippet"],
            "category": doc["category"],
            "source": doc["source"],
            "created_at": doc["created_at"],
            "text": doc["text"],
        }
        for key in ("captured_by", "validated_by", "from_name"):
            if doc.get(key):
                row[key] = doc[key]
        if embeddings and i < len(embeddings):
            row["embedding"] = embeddings[i]
        indexed.append(row)

    index = {
        "content_hash": content_hash,
        "semantic": bool(embeddings),
        "documents": indexed,
    }
    _save_index(index)
    return index


def _evipedia_hits(query: str, *, limit: int) -> list[SearchHit]:
    result = search_evipedia(query, limit=limit)
    hits: list[SearchHit] = []
    for row in result["matches"]:
        hits.append(
            SearchHit(
                id=f"evipedia:{row['id']}",
                kind="evipedia",
                title=row["title"],
                snippet=row.get("snippet") or row.get("summary") or "",
                category=row.get("category") or "Evidence",
                score=float(row.get("score") or 0),
                source="evipedia.ai",
                created_at="",
                meta={
                    "url": row.get("url"),
                    "slug": row.get("slug"),
                    "tags": row.get("tags") or [],
                    "match_mode": row.get("match_mode") or result.get("mode"),
                },
            )
        )
    return hits


def _merge_hits(corpus_hits: list[SearchHit], evipedia_hits: list[SearchHit], *, limit: int) -> list[SearchHit]:
    combined = corpus_hits + evipedia_hits
    combined.sort(key=lambda h: h.score, reverse=True)
    return combined[:limit]


def search_knowledge(query: str, *, limit: int = 20) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {"query": "", "mode": "none", "results": [], "total": 0}

    evipedia = _evipedia_hits(query, limit=min(limit, 8))
    docs = _collect_documents()
    if not docs:
        return {
            "query": query,
            "mode": "evipedia_only" if evipedia else "empty",
            "results": [h.to_dict() for h in evipedia[:limit]],
            "total": len(evipedia),
        }

    index = _build_index(docs)
    mode = "semantic" if index.get("semantic") else "keyword"
    indexed_docs = index.get("documents") or []
    corpus_limit = max(limit - len(evipedia), 1)

    if mode == "semantic":
        query_embedding = _embed_texts([query])
        if query_embedding:
            q_vec = query_embedding[0]
            scored: list[tuple[float, dict[str, Any]]] = []
            for doc in indexed_docs:
                emb = doc.get("embedding")
                if not emb:
                    continue
                score = _cosine(q_vec, emb)
                if score > 0:
                    scored.append((score, doc))
            scored.sort(key=lambda x: x[0], reverse=True)
            corpus_hits = [_hit_from_doc(doc, score) for score, doc in scored[:corpus_limit]]
            merged = _merge_hits(corpus_hits, evipedia, limit=limit)
            return {
                "query": query,
                "mode": mode,
                "results": [h.to_dict() for h in merged],
                "total": len(scored) + len(evipedia),
            }

    # Keyword fallback (or when embeddings unavailable)
    scored_kw: list[tuple[float, dict[str, Any]]] = []
    for doc in indexed_docs:
        score = _keyword_score(query, doc)
        if score > 0:
            scored_kw.append((score, doc))
    scored_kw.sort(key=lambda x: x[0], reverse=True)
    max_score = scored_kw[0][0] if scored_kw else 1.0
    corpus_hits = [_hit_from_doc(doc, score / max_score) for score, doc in scored_kw[:corpus_limit]]
    merged = _merge_hits(corpus_hits, evipedia, limit=limit)
    return {
        "query": query,
        "mode": "keyword",
        "results": [h.to_dict() for h in merged],
        "total": len(scored_kw) + len(evipedia),
    }


def _hit_from_doc(doc: dict[str, Any], score: float) -> SearchHit:
    meta = {}
    if doc.get("captured_by"):
        meta["captured_by"] = doc["captured_by"]
    if doc.get("validated_by"):
        meta["validated_by"] = doc["validated_by"]
    if doc.get("from_name"):
        meta["from_name"] = doc["from_name"]
    return SearchHit(
        id=doc["id"],
        kind=doc["kind"],
        title=doc["title"],
        snippet=doc["snippet"],
        category=doc["category"],
        score=score,
        source=doc.get("source", ""),
        created_at=doc.get("created_at", ""),
        meta=meta,
    )
