# Multi-stage build: compile the React app, then serve the static output
# with nginx (also reverse-proxies /api to the backend service so the
# frontend can be deployed as a single container/port on the VPS).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# Empty base URL -> the app calls relative paths like "/api/jobs", which
# nginx below proxies to the backend container. Override at build time
# only if the frontend is served from a different origin than the API.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
