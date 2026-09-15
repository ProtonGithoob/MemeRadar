FROM node:22-alpine AS builder

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts

COPY apps/web ./
RUN npm run build
RUN cp -r .next/static .next/standalone/.next/static
RUN if [ -d public ]; then cp -r public .next/standalone/public; fi

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder --chown=node:node /app/apps/web/.next/standalone ./
USER node

EXPOSE 3000

CMD ["node", "server.js"]
