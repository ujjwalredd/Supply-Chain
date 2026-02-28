FROM node:18-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

COPY dashboard/package*.json ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
