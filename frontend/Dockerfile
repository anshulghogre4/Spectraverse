FROM node:20-alpine AS builder

WORKDIR /app

# Patch OS-level CVEs in alpine base
RUN apk upgrade --no-cache

# Receive build-time env (baked into the Next.js bundle)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Install deps first (layer-cache friendly)
COPY frontend/package*.json ./
# Use npm install (not ci) — no lock file committed yet
RUN npm install

# Copy source and build
COPY frontend/ .
RUN npm run build

# ── Production image ──────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

RUN apk upgrade --no-cache

ENV NODE_ENV=production

# Copy only what Next.js standalone output needs
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

CMD ["node", "server.js"]
