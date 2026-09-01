FROM node:22-alpine

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts

COPY apps/web ./
RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
