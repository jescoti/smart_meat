# Development Dockerfile for the Smart Meat frontend.
# Uses `npm run dev` for hot-reloading during local development.
FROM node:20-alpine

WORKDIR /app

COPY package*.json .
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]
