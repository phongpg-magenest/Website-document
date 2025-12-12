# ============================================
# STAGE 1: Build - Compile TypeScript & Bundle
# ============================================
# Dùng node:20-alpine làm base để build
# Alpine = ~5MB, node:20 full = ~1GB
# LƯU Ý: Chỉ dùng alpine cho build, KHÔNG chạy production với node
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package.json VÀ package-lock.json (nếu có)
# Lý do: Docker cache layer
# Nếu 2 file này không đổi -> npm install sẽ dùng cache
COPY package.json package-lock.json* ./

# npm ci thay vì npm install:
# - ci = Clean Install, nhanh hơn vì không check updates
# - Xóa node_modules cũ nếu có
# - Cài ĐÚNG version trong lock file (reproducible builds)
# --ignore-scripts: Bỏ qua postinstall scripts (bảo mật + nhanh hơn)
RUN npm ci --ignore-scripts

# Copy source code SAU khi install dependencies
# Lý do: Nếu chỉ sửa code (không sửa package.json),
# Docker dùng cache của npm ci -> build nhanh hơn nhiều
COPY . .

# Build arguments cho Vite
# Railway sẽ truyền VITE_API_URL vào lúc build
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build production bundle
# Kết quả: folder /app/dist chứa static files (HTML, JS, CSS)
# Vite tự động minify, tree-shake, code-split
RUN npm run build


# ============================================
# STAGE 2: Production - Serve với Nginx
# ============================================
# QUAN TRỌNG: Dùng nginx:alpine thay vì node để serve static files
#
# So sánh:
# - node:20-alpine + express/serve: ~180MB
# - nginx:alpine: ~25MB (nhỏ hơn 7 lần!)
#
# Nginx còn:
# - Nhanh hơn (được optimize cho static files)
# - Bảo mật hơn (battle-tested web server)
# - Ít tài nguyên hơn (không cần Node runtime)
FROM nginx:alpine AS production

# Copy file cấu hình nginx
# File này định nghĩa cách serve React SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static files từ builder stage
# Chỉ lấy folder dist (kết quả build), BỎ QUA:
# - node_modules (~500MB)
# - Source code TypeScript
# - Config files
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx chạy với user nginx (không phải root) theo mặc định
# Port 80 là standard cho HTTP

EXPOSE 80

# Health check
# curl được cài sẵn trong nginx:alpine
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# nginx -g "daemon off;": Chạy nginx ở foreground
# Cần thiết vì Docker cần process chạy foreground để giữ container alive
CMD ["nginx", "-g", "daemon off;"]
