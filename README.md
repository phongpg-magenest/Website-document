# MDMS - Magenest Document Management System

Hệ thống quản lý và tra cứu tài liệu nội bộ với các tính năng:
- **Semantic Search**: Tìm kiếm ngữ nghĩa trên toàn bộ tài liệu đã upload
- **Document Generation**: Tự động sinh tài liệu từ input của user (SRS, PRD, etc.)
- **Version Control**: Quản lý phiên bản tài liệu
- **Approval Workflow**: Quy trình phê duyệt tài liệu
- **Collaboration**: Bình luận và cộng tác trên tài liệu
- **Prompt Manager**: Quản lý prompt templates cho AI
- **Analytics Dashboard**: Thống kê và báo cáo
- **Audit Trail**: Theo dõi lịch sử hoạt động
- **Notifications**: Hệ thống thông báo realtime

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Database**: PostgreSQL với pgvector extension
- **LLM**: Google Gemini
- **Storage**: Local filesystem (or AWS S3)
- **Cache**: Redis (optional)

## Quick Start

### 1. Backend (port 8002)

```bash
cd mdms/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8002
```

### 2. Frontend (port 3000)

```bash
cd mdms/frontend
npm run dev
```

### 3. Access

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8002/docs
- **Login**: `testadmin@mdms.local` / `admin123`

## Features

### Core Features
| Feature | Description | Status |
|---------|-------------|--------|
| Document Upload | Upload PDF, DOCX, MD files | ✅ |
| Semantic Search | AI-powered search với pgvector | ✅ |
| Document Generation | Generate SRS, PRD, API docs | ✅ |
| Projects | Organize documents by project | ✅ |
| Templates | DOCX templates for export | ✅ |

### Advanced Features (New)
| Feature | Description | Status |
|---------|-------------|--------|
| Version Control | Track document versions, compare, restore | ✅ |
| Approval Workflow | Submit for review, approve/reject | ✅ |
| Collaboration | Comments, mentions, replies | ✅ |
| Prompt Manager | CRUD prompt templates, test, versioning | ✅ |
| Analytics Dashboard | Document stats, storage, activity | ✅ |
| Notifications | Bell icon, mark read, real-time | ✅ |
| Audit Trail | Track all user actions, filters | ✅ |

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/register` - Register
- `GET /api/v1/auth/me` - Current user

### Documents
- `GET /api/v1/documents` - List documents
- `POST /api/v1/documents` - Upload document
- `GET /api/v1/documents/{id}` - Get document
- `GET /api/v1/documents/{id}/versions` - Get versions
- `POST /api/v1/documents/{id}/versions/{version_id}/restore` - Restore version

### Approval Workflow
- `POST /api/v1/documents/{id}/submit-for-approval` - Submit for review
- `POST /api/v1/documents/{id}/approve` - Approve
- `POST /api/v1/documents/{id}/reject` - Reject
- `GET /api/v1/documents/pending-approvals` - List pending

### Comments
- `GET /api/v1/documents/{id}/comments` - List comments
- `POST /api/v1/documents/{id}/comments` - Add comment
- `POST /api/v1/comments/{id}/reply` - Reply to comment

### Prompts
- `GET /api/v1/prompts` - List prompts
- `POST /api/v1/prompts` - Create prompt
- `GET /api/v1/prompts/{id}` - Get prompt
- `PUT /api/v1/prompts/{id}` - Update prompt
- `DELETE /api/v1/prompts/{id}` - Delete prompt
- `GET /api/v1/prompts/{id}/versions` - Get versions
- `POST /api/v1/prompts/test` - Test prompt

### Analytics
- `GET /api/v1/analytics/summary` - Dashboard summary

### Notifications
- `GET /api/v1/notifications` - List notifications
- `GET /api/v1/notifications/unread-count` - Unread count
- `POST /api/v1/notifications/{id}/read` - Mark as read
- `POST /api/v1/notifications/read-all` - Mark all read

### Audit
- `GET /api/v1/audit` - List audit logs
- `GET /api/v1/audit/summary` - Audit summary
- `GET /api/v1/audit/my-activity` - My activity
- `GET /api/v1/audit/actions` - Available actions

## Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview, quick actions, recent docs |
| `/documents` | Documents | List, upload, manage documents |
| `/search` | Search | Semantic search |
| `/generate` | Generate | Generate documents with AI |
| `/templates` | Templates | Manage DOCX templates |
| `/projects` | Projects | Manage projects |
| `/analytics` | Analytics | Charts, stats, storage info |
| `/prompts` | Prompt Manager | CRUD AI prompts |
| `/audit` | Audit Trail | Activity logs |

## Project Structure

```
mdms/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── search.py
│   │   │   ├── generate.py
│   │   │   ├── projects.py
│   │   │   ├── templates.py
│   │   │   ├── prompts.py          # NEW
│   │   │   ├── analytics.py        # NEW
│   │   │   ├── notifications.py    # NEW
│   │   │   └── audit.py            # NEW
│   │   ├── models/
│   │   │   ├── document.py
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── prompt_template.py  # NEW
│   │   │   ├── notification.py     # NEW
│   │   │   └── audit.py            # NEW
│   │   ├── services/
│   │   │   ├── document_service.py
│   │   │   ├── search_service.py
│   │   │   ├── generate_service.py
│   │   │   ├── prompt_service.py   # NEW
│   │   │   ├── analytics_service.py # NEW
│   │   │   ├── notification_service.py # NEW
│   │   │   └── audit_service.py    # NEW
│   │   └── schemas/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Layout.tsx
│   │   │   └── NotificationBell.tsx # NEW
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Documents.tsx
│   │   │   ├── Search.tsx
│   │   │   ├── Generate.tsx
│   │   │   ├── Analytics.tsx       # NEW
│   │   │   ├── PromptManager.tsx   # NEW
│   │   │   └── AuditTrail.tsx      # NEW
│   │   └── services/
│   │       └── api.ts              # Updated with new APIs
│   └── package.json
└── README.md
```

## Environment Variables

```env
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mdms
GEMINI_API_KEY=your-gemini-api-key
SECRET_KEY=your-secret-key
UPLOAD_DIR=./uploads

# Frontend (.env or vite.config.ts)
VITE_API_URL=/api/v1
```

## Database

PostgreSQL với pgvector extension cho semantic search:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## License

Internal use only - Magenest
