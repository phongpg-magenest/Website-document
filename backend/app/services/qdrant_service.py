from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    SearchParams,
)

from app.core.config import settings
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = embedding_service.vector_size

    async def init_collection(self):
        """Initialize Qdrant collection if not exists"""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")
        else:
            logger.info(f"Qdrant collection already exists: {self.collection_name}")

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return embedding_service.get_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        return embedding_service.get_embeddings_batch(texts)

    async def index_document_chunks(
        self,
        document_id: UUID,
        chunks: List[str],
        metadata: Dict[str, Any],
    ) -> bool:
        """Index document chunks into Qdrant"""
        try:
            embeddings = self.get_embeddings_batch(chunks)
            points = []

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = f"{document_id}_{i}"
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "document_id": str(document_id),
                            "chunk_index": i,
                            "content": chunk,
                            **metadata,
                        },
                    )
                )

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info(f"Indexed {len(chunks)} chunks for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error indexing document {document_id}: {e}")
            return False

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search in Qdrant"""
        try:
            query_vector = embedding_service.get_query_embedding(query)

            # Build filter conditions
            filter_conditions = []
            if filters:
                if filters.get("project_id"):
                    filter_conditions.append(
                        FieldCondition(
                            key="project_id",
                            match=MatchValue(value=str(filters["project_id"])),
                        )
                    )
                if filters.get("owner_id"):
                    filter_conditions.append(
                        FieldCondition(
                            key="owner_id",
                            match=MatchValue(value=str(filters["owner_id"])),
                        )
                    )
                if filters.get("file_type"):
                    filter_conditions.append(
                        FieldCondition(
                            key="file_type",
                            match=MatchValue(value=filters["file_type"]),
                        )
                    )

            search_filter = Filter(must=filter_conditions) if filter_conditions else None

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=search_filter,
                search_params=SearchParams(hnsw_ef=128, exact=False),
            )

            return [
                {
                    "document_id": hit.payload.get("document_id"),
                    "chunk_index": hit.payload.get("chunk_index"),
                    "content": hit.payload.get("content"),
                    "score": hit.score,
                    "metadata": {
                        k: v
                        for k, v in hit.payload.items()
                        if k not in ["document_id", "chunk_index", "content"]
                    },
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete all chunks of a document from Qdrant"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        )
                    ]
                ),
            )
            logger.info(f"Deleted document {document_id} from Qdrant")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return False


# Singleton instance
qdrant_service = QdrantService()
