# Frontend Dockerfile - Optimized for Production
# STAGE 1: Builder
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies first for caching
COPY package*.json ./
RUN npm ci

# Copy code and build
COPY . .
RUN npm run build

# STAGE 2: Runtime
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Copy only necessary artifacts from builder
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Note: standalone mode requires specific Next.js config
# If standalone is not enabled, we copy package.json and node_modules
# But standalone is best practice for Docker.

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Metadata
LABEL org.opencontainers.image.source="https://github.com/Aniket-a14/Ai_friend"
LABEL org.opencontainers.image.description="AI Friend Frontend - Real-time Voice Interface"
LABEL org.opencontainers.image.version="2.1.3"

CMD ["node", "server.js"]
