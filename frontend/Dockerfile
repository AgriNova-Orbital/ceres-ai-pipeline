FROM node:20-alpine AS builder
WORKDIR /app
ARG API_URL=http://web:5055
ARG NEXT_PUBLIC_SENTRY_DSN=
ARG SENTRY_ENVIRONMENT=production
ARG SENTRY_RELEASE=local
ENV API_URL=$API_URL
ENV NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN \
    SENTRY_ENVIRONMENT=$SENTRY_ENVIRONMENT \
    SENTRY_RELEASE=$SENTRY_RELEASE
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
