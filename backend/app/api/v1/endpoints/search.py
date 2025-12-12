from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
import time
import logging

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.document import Document
from app.schemas.search import SearchQuery, SearchResponse, SearchResult, SearchSuggestion
from app.services import vector_service, document_processing_service
from app.services.rag_service import rag_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=SearchResponse)
async def semantic_search(
    search_query: SearchQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform semantic search across documents with RAG support.

    - use_rerank=True: Sử dụng Vietnamese Reranker để cải thiện độ chính xác
    - generate_answer=True: Sinh câu trả lời từ LLM dựa trên context tìm được
    """
    start_time = time.time()

    # Build filters
    filters = {}
    if search_query.project_id:
        filters["project_id"] = search_query.project_id
    if search_query.owner_id:
        filters["owner_id"] = search_query.owner_id
    if search_query.file_types and len(search_query.file_types) == 1:
        filters["file_type"] = search_query.file_types[0].value

    # Search in pgvector - lấy nhiều hơn để rerank
    search_multiplier = 3 if search_query.use_rerank else 1
    vector_results = await vector_service.search(
        db=db,
        query=search_query.query,
        top_k=search_query.top_k * search_multiplier,
        filters=filters if filters else None,
    )

    # RAG Processing: Rerank + Generate Answer
    used_rerank = False
    answer = None

    if settings.USE_LOCAL_RAG and vector_results:
        if search_query.use_rerank or search_query.generate_answer:
            rag_result = rag_service.process_search_results(
                query=search_query.query,
                search_results=vector_results,
                generate_answer=search_query.generate_answer
            )

            if search_query.use_rerank and rag_result["reranked_results"]:
                # Cập nhật vector_results với rerank scores
                reranked_map = {
                    r["document_id"]: r.get("rerank_score")
                    for r in rag_result["reranked_results"]
                }
                for vr in vector_results:
                    if vr["document_id"] in reranked_map:
                        vr["rerank_score"] = reranked_map[vr["document_id"]]
                used_rerank = True

            if search_query.generate_answer:
                answer = rag_result.get("answer")

    # Group results by document and get best chunk per document
    doc_results = {}
    for result in vector_results:
        doc_id = result["document_id"]
        # Ưu tiên rerank_score nếu có, fallback về score
        result_score = result.get("rerank_score") or result["score"]
        if doc_id not in doc_results or result_score > (doc_results[doc_id].get("rerank_score") or doc_results[doc_id]["score"]):
            doc_results[doc_id] = result

    # Fetch document details from database
    search_results = []
    doc_ids = list(doc_results.keys())[:search_query.top_k]

    if doc_ids:
        result = await db.execute(
            select(Document).where(Document.id.in_([UUID(d) for d in doc_ids]))
        )
        documents = {str(doc.id): doc for doc in result.scalars().all()}

        for doc_id in doc_ids:
            if doc_id in documents:
                doc = documents[doc_id]
                vector_result = doc_results[doc_id]

                # Generate snippet and highlights
                content = vector_result.get("content", "")
                snippet = document_processing_service.generate_snippet(
                    content, search_query.query
                )
                highlights = document_processing_service.highlight_terms(
                    content, search_query.query
                )

                # Get owner name
                owner_result = await db.execute(
                    select(User).where(User.id == doc.owner_id)
                )
                owner = owner_result.scalar_one_or_none()

                search_results.append(
                    SearchResult(
                        document_id=doc.id,
                        title=doc.title,
                        snippet=snippet,
                        highlights=highlights,
                        score=vector_result["score"],
                        rerank_score=vector_result.get("rerank_score"),
                        file_type=doc.file_type,
                        owner_name=owner.name if owner else "Unknown",
                        project_name=None,
                        tags=doc.tags or [],
                        created_at=doc.created_at,
                    )
                )

    # Sort by rerank_score if available, else by score
    search_results.sort(
        key=lambda x: x.rerank_score if x.rerank_score is not None else x.score,
        reverse=True
    )

    processing_time = (time.time() - start_time) * 1000

    return SearchResponse(
        query=search_query.query,
        results=search_results,
        total=len(search_results),
        processing_time_ms=processing_time,
        answer=answer,
        used_rerank=used_rerank,
    )


@router.get("/suggestions", response_model=SearchSuggestion)
async def get_search_suggestions(
    q: str,
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get search suggestions based on document titles and tags"""
    suggestions = []

    # Search in document titles
    result = await db.execute(
        select(Document.title)
        .where(Document.title.ilike(f"%{q}%"))
        .limit(limit)
    )
    titles = result.scalars().all()
    suggestions.extend(titles)

    # Search in tags (unique)
    result = await db.execute(
        select(Document.tags)
        .where(Document.tags.any(q))
        .limit(limit)
    )
    for tags in result.scalars().all():
        if tags:
            for tag in tags:
                if q.lower() in tag.lower() and tag not in suggestions:
                    suggestions.append(tag)

    return SearchSuggestion(suggestions=suggestions[:limit])
