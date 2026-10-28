"""
Curated evipedia.ai references for clinician decision support.

These links inform experts when answering tickets or browsing the knowledge
library. They are NOT part of the deterministic rule engine.

Search uses embedding similarity when GITHUB_TOKEN is configured (same model as
the knowledge library); otherwise falls back to weighted keyword scoring.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.storage.data_paths import subdir

_ROOT = Path(__file__).resolve().parents[2]
_YAML_PATH = _ROOT / "knowledge" / "evipedia_references.yml"
_INDEX_FILE = subdir("knowledge") / "evipedia_search_index.json"
_BASE_URL = "https://evipedia.ai"
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_SEMANTIC_MIN_SCORE = 0.22


@dataclass(frozen=True)
class EvipediaRef:
    id: str
    title: str
    slug: str
    category: str
    summary: str
    tags: tuple[str, ...]
    ayun_topics: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"{_BASE_URL}/{self.slug}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "url": self.url,
            "category": self.category,
            "summary": self.summary,
            "tags": list(self.tags),
            "ayun_topics": list(self.ayun_topics),
        }


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embed_texts(texts: list[str]) -> list[list[float]] | None:
    from backend.ai import chatbot as cb

    return cb.embed_texts(texts)


@lru_cache(maxsize=1)
def load_evipedia_refs() -> tuple[EvipediaRef, ...]:
    if not _YAML_PATH.exists():
        return ()
    raw = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8")) or {}
    refs: list[EvipediaRef] = []
    for ref_id, row in (raw.get("references") or {}).items():
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or ref_id).strip()
        if not slug:
            continue
        refs.append(
            EvipediaRef(
                id=str(ref_id),
                title=str(row.get("title") or ref_id.replace("_", " ").title()),
                slug=slug,
                category=str(row.get("category") or "General"),
                summary=str(row.get("summary") or ""),
                tags=tuple(str(t) for t in (row.get("tags") or [])),
                ayun_topics=tuple(str(t) for t in (row.get("ayun_topics") or [])),
            )
        )
    return tuple(refs)


def list_evipedia_refs(*, category: str | None = None) -> list[dict[str, Any]]:
    refs = load_evipedia_refs()
    if category:
        cat = category.strip().lower()
        refs = [r for r in refs if r.category.lower() == cat]
    return [r.to_dict() for r in refs]


def _ref_search_text(ref: EvipediaRef) -> str:
    return "\n".join(
        [
            ref.title,
            ref.category,
            ref.summary,
            " ".join(ref.tags),
            " ".join(t.replace("_", " ") for t in ref.ayun_topics),
        ]
    )


def _refs_by_id() -> dict[str, EvipediaRef]:
    return {r.id: r for r in load_evipedia_refs()}


def _content_hash(refs: tuple[EvipediaRef, ...]) -> str:
    payload = json.dumps(
        [{"id": r.id, "text": _ref_search_text(r)} for r in refs],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _build_evipedia_index() -> dict[str, Any]:
    refs = load_evipedia_refs()
    content_hash = _content_hash(refs)
    existing = _load_index()
    from backend.ai import chatbot as cb

    if existing and existing.get("content_hash") == content_hash:
        # Rebuild if we previously had no embeddings but GITHUB_TOKEN is now available
        if existing.get("semantic") or not cb.is_configured():
            return existing

    texts = [_ref_search_text(r) for r in refs]
    embeddings = _embed_texts(texts) if texts else None
    documents: list[dict[str, Any]] = []
    for i, ref in enumerate(refs):
        row = {
            "id": ref.id,
            "title": ref.title,
            "category": ref.category,
            "text": texts[i],
        }
        if embeddings and i < len(embeddings):
            row["embedding"] = embeddings[i]
        documents.append(row)

    index = {
        "content_hash": content_hash,
        "semantic": bool(embeddings),
        "documents": documents,
    }
    _save_index(index)
    return index


def _query_text(query: str, *, category: str = "") -> str:
    parts = [query.strip()]
    cat = category.strip()
    if cat and cat.lower() != "general":
        parts.append(cat)
    return " ".join(p for p in parts if p)


def _score_ref(query: str, ref: EvipediaRef, *, category: str = "") -> float:
    q_tokens = _tokenize(query)
    if category and category.lower() != "general":
        q_tokens |= _tokenize(category)
    if not q_tokens:
        return 0.0

    title_tokens = _tokenize(ref.title)
    category_tokens = _tokenize(ref.category)
    tag_tokens = _tokenize(" ".join(ref.tags))
    topic_tokens = _tokenize(" ".join(ref.ayun_topics))
    body_tokens = _tokenize(_ref_search_text(ref))

    score = 0.0
    for token in q_tokens:
        if token in title_tokens:
            score += 4.0
        if token in tag_tokens:
            score += 3.0
        if token in topic_tokens:
            score += 2.5
        if token in category_tokens:
            score += 2.0
        if token in body_tokens:
            score += 1.0
        for pool in (title_tokens, tag_tokens, body_tokens):
            for bt in pool:
                if len(token) > 3 and (token in bt or bt in token):
                    score += 0.3
    return score


def _keyword_matches(
    query: str,
    *,
    category: str = "",
    limit: int = 6,
) -> list[tuple[float, EvipediaRef]]:
    scored: list[tuple[float, EvipediaRef]] = []
    for ref in load_evipedia_refs():
        score = _score_ref(query, ref, category=category)
        if score > 0:
            scored.append((score, ref))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def _semantic_matches(
    query: str,
    *,
    category: str = "",
    limit: int = 6,
) -> list[tuple[float, EvipediaRef]] | None:
    search_text = _query_text(query, category=category)
    if not search_text:
        return None

    index = _build_evipedia_index()
    if not index.get("semantic"):
        return None

    query_embedding = _embed_texts([search_text])
    if not query_embedding:
        return None

    refs = _refs_by_id()
    q_vec = query_embedding[0]
    scored: list[tuple[float, EvipediaRef]] = []
    for doc in index.get("documents") or []:
        emb = doc.get("embedding")
        ref = refs.get(doc.get("id", ""))
        if not emb or not ref:
            continue
        score = _cosine(q_vec, emb)
        if score >= _SEMANTIC_MIN_SCORE:
            scored.append((score, ref))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def _rows_from_scored(
    scored: list[tuple[float, EvipediaRef]],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    if not scored:
        return []

    max_score = scored[0][0]
    hits: list[dict[str, Any]] = []
    for score, ref in scored:
        row = ref.to_dict()
        row["score"] = round(score / max_score, 4) if max_score else 0.0
        row["raw_score"] = round(score, 4)
        row["kind"] = "evipedia"
        row["snippet"] = ref.summary
        row["source"] = "evipedia.ai"
        row["match_mode"] = mode
        hits.append(row)
    return hits


def search_evipedia(
    query: str,
    *,
    category: str = "",
    limit: int = 6,
) -> dict[str, Any]:
    """Semantic or keyword search over curated evipedia references."""
    query = (query or "").strip()
    category = (category or "").strip()
    if not _query_text(query, category=category):
        return {"query": query, "category": category, "mode": "none", "matches": [], "total": 0}

    safe_limit = max(1, min(limit, 20))

    semantic = _semantic_matches(query, category=category, limit=safe_limit)
    if semantic:
        matches = _rows_from_scored(semantic, mode="semantic")
        return {
            "query": query,
            "category": category,
            "mode": "semantic",
            "matches": matches,
            "total": len(matches),
        }

    keyword = _keyword_matches(query, category=category, limit=safe_limit)
    matches = _rows_from_scored(keyword, mode="keyword")
    return {
        "query": query,
        "category": category,
        "mode": "keyword" if matches else "none",
        "matches": matches,
        "total": len(matches),
    }


def match_evipedia(
    query: str,
    *,
    category: str = "",
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Backward-compatible helper — returns match rows only."""
    return search_evipedia(query, category=category, limit=limit)["matches"]


def format_evipedia_block(matches: list[dict[str, Any]]) -> str:
    """Format matched references for LLM system prompts."""
    if not matches:
        return "(No closely matched evipedia reviews for this question.)"

    lines = [
        "Use these Forever Healthy evidence review links as optional background.",
        "Do NOT treat them as AYUN-validated answers. Clinician judgment applies.",
        "",
    ]
    for i, row in enumerate(matches, start=1):
        lines.append(f"[Web {i}] {row['title']} ({row['category']})")
        lines.append(f"    Location: {row['url']}")
        if row.get("summary"):
            lines.append(f"    Summary: {row['summary']}")
        lines.append("")
    return "\n".join(lines).rstrip()
