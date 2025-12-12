"""
Schemas cho tính năng Review tài liệu bằng AI
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class SeverityLevel(str, Enum):
    """Mức độ nghiêm trọng của vấn đề"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewIssue(BaseModel):
    """Một vấn đề được phát hiện trong tài liệu"""
    location: str = Field(..., description="Vị trí vấn đề (trang, đoạn, mục)")
    issue: str = Field(..., description="Mô tả vấn đề")
    suggestion: Optional[str] = Field(None, description="Gợi ý sửa")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)


class ReviewRisk(BaseModel):
    """Rủi ro được phát hiện (cho hợp đồng, văn bản pháp lý)"""
    location: str = Field(..., description="Vị trí rủi ro")
    risk: str = Field(..., description="Mô tả rủi ro")
    impact: str = Field(..., description="Tác động tiềm ẩn")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)


class CategoryScore(BaseModel):
    """Điểm và vấn đề của một hạng mục đánh giá"""
    score: float = Field(..., ge=0, le=10, description="Điểm từ 0-10")
    label: str = Field(..., description="Tên hạng mục")
    issues: List[ReviewIssue] = Field(default_factory=list)


class SpellingGrammarCategory(CategoryScore):
    """Hạng mục: Chính tả & Ngữ pháp"""
    pass


class StructureCategory(CategoryScore):
    """Hạng mục: Cấu trúc & Bố cục"""
    pass


class CompletenessCategory(CategoryScore):
    """Hạng mục: Tính đầy đủ"""
    missing_sections: List[str] = Field(default_factory=list, description="Các mục bị thiếu")


class ContentQualityCategory(CategoryScore):
    """Hạng mục: Chất lượng nội dung"""
    pass


class RiskDetectionCategory(BaseModel):
    """Hạng mục: Phát hiện rủi ro"""
    score: float = Field(..., ge=0, le=10)
    label: str = Field(default="Phát hiện rủi ro")
    risks: List[ReviewRisk] = Field(default_factory=list)


class ReviewCategories(BaseModel):
    """Tất cả các hạng mục đánh giá"""
    spelling_grammar: SpellingGrammarCategory = Field(
        ...,
        description="Đánh giá chính tả và ngữ pháp"
    )
    structure: StructureCategory = Field(
        ...,
        description="Đánh giá cấu trúc và bố cục"
    )
    completeness: CompletenessCategory = Field(
        ...,
        description="Đánh giá tính đầy đủ"
    )
    content_quality: ContentQualityCategory = Field(
        ...,
        description="Đánh giá chất lượng nội dung"
    )
    risk_detection: RiskDetectionCategory = Field(
        ...,
        description="Phát hiện rủi ro"
    )


class TemplateComparison(BaseModel):
    """Kết quả so sánh với template chuẩn"""
    template_name: str = Field(..., description="Tên template được sử dụng")
    template_id: Optional[UUID] = Field(None, description="ID template")
    matched_sections: List[str] = Field(default_factory=list, description="Các mục khớp với template")
    missing_sections: List[str] = Field(default_factory=list, description="Các mục thiếu so với template")
    extra_sections: List[str] = Field(default_factory=list, description="Các mục thừa so với template")


class ReviewResult(BaseModel):
    """Kết quả review tài liệu"""
    overall_score: float = Field(..., ge=0, le=10, description="Điểm tổng thể từ 0-10")
    summary: str = Field(..., description="Tóm tắt đánh giá")
    document_name: str = Field(..., description="Tên tài liệu được review")
    document_type: Optional[str] = Field(None, description="Loại tài liệu")
    review_time_seconds: float = Field(..., description="Thời gian review (giây)")

    categories: ReviewCategories = Field(..., description="Đánh giá theo từng hạng mục")
    recommendations: List[str] = Field(default_factory=list, description="Danh sách khuyến nghị cải thiện")
    template_comparison: Optional[TemplateComparison] = Field(
        None,
        description="So sánh với template (null nếu không có template)"
    )


class ReviewRequest(BaseModel):
    """Request body cho review (khi gửi JSON thay vì form-data)"""
    document_type: Optional[str] = Field(None, description="Loại tài liệu")
    template_id: Optional[UUID] = Field(None, description="ID template cụ thể (optional)")


class ExportFormat(str, Enum):
    """Định dạng export"""
    PDF = "pdf"
    DOCX = "docx"


class ExportRequest(BaseModel):
    """Request export báo cáo review"""
    review_result: ReviewResult = Field(..., description="Kết quả review cần export")
    format: ExportFormat = Field(..., description="Định dạng file (pdf/docx)")
    document_name: Optional[str] = Field(None, description="Tên file export")


class ReviewResponse(BaseModel):
    """Response wrapper cho API review"""
    success: bool = Field(default=True)
    data: ReviewResult
    message: Optional[str] = None
