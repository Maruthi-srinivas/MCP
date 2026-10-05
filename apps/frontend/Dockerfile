FROM node:22.14.0-bookworm AS build
WORKDIR /app
COPY apps/frontend/package.json apps/frontend/tsconfig.json apps/frontend/vite.config.ts apps/frontend/index.html ./
COPY apps/frontend/src ./src
RUN npm install && npm run build

FROM nginx:1.27.4-alpine AS runtime
COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000

FROM mcr.microsoft.com/playwright:v1.49.1-jammy AS test
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY apps/frontend/package.json apps/frontend/playwright.config.ts ./
COPY apps/frontend/tests ./tests
COPY mcp-servers/analysis-mcp/tests/fixtures/service_app /opt/fixtures/service_app
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm install
CMD ["npx", "playwright", "test"]
