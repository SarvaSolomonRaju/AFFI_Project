# Multi-stage: build with Node, serve the static output with nginx —
# no Node runtime in the final image, just the compiled JS/CSS/HTML.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Empty API base => the app calls the backend with RELATIVE paths (/api, /outputs,
# /health), which nginx below proxies to the api container same-origin. This is
# what makes the built site work behind ANY host/IP/domain (a remote visitor's
# browser must NOT be told to call http://localhost:8000 — that's their own machine).
ARG VITE_API_BASE=""
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
