"""
RAG Service - Reranker + LLM để sinh câu trả lời
- Reranker: AITeamVN/Vietnamese_Reranker via Infinity
- LLM: Qwen2.5:1.5b via Ollama
"""
from typing import List, Dict, Any, Optional
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.reranker_url = settings.RERANKER_URL
        self.ollama_url = settings.OLLAMA_URL
        self.ollama_model = settings.OLLAMA_MODEL
        self.top_k_rerank = settings.RAG_TOP_K_RERANK
        self.max_tokens = getattr(settings, 'RAG_MAX_TOKENS', 2048)
        self.use_local = settings.USE_LOCAL_RAG

    def rerank(self, query: str, documents: List[str]) -> List[Dict[str, Any]]:
        """
        Rerank documents sử dụng Vietnamese Reranker
        Returns: List of {index, relevance_score, document}
        """
        if not self.use_local or not documents:
            # Không dùng local hoặc không có documents, trả về nguyên bản
            return [
                {"index": i, "relevance_score": 1.0, "document": doc}
                for i, doc in enumerate(documents)
            ]

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.reranker_url}/rerank",
                    json={
                        "model": "vietnamese-reranker",
                        "query": query,
                        "documents": documents
                    }
                )
                response.raise_for_status()
                result = response.json()

                # Kết hợp score với document
                reranked = []
                for item in result.get("results", []):
                    idx = item["index"]
                    reranked.append({
                        "index": idx,
                        "relevance_score": item["relevance_score"],
                        "document": documents[idx]
                    })

                # Sort by relevance_score descending
                reranked.sort(key=lambda x: x["relevance_score"], reverse=True)
                return reranked

        except Exception as e:
            logger.error(f"Rerank error: {e}")
            # Fallback: trả về documents nguyên bản
            return [
                {"index": i, "relevance_score": 1.0, "document": doc}
                for i, doc in enumerate(documents)
            ]

    def generate_answer(
        self,
        query: str,
        context_chunks: List[str],
        max_tokens: int = None
    ) -> Optional[str]:
        """
        Sinh câu trả lời từ LLM dựa trên context
        """
        if not self.use_local or not context_chunks:
            return None

        if max_tokens is None:
            max_tokens = self.max_tokens

        try:
            # Build context - đánh số để dễ theo dõi
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                context_parts.append(f"[{i}] {chunk}")
            context = "\n\n".join(context_parts)

            prompt = f"""Bạn là trợ lý AI chuyên trả lời câu hỏi dựa trên tài liệu. Hãy đọc kỹ thông tin tham khảo và trả lời câu hỏi một cách ĐẦY ĐỦ và CHI TIẾT bằng tiếng Việt.

Quy tắc:
- Trả lời đầy đủ, không bỏ sót thông tin quan trọng
- Nếu có nhiều mục/danh sách, liệt kê hết
- Nếu có số liệu, trích dẫn chính xác
- Nếu thông tin không đủ để trả lời, hãy nói rõ

Thông tin tham khảo:
{context}

Câu hỏi: {query}

Trả lời đầy đủ:"""

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.3
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"LLM generate error: {e}")
            return None

    def process_search_results(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        generate_answer: bool = True
    ) -> Dict[str, Any]:
        """
        Xử lý kết quả search: Rerank + Generate answer

        Args:
            query: Câu hỏi của user
            search_results: Kết quả từ vector search (có content, score, document_id, ...)
            generate_answer: Có sinh câu trả lời từ LLM không

        Returns:
            {
                "reranked_results": [...],
                "answer": "..." or None,
                "context_used": [...]
            }
        """
        if not search_results:
            return {
                "reranked_results": [],
                "answer": None,
                "context_used": []
            }

        # Extract contents for reranking
        documents = [r["content"] for r in search_results]

        # Rerank
        reranked = self.rerank(query, documents)

        # Lấy top K sau rerank
        top_reranked = reranked[:self.top_k_rerank]

        # Map lại với search results gốc để giữ metadata
        reranked_results = []
        for item in top_reranked:
            original = search_results[item["index"]]
            reranked_results.append({
                **original,
                "rerank_score": item["relevance_score"]
            })

        # Generate answer nếu cần
        answer = None
        context_used = [item["document"] for item in top_reranked]

        if generate_answer and self.use_local:
            answer = self.generate_answer(query, context_used)

        return {
            "reranked_results": reranked_results,
            "answer": answer,
            "context_used": context_used
        }

    def check_services_health(self) -> Dict[str, bool]:
        """Kiểm tra health của các services"""
        health = {
            "reranker": False,
            "llm": False
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                # Check reranker
                try:
                    r = client.get(f"{self.reranker_url}/health")
                    health["reranker"] = r.status_code == 200
                except:
                    pass

                # Check LLM
                try:
                    r = client.get(f"{self.ollama_url}/api/tags")
                    health["llm"] = r.status_code == 200
                except:
                    pass

        except Exception as e:
            logger.error(f"Health check error: {e}")

        return health


# Singleton instance
rag_service = RAGService()
