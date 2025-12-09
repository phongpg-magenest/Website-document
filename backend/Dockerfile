# ============================================
# STAGE 1: Builder - Cài đặt dependencies
# ============================================
# Dùng python:3.12-slim thay vì python:3.12 để giảm ~850MB
# AS builder: Đặt tên stage để reference sau
FROM python:3.12-slim AS builder

WORKDIR /app

# Cài build tools CẦN THIẾT để compile các package như psycopg2, numpy
# --no-install-recommends: Không cài packages phụ -> giảm dung lượng
# rm -rf /var/lib/apt/lists/*: Xóa cache apt -> giảm thêm ~50MB
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài uv - package manager siêu nhanh (10-100x nhanh hơn pip)
# uv được viết bằng Rust, tối ưu cho tốc độ
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Tạo virtual environment riêng biệt
# Lý do: Dễ copy toàn bộ venv sang stage 2
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements TRƯỚC code
# Lý do: Docker cache layer - nếu requirements không đổi,
# Docker sẽ dùng cache, không cần install lại
COPY requirements.txt .

# Dùng uv thay pip - nhanh hơn rất nhiều!
# --no-cache: Không lưu cache -> giảm dung lượng image
# --system: Cài vào system/venv thay vì tạo venv mới
RUN uv pip install --no-cache -r requirements.txt


# ============================================
# STAGE 2: Production - Image chạy thực tế
# ============================================
# Bắt đầu từ image sạch, KHÔNG có build tools
FROM python:3.12-slim AS production

WORKDIR /app

# Chỉ cài RUNTIME dependencies (không cần gcc, make...)
# libpq5: Runtime library cho PostgreSQL (psycopg2 cần)
# libmagic1: Để detect file types
# fonts-dejavu-core: Font cho PDF tiếng Việt
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# QUAN TRỌNG: Copy virtual environment từ builder stage
# Chỉ copy kết quả đã compile, KHÔNG copy build tools
# Đây là lý do chính giúp giảm dung lượng
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Cấu hình Python cho production
# PYTHONDONTWRITEBYTECODE=1: Không tạo file .pyc -> giảm dung lượng
# PYTHONUNBUFFERED=1: Log realtime, không buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Tạo user không phải root -> Bảo mật
# Không chạy container với root để tránh bị exploit
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Copy code ứng dụng
# --chown: Đặt quyền sở hữu cho appuser
COPY --chown=appuser:appuser . .

EXPOSE 8000

# Health check để container orchestrator biết app còn sống
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Chạy với uvicorn
# --workers 2: Chạy 2 process để handle nhiều request hơn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
