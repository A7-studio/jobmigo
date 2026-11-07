# Production image: build with all dependencies, run on plain Node as a non-root user.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
# The migration runner needs only drizzle-orm and pg. Install the exact versions the
# lockfile resolved (read from the full install above), not a fresh semver range.
RUN mkdir /migrate && cd /migrate && npm init -y >/dev/null \
 && npm install --omit=dev --no-audit --no-fund \
    "drizzle-orm@$(node -p "require('/app/node_modules/drizzle-orm/package.json').version")" \
    "pg@$(node -p "require('/app/node_modules/pg/package.json').version")"

FROM node:22-slim
ENV NODE_ENV=production PORT=3000
WORKDIR /app
COPY --from=build /app/.output ./.output
COPY --from=build /app/drizzle ./drizzle
COPY --from=build /migrate/node_modules ./migrate/node_modules
COPY scripts/migrate.mjs ./migrate/migrate.mjs
COPY docker-entrypoint.sh ./docker-entrypoint.sh
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/readyz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["./docker-entrypoint.sh"]
