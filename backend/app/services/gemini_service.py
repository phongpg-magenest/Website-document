import google.generativeai as genai
from typing import List, Optional, Dict, Any
import logging
import json
import asyncio

from app.core.config import settings
from app.schemas.generate import DocumentType, OutputLanguage

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds

# Document templates
TEMPLATES = {
    DocumentType.SRS: {
        "name": "Software Requirements Specification",
        "standard": "IEEE 830",
        "structure": """
# Software Requirements Specification (SRS)
## According to IEEE 830 Standard

### 1. Introduction
#### 1.1 Purpose
#### 1.2 Scope
#### 1.3 Definitions, Acronyms, and Abbreviations
#### 1.4 References
#### 1.5 Overview

### 2. Overall Description
#### 2.1 Product Perspective
#### 2.2 Product Features
#### 2.3 User Classes and Characteristics
#### 2.4 Operating Environment
#### 2.5 Design and Implementation Constraints
#### 2.6 Assumptions and Dependencies

### 3. Specific Requirements
#### 3.1 External Interface Requirements
##### 3.1.1 User Interfaces
##### 3.1.2 Hardware Interfaces
##### 3.1.3 Software Interfaces
##### 3.1.4 Communication Interfaces
#### 3.2 Functional Requirements
#### 3.3 Non-Functional Requirements
##### 3.3.1 Performance Requirements
##### 3.3.2 Security Requirements
##### 3.3.3 Quality Attributes

### 4. Appendices
""",
    },
    DocumentType.PRD: {
        "name": "Product Requirements Document",
        "standard": "Custom",
        "structure": """
# Product Requirements Document (PRD)

### 1. Executive Summary

### 2. Problem Statement

### 3. Goals and Objectives

### 4. User Personas

### 5. User Stories and Use Cases

### 6. Features and Requirements
#### 6.1 Must Have (P0)
#### 6.2 Should Have (P1)
#### 6.3 Nice to Have (P2)

### 7. Success Metrics

### 8. Technical Considerations

### 9. Timeline and Milestones

### 10. Risks and Mitigations

### 11. Open Questions
""",
    },
    DocumentType.TECHNICAL_DESIGN: {
        "name": "Technical Design Document",
        "standard": "Custom",
        "structure": """
# Technical Design Document

### 1. Overview

### 2. Goals and Non-Goals

### 3. Background and Context

### 4. Proposed Solution
#### 4.1 High-Level Architecture
#### 4.2 Detailed Design
#### 4.3 Data Models
#### 4.4 API Design

### 5. Alternatives Considered

### 6. Security Considerations

### 7. Testing Strategy

### 8. Deployment Plan

### 9. Monitoring and Observability

### 10. Dependencies

### 11. Timeline
""",
    },
    DocumentType.TEST_CASES: {
        "name": "Test Cases Document",
        "standard": "Custom",
        "structure": """
# Test Cases Document

### 1. Test Plan Overview

### 2. Test Scope

### 3. Test Environment

### 4. Test Cases
| Test ID | Description | Pre-conditions | Steps | Expected Result | Status |
|---------|-------------|----------------|-------|-----------------|--------|

### 5. Smoke Test Cases

### 6. Integration Test Cases

### 7. Regression Test Cases

### 8. Edge Cases

### 9. Test Data Requirements
""",
    },
    DocumentType.API_DOCUMENTATION: {
        "name": "API Documentation",
        "standard": "OpenAPI/Custom",
        "structure": """
# API Documentation

### 1. Overview

### 2. Authentication

### 3. Base URL

### 4. Endpoints
#### 4.1 [Resource Name]
- **GET** `/endpoint` - Description
- **POST** `/endpoint` - Description
- **PUT** `/endpoint/:id` - Description
- **DELETE** `/endpoint/:id` - Description

### 5. Request/Response Formats

### 6. Error Codes

### 7. Rate Limiting

### 8. Examples
""",
    },
    DocumentType.RELEASE_NOTES: {
        "name": "Release Notes",
        "standard": "Custom",
        "structure": """
# Release Notes

## Version X.X.X
**Release Date:** YYYY-MM-DD

### New Features

### Improvements

### Bug Fixes

### Breaking Changes

### Known Issues

### Migration Guide

### Contributors
""",
    },
    DocumentType.USER_GUIDE: {
        "name": "User Guide",
        "standard": "Custom",
        "structure": """
# User Guide

### 1. Introduction

### 2. Getting Started
#### 2.1 System Requirements
#### 2.2 Installation
#### 2.3 Quick Start

### 3. Features
#### 3.1 Feature A
#### 3.2 Feature B

### 4. How-To Guides

### 5. Troubleshooting

### 6. FAQ

### 7. Support and Contact
""",
    },
}


