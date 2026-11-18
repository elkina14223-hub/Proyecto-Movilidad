FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_MAPTILER_KEY=""
ENV VITE_MAPTILER_KEY=$VITE_MAPTILER_KEY
RUN npm run build

FROM nginx:1.27-alpine
# Plantilla con variables (envsubst): ver nginx/default.conf.template
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443
