# MDMS - Magenest Document Management System

Hệ thống quản lý và tra cứu tài liệu nội bộ với các tính năng:
- **Semantic Search**: Tìm kiếm ngữ nghĩa trên toàn bộ tài liệu đã upload
- **Document Generation**: Tự động sinh tài liệu từ input của user (SRS, PRD, etc.)

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + TypeScript + Tailwind CSS
- **Database**: PostgreSQL
- **Vector Database**: Qdrant
- **LLM**: Google Gemini
- **Storage**: AWS S3 (or local for development)
- **Cache**: Redis

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional)
- PostgreSQL 15+
- Redis 7+
- Qdrant

## Quick Start with Docker

```bash
cd mdms
docker-compose up -d
```

This will start:
- Backend API at http://localhost:8000
- Frontend at http://localhost:3000
- PostgreSQL at localhost:5432
- Redis at localhost:6379
- Qdrant at localhost:6333

## Development Setup

### Backend

```bash
cd mdms/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run migrations (when database is ready)
# alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd mdms/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## API Documentation

After starting the backend, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Key Features

### 1. Document Upload & Management
- Support for PDF, Word (.doc, .docx), Excel (.xls, .xlsx), Markdown
- Automatic text extraction and indexing
- Version control
- Project and category organization

### 2. Semantic Search
- Natural language queries in Vietnamese and English
- AI-powered search using vector embeddings
- Highlighted results with relevant snippets
- Filters by project, category, date, file type

### 3. Document Generation
- SRS (IEEE 830 standard)
- PRD (Product Requirements Document)
- Technical Design Document
- Test Cases
- API Documentation
- Release Notes
- User Guide

### 4. User Management
- Role-based access control (Admin, Manager, Member, Viewer)
- Odoo SSO integration ready
- Project-based permissions

## Configuration

### Environment Variables

```env
# Application
APP_NAME=MDMS
DEBUG=True
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mdms

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Google Gemini
GEMINI_API_KEY=your-api-key

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=mdms-documents
```

## Project Structure

```
mdms/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # API routes
│   │   ├── core/               # Config, security, database
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   └── main.py             # FastAPI app
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── services/           # API services
│   │   ├── hooks/              # Custom hooks
│   │   └── styles/             # CSS/Tailwind
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml
```

## License

Internal use only - Magenest

admin@test.com 123456