class GeminiService:
    def __init__(self):
        self.model_name = "gemini-2.0-flash"
        self.generation_config = genai.GenerationConfig(
            max_output_tokens=8192,
            temperature=0.7,
        )

        # Configure with custom base URL if provided (for proxy with auto key rotation)
        if settings.GEMINI_BASE_URL:
            genai.configure(
                api_key=settings.GEMINI_API_KEY,
                transport="rest",
                client_options={"api_endpoint": settings.GEMINI_BASE_URL}
            )
            logger.info(f"Using Gemini proxy: {settings.GEMINI_BASE_URL}")
        else:
            genai.configure(api_key=settings.GEMINI_API_KEY)

        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config=self.generation_config
        )

    async def generate_document(
        self,
        document_type: DocumentType,
        reference_content: str,
        context: Optional[str] = None,
        language: OutputLanguage = OutputLanguage.VIETNAMESE,
        custom_template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate document using Gemini based on reference content"""
        template = TEMPLATES.get(document_type)
        if not template:
            raise ValueError(f"Unknown document type: {document_type}")

        language_instruction = (
            "Please write the document in Vietnamese."
            if language == OutputLanguage.VIETNAMESE
            else "Please write the document in English."
        )

        # Use custom template if provided, otherwise use default
        if custom_template:
            template_structure = custom_template
            template_info = f"Use the EXACT format and structure from the provided template below"
        else:
            template_structure = template['structure']
            template_info = f"following the {template['standard']} standard"

        prompt = f"""
You are a professional technical writer. Based on the following reference materials,
generate a complete {template['name']} document {template_info}.

{language_instruction}

## Reference Materials (Input data to extract information from):
{reference_content}

{f"## Additional Context: {context}" if context else ""}

## TEMPLATE FORMAT TO FOLLOW (Generate document using this EXACT structure):
{template_structure}

## CRITICAL Instructions:
1. **FOLLOW THE TEMPLATE EXACTLY**: Use the same headings, sections, numbering, and format as the template
2. Carefully analyze ALL reference materials to extract ALL relevant information
3. Fill in EVERY section of the template with comprehensive and detailed content
4. IMPORTANT: Generate a COMPLETE document - do not truncate or summarize
5. Include ALL specific details, use cases, requirements from the reference materials
6. If information for a section is not available, note it as "To be determined" or "N/A"
7. Maintain the same professional writing style as the template
8. The document should be thorough and cover all aspects mentioned in the reference materials
9. Do NOT stop mid-sentence or mid-section - complete the entire document
10. Keep the same formatting conventions (headers, lists, tables) as the template

## TABLE FORMATTING REQUIREMENTS (VERY IMPORTANT):
- **USE MARKDOWN TABLES** for all structured information to make the document professional and readable
- For Use Cases, create a table with columns: | Mục | Nội dung |
- For each Use Case, include a well-formatted table like this:

| Mục | Nội dung |
|-----|----------|
| **Mã Use Case** | UC-001 |
| **Tên Use Case** | Tên của use case |
| **Mô tả** | Mô tả chi tiết |
| **Tác nhân** | Người dùng, Admin, etc. |
| **Tiền điều kiện** | Các điều kiện cần có trước |
| **Hậu điều kiện** | Kết quả sau khi thực hiện |
| **Luồng sự kiện chính** | 1. Bước 1<br>2. Bước 2<br>3. Bước 3 |
| **Luồng thay thế** | Các trường hợp ngoại lệ |
| **Yêu cầu đặc biệt** | Các yêu cầu bổ sung |

- For Requirements lists, use tables like: | ID | Yêu cầu | Mô tả | Độ ưu tiên |
- For Actor lists, use tables like: | STT | Tác nhân | Mô tả | Quyền hạn |
- For Terminology, use tables like: | Thuật ngữ | Định nghĩa |
- For Change History, use tables like: | Version | Ngày | Người thực hiện | Mô tả thay đổi |
- ALWAYS use proper Markdown table syntax with | and --- separators
- Tables make documents look professional and easier to read

Please generate the COMPLETE document with professional tables following the template structure above:
"""

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Gemini generation attempt {attempt + 1}/{MAX_RETRIES}")
                response = await asyncio.to_thread(
                    self.model.generate_content, prompt
                )
                generated_text = response.text
                logger.info("Gemini generation completed successfully")

                return {
                    "title": f"{template['name']} - Generated",
                    "content": generated_text,
                    "document_type": document_type,
                    "template_used": template["name"],
                }
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini generation attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        logger.error(f"Gemini generation failed after {MAX_RETRIES} attempts: {last_error}")
        raise last_error

    async def summarize_text(self, text: str, max_length: int = 500) -> str:
        """Summarize text using Gemini"""
        prompt = f"""
Please summarize the following text in about {max_length} characters.
Keep the key points and main ideas. Write in the same language as the input.

Text:
{text}

Summary:
"""
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini summarization error: {e}")
            return text[:max_length] + "..."

    async def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text using Gemini"""
        prompt = f"""
Extract the {max_keywords} most important keywords or phrases from the following text.
Return only the keywords, one per line.

Text:
{text}

Keywords:
"""
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, prompt
            )
            keywords = [
                kw.strip().strip("-").strip("*").strip()
                for kw in response.text.strip().split("\n")
                if kw.strip()
            ]
            return keywords[:max_keywords]
        except Exception as e:
            logger.error(f"Gemini keyword extraction error: {e}")
            return []

    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Get list of available document templates"""
        return [
            {
                "document_type": doc_type,
                "name": template["name"],
                "standard": template["standard"],
            }
            for doc_type, template in TEMPLATES.items()
        ]


# Singleton instance
gemini_service = GeminiService()
