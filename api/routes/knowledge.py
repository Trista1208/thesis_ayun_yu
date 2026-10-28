from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import KnowledgeCaptureRequest
from api.serializers import node_to_expert_dict
from api.routes.auth import ExpertSession
from api.deps import load_env

load_env()

from backend.storage.knowledge_store import list_nodes, delete_node, remove_validated_qa_from_library, store_stats, list_tickets  # noqa: E402
from backend.ai.knowledge_pipeline import capture_manual_knowledge  # noqa: E402
from backend.ai.evipedia_refs import list_evipedia_refs, search_evipedia  # noqa: E402
from backend.ai.knowledge_search import search_knowledge  # noqa: E402
from backend.rules.protocol_library import list_protocol_catalog  # noqa: E402
from api.serializers import ticket_to_expert_dict  # noqa: E402

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/stats")
def knowledge_stats(session: ExpertSession):
    stats = store_stats()
    tickets = list_tickets(limit=500)
    stats["tickets_total"] = len(tickets)
    return stats


@router.get("/nodes")
def knowledge_nodes(session: ExpertSession, limit: int = 100):
    nodes = list_nodes(limit=limit)
    return {"nodes": [node_to_expert_dict(n) for n in nodes]}


@router.get("/search")
def knowledge_search(session: ExpertSession, q: str = "", limit: int = 20):
    """Semantic search over validated Q&A, knowledge nodes, and evipedia refs (experts only)."""
    safe_limit = max(1, min(limit, 50))
    return search_knowledge(q, limit=safe_limit)


@router.get("/protocols")
def knowledge_protocols(session: ExpertSession):
    """Immutable AYUN scientist protocols and workout templates."""
    protocols = list_protocol_catalog()
    return {
        "source": "knowledge/protocols_quick_reference.yml",
        "protocols": protocols,
        "total": len(protocols),
    }


@router.get("/evipedia")
def knowledge_evipedia_catalog(session: ExpertSession, category: str = ""):
    """Curated evipedia.ai evidence reviews for clinician reference."""
    return {
        "source": "https://evipedia.ai",
        "references": list_evipedia_refs(category=category or None),
    }


@router.get("/evipedia/match")
def knowledge_evipedia_match(session: ExpertSession, q: str = "", category: str = "", limit: int = 6):
    """Semantic (or keyword) match against curated evipedia references."""
    safe_limit = max(1, min(limit, 20))
    return search_evipedia(q, category=category, limit=safe_limit)


@router.get("/qa")
def knowledge_validated_qa(session: ExpertSession, limit: int = 100):
    """All validated member Q&A — expert knowledge base (not visible to members)."""
    tickets = [t for t in list_tickets(limit=limit) if t.status == "validated"]
    return {"tickets": [ticket_to_expert_dict(t) for t in tickets]}


@router.post("/nodes")
def capture_node(body: KnowledgeCaptureRequest, session: ExpertSession):
    if not body.title.strip() or not body.content.strip():
        raise HTTPException(status_code=400, detail="Title and content required")
    node = capture_manual_knowledge(
        title=body.title,
        category=body.category,
        content=body.content,
        captured_by=body.captured_by or session["name"],
    )
    return {"node": node_to_expert_dict(node)}


@router.delete("/nodes/{node_id}")
def remove_node(node_id: str, session: ExpertSession):
    if not delete_node(node_id):
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True, "id": node_id}


@router.delete("/qa/{ticket_id}")
def remove_validated_qa(ticket_id: str, session: ExpertSession):
    """Remove validated Q&A from the knowledge library (corpus node + unvalidate ticket)."""
    if not remove_validated_qa_from_library(ticket_id):
        raise HTTPException(status_code=404, detail="Validated Q&A not found")
    return {"ok": True, "id": ticket_id}
