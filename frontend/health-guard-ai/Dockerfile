# Build Stage
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy the rest of the application
COPY . .

# Build the Vite application
RUN npm run build

# Production Stage
FROM node:20-alpine

WORKDIR /app

# Install 'serve' to run the static files
RUN npm install -g serve

# Copy the built files from the build stage
COPY --from=build /app/dist ./dist

# Cloud Run defines the PORT environment variable (default 8080)
ENV PORT=8080
EXPOSE 8080

# Run the 'serve' command to host the static site
CMD serve -s dist -l tcp://0.0.0.0:$PORT
