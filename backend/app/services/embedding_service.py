"""
Embedding Service using Google Gemini API
Replaces sentence-transformers to reduce Docker image size (~7GB -> ~200MB)
"""
from typing import List
import logging
import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Gemini embedding model - outputs 768 dimensions
GEMINI_EMBEDDING_MODEL = "models/text-embedding-004"
VECTOR_SIZE = 768


class EmbeddingService:
    def __init__(self):
        # Configure Gemini API
        if settings.GEMINI_BASE_URL:
            genai.configure(
                api_key=settings.GEMINI_API_KEY,
                transport="rest",
                client_options={"api_endpoint": settings.GEMINI_BASE_URL}
            )
        else:
            genai.configure(api_key=settings.GEMINI_API_KEY)

        self.model_name = GEMINI_EMBEDDING_MODEL
        self.vector_size = VECTOR_SIZE

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            # Gemini supports batch embedding
            result = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise

    def get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query (uses different task_type)"""
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise


# Singleton instance
embedding_service = EmbeddingService()
