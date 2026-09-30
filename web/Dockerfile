FROM node:22-alpine AS build

WORKDIR /app/web

COPY web/package.json web/package-lock.json web/.npmrc ./
# @capywitch/ui vem do GitHub Packages — exige auth mesmo sendo pacote
# público. Token via BuildKit secret (nunca fica no layer/imagem final).
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) && \
    npm config set //npm.pkg.github.com/:_authToken=$NPM_TOKEN && \
    npm ci

COPY web ./
# lib/rules/game-changers.ts lê backend/mtg_analyzer/rules/commander/*.yaml via
# process.cwd()/../backend/... — precisa estar presente tanto no build (páginas
# estáticas) quanto no runtime (a "/" é dinâmica e chama getGameChangerNames()
# a cada request).
COPY backend/mtg_analyzer/rules/commander /app/backend/mtg_analyzer/rules/commander

RUN npm run build

FROM node:22-alpine AS run

WORKDIR /app/web
ENV NODE_ENV=production

COPY --from=build /app/web/package.json /app/web/package-lock.json /app/web/.npmrc ./
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) && \
    npm config set //npm.pkg.github.com/:_authToken=$NPM_TOKEN && \
    npm ci --omit=dev

COPY --from=build /app/web/.next ./.next
COPY --from=build /app/web/public ./public
COPY --from=build /app/web/next.config.ts ./next.config.ts
COPY --from=build /app/backend/mtg_analyzer/rules/commander /app/backend/mtg_analyzer/rules/commander

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-p", "3000", "-H", "0.0.0.0"]
