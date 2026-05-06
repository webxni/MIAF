# syntax=docker/dockerfile:1.7

# --- shared base -------------------------------------------------------------
FROM node:20-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /srv/web

# --- deps stage --------------------------------------------------------------
FROM base AS deps
COPY package.json ./
# No lockfile yet; npm install will generate node_modules.
# When apps/web/package-lock.json exists this should switch to `npm ci`.
RUN npm install --no-audit --no-fund

# --- dev stage ---------------------------------------------------------------
FROM base AS dev
RUN apk add --no-cache wget
COPY --from=deps --chown=node:node /srv/web/node_modules ./node_modules
COPY --chown=node:node . .
# Pre-create .next so the named-volume mount inherits node ownership
# (Docker copies image contents into an empty named volume on first start,
# preserving file ownership — only works if the dir exists in the image).
RUN mkdir -p /srv/web/.next && chown -R node:node /srv/web
EXPOSE 3000
USER node
CMD ["npm", "run", "dev"]

# --- builder stage -----------------------------------------------------------
FROM base AS builder
ENV NODE_ENV=production
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
RUN npm run build

# --- prod stage --------------------------------------------------------------
FROM node:20-alpine AS prod
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /srv/web

# Copy the standalone output produced by `output: "standalone"`
COPY --from=builder --chown=node:node /srv/web/public ./public
COPY --from=builder --chown=node:node /srv/web/.next/standalone ./
COPY --from=builder --chown=node:node /srv/web/.next/static ./.next/static

USER node
EXPOSE 3000
CMD ["node", "server.js"]
