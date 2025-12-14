# Use nginx alpine image for minimal size
FROM nginx:alpine

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose the reverse proxy port
EXPOSE 9000

# nginx alpine image already has CMD to start nginx
