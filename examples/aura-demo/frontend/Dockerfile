# syntax=docker/dockerfile:1
# ASSURE aura-demo frontend — Next.js 14 production build.
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first for layer caching.
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build.
COPY frontend /app

# Point server-side fetches to the backend service inside Docker.
ENV API_URL=http://backend:8000
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---- production runner ----
FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Standalone output keeps only what is needed to run.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Non-root runtime user.
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3000/', (r) => r.statusCode === 200 ? process.exit(0) : process.exit(1)).on('error', () => process.exit(1))" || exit 1

CMD ["node", "server.js"]
