# Use Node.js 20 LTS slim image
FROM node:20-slim

# Set working directory
WORKDIR /app

# Copy package files first for layer caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Expose Vite dev server port
EXPOSE 5173

# Command to run Vite dev server
# --host 0.0.0.0 makes it accessible from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
