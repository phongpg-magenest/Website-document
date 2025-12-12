"""
Review Service - Đánh giá tài liệu bằng AI (Gemini)
"""
import google.generativeai as genai
from typing import Optional, Dict, Any
import logging
import json
import asyncio
import time
import re

from app.core.config import settings
from app.schemas.review import (
    ReviewResult,
    ReviewCategories,
    SpellingGrammarCategory,
    StructureCategory,
    CompletenessCategory,
    ContentQualityCategory,
    RiskDetectionCategory,
    TemplateComparison,
    ReviewIssue,
    ReviewRisk,
    SeverityLevel,
)

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2


class ReviewService:
    def __init__(self):
        self.model_name = "gemini-2.0-flash"

        # Config cho review - cần output dài và chính xác
        self.generation_config = genai.GenerationConfig(
            max_output_tokens=16384,  # Tăng để có báo cáo đầy đủ
            temperature=0.3,  # Thấp để chính xác hơn
        )

        # Configure Gemini
        if settings.GEMINI_BASE_URL:
            genai.configure(
                api_key=settings.GEMINI_API_KEY,
                transport="rest",
                client_options={"api_endpoint": settings.GEMINI_BASE_URL}
            )
            logger.info(f"ReviewService: Using Gemini proxy: {settings.GEMINI_BASE_URL}")
        else:
            genai.configure(api_key=settings.GEMINI_API_KEY)

        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config=self.generation_config
        )

    def _build_review_prompt(
        self,
        document_content: str,
        document_name: str,
        document_type: Optional[str] = None,
        template_content: Optional[str] = None,
        template_name: Optional[str] = None,
    ) -> str:
        """Xây dựng prompt cho việc review tài liệu"""

        template_section = ""
        if template_content:
            template_section = f"""
## TEMPLATE CHUẨN ĐỂ SO SÁNH:
Tên template: {template_name or 'Template chuẩn'}

{template_content}

Hãy so sánh tài liệu với template trên để đánh giá tính đầy đủ.
"""
        else:
            template_section = """
## LƯU Ý: Không có template chuẩn để so sánh.
Bỏ qua phần so sánh template, chỉ đánh giá dựa trên cấu trúc chung của loại tài liệu này.
"""

        prompt = f"""Bạn là chuyên gia review tài liệu chuyên nghiệp. Hãy đánh giá tài liệu sau một cách CHI TIẾT và TOÀN DIỆN.

## THÔNG TIN TÀI LIỆU:
- Tên file: {document_name}
- Loại tài liệu: {document_type or 'Không xác định'}

## NỘI DUNG TÀI LIỆU CẦN REVIEW:
{document_content}

{template_section}

## YÊU CẦU ĐÁNH GIÁ:

Đánh giá tài liệu theo 5 tiêu chí sau, mỗi tiêu chí cho điểm từ 0-10:

### 1. CHÍNH TẢ & NGỮ PHÁP (spelling_grammar)
- Kiểm tra lỗi chính tả tiếng Việt và tiếng Anh
- Kiểm tra lỗi ngữ pháp, câu cú
- Kiểm tra dấu câu, viết hoa
- Liệt kê CỤ THỂ từng lỗi với vị trí

### 2. CẤU TRÚC & BỐ CỤC (structure)
- Đánh giá cách tổ chức nội dung
- Kiểm tra đánh số heading, mục lục
- Đánh giá tính logic trong sắp xếp
- Kiểm tra format, căn lề, font chữ (nếu có thể nhận biết)

### 3. TÍNH ĐẦY ĐỦ (completeness)
- So sánh với template (nếu có)
- Liệt kê các mục BẮT BUỘC bị thiếu
- Đánh giá độ chi tiết của nội dung
- Kiểm tra các phần quan trọng có đầy đủ không

### 4. CHẤT LƯỢNG NỘI DUNG (content_quality)
- Đánh giá tính logic, mạch lạc
- Kiểm tra mâu thuẫn trong nội dung
- Đánh giá độ rõ ràng, dễ hiểu
- Kiểm tra thông tin có chính xác, cập nhật không

### 5. PHÁT HIỆN RỦI RO (risk_detection)
- Với hợp đồng: điều khoản bất lợi, thiếu điều khoản bảo vệ
- Với tài liệu kỹ thuật: rủi ro bảo mật, hiệu năng
- Với đề xuất: rủi ro dự án, ngân sách
- Liệt kê CỤ THỂ từng rủi ro với mức độ nghiêm trọng

## OUTPUT FORMAT (BẮT BUỘC trả về JSON hợp lệ):

```json
{{
  "overall_score": 8.5,
  "summary": "Tóm tắt đánh giá tổng quan trong 2-3 câu",

  "categories": {{
    "spelling_grammar": {{
      "score": 9,
      "label": "Chính tả & Ngữ pháp",
      "issues": [
        {{
          "location": "Trang 2, đoạn 3",
          "issue": "Lỗi chính tả: 'kiêm tra' → 'kiểm tra'",
          "suggestion": "Sửa thành 'kiểm tra'",
          "severity": "low"
        }}
      ]
    }},
    "structure": {{
      "score": 8,
      "label": "Cấu trúc & Bố cục",
      "issues": [
        {{
          "location": "Mục 3",
          "issue": "Thiếu đánh số heading cấp 3",
          "suggestion": "Thêm đánh số 3.1, 3.2...",
          "severity": "medium"
        }}
      ]
    }},
    "completeness": {{
      "score": 7,
      "label": "Tính đầy đủ",
      "missing_sections": ["Phụ lục A", "Danh mục từ viết tắt"],
      "issues": [
        {{
          "location": "Toàn tài liệu",
          "issue": "Thiếu mục Phụ lục theo template",
          "suggestion": "Bổ sung Phụ lục A theo template chuẩn",
          "severity": "medium"
        }}
      ]
    }},
    "content_quality": {{
      "score": 8,
      "label": "Chất lượng nội dung",
      "issues": [
        {{
          "location": "Mục 2.3",
          "issue": "Nội dung chưa rõ ràng, cần giải thích thêm",
          "suggestion": "Bổ sung ví dụ minh họa",
          "severity": "low"
        }}
      ]
    }},
    "risk_detection": {{
      "score": 8,
      "label": "Phát hiện rủi ro",
      "risks": [
        {{
          "location": "Điều 5.2",
          "risk": "Điều khoản phạt vi phạm chưa quy định rõ mức phạt",
          "impact": "Có thể gây tranh chấp khi xảy ra vi phạm",
          "severity": "high"
        }}
      ]
    }}
  }},

  "recommendations": [
    "Khuyến nghị cải thiện 1",
    "Khuyến nghị cải thiện 2",
    "Khuyến nghị cải thiện 3"
  ],

  "template_comparison": {{
    "template_name": "{template_name or 'Không có template'}",
    "matched_sections": ["Mục 1", "Mục 2"],
    "missing_sections": ["Phụ lục A"],
    "extra_sections": ["Mục bổ sung"]
  }}
}}
```

## LƯU Ý QUAN TRỌNG:
1. CHỈ trả về JSON, không có text khác
2. Đảm bảo JSON hợp lệ, đúng format
3. severity chỉ có 4 giá trị: "low", "medium", "high", "critical"
4. Điểm số từ 0-10, có thể có số thập phân (VD: 7.5)
5. Nếu không có template, set template_comparison = null
6. Liệt kê TẤT CẢ các vấn đề phát hiện được, không bỏ sót
7. Recommendations phải cụ thể, actionable

Bắt đầu review và trả về JSON:"""

        return prompt

    def _parse_review_response(
        self,
        response_text: str,
        document_name: str,
        document_type: Optional[str],
        review_time: float,
        template_id: Optional[str] = None,
    ) -> ReviewResult:
        """Parse response từ Gemini thành ReviewResult"""

        # Tìm và extract JSON từ response
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Thử parse trực tiếp nếu không có markdown code block
            json_str = response_text.strip()
            # Loại bỏ các ký tự không phải JSON ở đầu/cuối
            if not json_str.startswith('{'):
                start = json_str.find('{')
                if start != -1:
                    json_str = json_str[start:]
            if not json_str.endswith('}'):
                end = json_str.rfind('}')
                if end != -1:
                    json_str = json_str[:end+1]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Response text: {response_text[:1000]}...")
            # Trả về kết quả mặc định nếu parse lỗi
            return self._get_default_result(document_name, document_type, review_time)

        # Parse categories
        categories_data = data.get("categories", {})

        # Spelling & Grammar
        sg_data = categories_data.get("spelling_grammar", {})
        spelling_grammar = SpellingGrammarCategory(
            score=sg_data.get("score", 5),
            label=sg_data.get("label", "Chính tả & Ngữ pháp"),
            issues=[
                ReviewIssue(
                    location=i.get("location", ""),
                    issue=i.get("issue", ""),
                    suggestion=i.get("suggestion"),
                    severity=SeverityLevel(i.get("severity", "medium"))
                )
                for i in sg_data.get("issues", [])
            ]
        )

        # Structure
        st_data = categories_data.get("structure", {})
        structure = StructureCategory(
            score=st_data.get("score", 5),
            label=st_data.get("label", "Cấu trúc & Bố cục"),
            issues=[
                ReviewIssue(
                    location=i.get("location", ""),
                    issue=i.get("issue", ""),
                    suggestion=i.get("suggestion"),
                    severity=SeverityLevel(i.get("severity", "medium"))
                )
                for i in st_data.get("issues", [])
            ]
        )

        # Completeness
        cp_data = categories_data.get("completeness", {})
        completeness = CompletenessCategory(
            score=cp_data.get("score", 5),
            label=cp_data.get("label", "Tính đầy đủ"),
            missing_sections=cp_data.get("missing_sections", []),
            issues=[
                ReviewIssue(
                    location=i.get("location", ""),
                    issue=i.get("issue", ""),
                    suggestion=i.get("suggestion"),
                    severity=SeverityLevel(i.get("severity", "medium"))
                )
                for i in cp_data.get("issues", [])
            ]
        )

        # Content Quality
        cq_data = categories_data.get("content_quality", {})
        content_quality = ContentQualityCategory(
            score=cq_data.get("score", 5),
            label=cq_data.get("label", "Chất lượng nội dung"),
            issues=[
                ReviewIssue(
                    location=i.get("location", ""),
                    issue=i.get("issue", ""),
                    suggestion=i.get("suggestion"),
                    severity=SeverityLevel(i.get("severity", "medium"))
                )
                for i in cq_data.get("issues", [])
            ]
        )

        # Risk Detection
        rd_data = categories_data.get("risk_detection", {})
        risk_detection = RiskDetectionCategory(
            score=rd_data.get("score", 5),
            label=rd_data.get("label", "Phát hiện rủi ro"),
            risks=[
                ReviewRisk(
                    location=r.get("location", ""),
                    risk=r.get("risk", ""),
                    impact=r.get("impact", ""),
                    severity=SeverityLevel(r.get("severity", "medium"))
                )
                for r in rd_data.get("risks", [])
            ]
        )

        categories = ReviewCategories(
            spelling_grammar=spelling_grammar,
            structure=structure,
            completeness=completeness,
            content_quality=content_quality,
            risk_detection=risk_detection,
        )

        # Template comparison
        template_comparison = None
        tc_data = data.get("template_comparison")
        if tc_data and tc_data.get("template_name") != "Không có template":
            template_comparison = TemplateComparison(
                template_name=tc_data.get("template_name", ""),
                template_id=template_id,
                matched_sections=tc_data.get("matched_sections", []),
                missing_sections=tc_data.get("missing_sections", []),
                extra_sections=tc_data.get("extra_sections", []),
            )

        return ReviewResult(
            overall_score=data.get("overall_score", 5),
            summary=data.get("summary", "Không có tóm tắt"),
            document_name=document_name,
            document_type=document_type,
            review_time_seconds=review_time,
            categories=categories,
            recommendations=data.get("recommendations", []),
            template_comparison=template_comparison,
        )

    def _get_default_result(
        self,
        document_name: str,
        document_type: Optional[str],
        review_time: float,
    ) -> ReviewResult:
        """Trả về kết quả mặc định khi có lỗi"""
        return ReviewResult(
            overall_score=5.0,
            summary="Không thể phân tích tài liệu. Vui lòng thử lại.",
            document_name=document_name,
            document_type=document_type,
            review_time_seconds=review_time,
            categories=ReviewCategories(
                spelling_grammar=SpellingGrammarCategory(
                    score=5, label="Chính tả & Ngữ pháp", issues=[]
                ),
                structure=StructureCategory(
                    score=5, label="Cấu trúc & Bố cục", issues=[]
                ),
                completeness=CompletenessCategory(
                    score=5, label="Tính đầy đủ", missing_sections=[], issues=[]
                ),
                content_quality=ContentQualityCategory(
                    score=5, label="Chất lượng nội dung", issues=[]
                ),
                risk_detection=RiskDetectionCategory(
                    score=5, label="Phát hiện rủi ro", risks=[]
                ),
            ),
            recommendations=["Vui lòng thử review lại tài liệu"],
            template_comparison=None,
        )

    async def review_document(
        self,
        document_content: str,
        document_name: str,
        document_type: Optional[str] = None,
        template_content: Optional[str] = None,
        template_name: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> ReviewResult:
        """
        Review tài liệu bằng Gemini AI

        Args:
            document_content: Nội dung text của tài liệu
            document_name: Tên file tài liệu
            document_type: Loại tài liệu (srs, prd, contract...)
            template_content: Nội dung template chuẩn (nếu có)
            template_name: Tên template
            template_id: ID của template

        Returns:
            ReviewResult với đánh giá chi tiết
        """
        start_time = time.time()

        # Build prompt
        prompt = self._build_review_prompt(
            document_content=document_content,
            document_name=document_name,
            document_type=document_type,
            template_content=template_content,
            template_name=template_name,
        )

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Review attempt {attempt + 1}/{MAX_RETRIES} for {document_name}")

                response = await asyncio.to_thread(
                    self.model.generate_content, prompt
                )

                review_time = time.time() - start_time
                logger.info(f"Review completed in {review_time:.2f}s")

                result = self._parse_review_response(
                    response_text=response.text,
                    document_name=document_name,
                    document_type=document_type,
                    review_time=review_time,
                    template_id=template_id,
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Review attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        review_time = time.time() - start_time
        logger.error(f"Review failed after {MAX_RETRIES} attempts: {last_error}")

        return self._get_default_result(document_name, document_type, review_time)


# Singleton instance
review_service = ReviewService()
