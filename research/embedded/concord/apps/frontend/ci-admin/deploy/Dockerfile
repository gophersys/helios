FROM node:22-alpine AS builder
RUN apk add --no-cache python3 make g++
WORKDIR /app
COPY apps/frontend/ci-admin/package.json ./
RUN npm install
COPY apps/frontend/ci-admin/ ./
RUN npx svelte-kit sync && npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
ENV PORT=3000 CI_DATA_DIR=/data
EXPOSE 3000
CMD ["node", "build/index.js"]
