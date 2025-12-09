from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
import time
import logging

from app.core.database import get_db
from app.models.user import User
from app.models.document import Document
from app.schemas.search import SearchQuery, SearchResponse, SearchResult, SearchSuggestion
from app.services import vector_service, document_processing_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=SearchResponse)
async def semantic_search(
    search_query: SearchQuery,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Perform semantic search across documents"""
    start_time = time.time()

    # Build filters for Qdrant
    filters = {}
    if search_query.project_id:
        filters["project_id"] = search_query.project_id
    if search_query.owner_id:
        filters["owner_id"] = search_query.owner_id
    if search_query.file_types and len(search_query.file_types) == 1:
        filters["file_type"] = search_query.file_types[0].value

    # Search in pgvector
    vector_results = await vector_service.search(
        db=db,
        query=search_query.query,
        top_k=search_query.top_k * 3,  # Get more to dedupe by document
        filters=filters if filters else None,
    )

    # Group results by document and get best chunk per document
    doc_results = {}
    for result in vector_results:
        doc_id = result["document_id"]
        if doc_id not in doc_results or result["score"] > doc_results[doc_id]["score"]:
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
                qdrant_result = doc_results[doc_id]

                # Generate snippet and highlights
                content = qdrant_result.get("content", "")
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
                        score=qdrant_result["score"],
                        file_type=doc.file_type,
                        owner_name=owner.name if owner else "Unknown",
                        project_name=None,  # TODO: fetch project name
                        tags=doc.tags or [],
                        created_at=doc.created_at,
                    )
                )

    # Sort by score
    search_results.sort(key=lambda x: x.score, reverse=True)

    processing_time = (time.time() - start_time) * 1000  # Convert to ms

    return SearchResponse(
        query=search_query.query,
        results=search_results,
        total=len(search_results),
        processing_time_ms=processing_time,
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
