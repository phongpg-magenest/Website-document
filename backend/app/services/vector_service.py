from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class VectorService:
    def __init__(self):
        self.vector_size = embedding_service.vector_size

    async def init_pgvector(self, db: AsyncSession):
        """Initialize pgvector extension and create table"""
        try:
            # Enable pgvector extension
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Create document_chunks table with vector column
            await db.execute(text(f"""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id SERIAL PRIMARY KEY,
                    document_id UUID NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector({self.vector_size}),
                    metadata JSONB DEFAULT '{{}}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(document_id, chunk_index)
                )
            """))

            # Create index for vector similarity search
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
                ON document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """))

            await db.commit()
            logger.info("pgvector initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing pgvector: {e}")
            await db.rollback()

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return embedding_service.get_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        return embedding_service.get_embeddings_batch(texts)

    async def index_document_chunks(
        self,
        db: AsyncSession,
        document_id: UUID,
        chunks: List[str],
        metadata: Dict[str, Any],
    ) -> bool:
        """Index document chunks into pgvector"""
        try:
            embeddings = self.get_embeddings_batch(chunks)

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                embedding_str = f"[{','.join(map(str, embedding))}]"

                await db.execute(
                    text("""
                        INSERT INTO document_chunks (document_id, chunk_index, content, embedding, metadata)
                        VALUES (:doc_id, :idx, :content, :embedding::vector, :metadata::jsonb)
                        ON CONFLICT (document_id, chunk_index)
                        DO UPDATE SET content = :content, embedding = :embedding::vector, metadata = :metadata::jsonb
                    """),
                    {
                        "doc_id": str(document_id),
                        "idx": i,
                        "content": chunk,
                        "embedding": embedding_str,
                        "metadata": str(metadata).replace("'", '"'),
                    }
                )

            await db.commit()
            logger.info(f"Indexed {len(chunks)} chunks for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error indexing document {document_id}: {e}")
            await db.rollback()
            return False

    async def search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search using pgvector"""
        try:
            query_embedding = embedding_service.get_query_embedding(query)
            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            # Build filter conditions
            filter_sql = ""
            params = {"embedding": embedding_str, "top_k": top_k}

            if filters:
                conditions = []
                if filters.get("project_id"):
                    conditions.append("metadata->>'project_id' = :project_id")
                    params["project_id"] = str(filters["project_id"])
                if filters.get("owner_id"):
                    conditions.append("metadata->>'owner_id' = :owner_id")
                    params["owner_id"] = str(filters["owner_id"])
                if filters.get("file_type"):
                    conditions.append("metadata->>'file_type' = :file_type")
                    params["file_type"] = filters["file_type"]

                if conditions:
                    filter_sql = "WHERE " + " AND ".join(conditions)

            result = await db.execute(
                text(f"""
                    SELECT
                        document_id,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> :embedding::vector) as score
                    FROM document_chunks
                    {filter_sql}
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT :top_k
                """),
                params
            )

            rows = result.fetchall()

            return [
                {
                    "document_id": str(row.document_id),
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "score": float(row.score),
                    "metadata": row.metadata or {},
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def delete_document(self, db: AsyncSession, document_id: UUID) -> bool:
        """Delete all chunks of a document"""
        try:
            await db.execute(
                text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
                {"doc_id": str(document_id)}
            )
            await db.commit()
            logger.info(f"Deleted document {document_id} from vector store")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            await db.rollback()
            return False


# Singleton instance
vector_service = VectorService()
