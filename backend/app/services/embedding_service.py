"""
Embedding Service - Hỗ trợ cả Local TEI và Google Gemini API
- Local: AITeamVN/Vietnamese_Embedding via TEI (1024 dimensions)
- Cloud: Google Gemini text-embedding-004 (768 dimensions)
"""
from typing import List
import logging
import httpx
import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Gemini embedding model - outputs 768 dimensions
GEMINI_EMBEDDING_MODEL = "models/text-embedding-004"
GEMINI_VECTOR_SIZE = 768

# Local TEI - outputs 1024 dimensions
LOCAL_VECTOR_SIZE = 1024


class EmbeddingService:
    def __init__(self):
        self.use_local = settings.USE_LOCAL_RAG

        if self.use_local:
            # Local TEI configuration
            self.tei_url = settings.TEI_URL
            self.vector_size = LOCAL_VECTOR_SIZE
            logger.info(f"EmbeddingService: Using LOCAL TEI at {self.tei_url}")
        else:
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
            self.vector_size = GEMINI_VECTOR_SIZE
            logger.info("EmbeddingService: Using GEMINI API")

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if self.use_local:
            return self._get_local_embedding(text)
        else:
            return self._get_gemini_embedding(text)

    def _get_local_embedding(self, text: str) -> List[float]:
        """Generate embedding using local TEI service"""
        try:
            # TEI has max token limit ~8192, truncate if needed
            # Roughly 4 chars per token for Vietnamese
            max_chars = 30000
            if len(text) > max_chars:
                text = text[:max_chars]
                logger.warning(f"Text truncated to {max_chars} chars for embedding")

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.tei_url}/embed",
                    json={"inputs": text}
                )
                response.raise_for_status()
                embeddings = response.json()
                return embeddings[0]
        except Exception as e:
            logger.error(f"Error generating local embedding: {e}")
            raise

    def _get_gemini_embedding(self, text: str) -> List[float]:
        """Generate embedding using Gemini API"""
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating Gemini embedding: {e}")
            raise

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if self.use_local:
            return self._get_local_embeddings_batch(texts)
        else:
            return self._get_gemini_embeddings_batch(texts)

    def _get_local_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using local TEI service"""
        try:
            # TEI has max token limit ~8192 per text, truncate if needed
            max_chars = 30000
            truncated_texts = []
            for text in texts:
                if len(text) > max_chars:
                    truncated_texts.append(text[:max_chars])
                    logger.warning(f"Batch text truncated to {max_chars} chars")
                else:
                    truncated_texts.append(text)

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.tei_url}/embed",
                    json={"inputs": truncated_texts}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error generating local batch embeddings: {e}")
            raise

    def _get_gemini_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using Gemini API"""
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating Gemini batch embeddings: {e}")
            raise

    def get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query"""
        if self.use_local:
            # TEI không phân biệt query/document, dùng chung
            return self._get_local_embedding(query)
        else:
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
