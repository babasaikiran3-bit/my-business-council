# Docker Setup for LLM Council

This guide explains how to run LLM Council using Docker for local development.

## Benefits

- **No Local Tool Installation**: No need to install Python, Node.js, uv, or npm locally
- **Hot Reload**: Code changes reflect immediately in both backend and frontend
- **Data Persistence**: Conversations survive container restarts
- **Clean URLs**: Access via `llmcouncil.local:9000` instead of `localhost:5173`
- **Single Command**: `docker-compose up` starts everything
- **Isolation**: Dependencies are containerized, no conflicts with other projects
- **Consistent Environment**: Same setup across different machines

## Prerequisites

- **Docker**: Install from [docker.com](https://www.docker.com/get-started)
- **Docker Compose**: Included with Docker Desktop, or install separately
- **OpenRouter API Key**: Required for LLM access

## First Time Setup

### 1. Create Environment File

Create a `.env` file in the project root with your OpenRouter API key:

```bash
echo "OPENROUTER_API_KEY=your_api_key_here" > .env
```

Replace `your_api_key_here` with your actual OpenRouter API key.

### 2. Add Custom Hostname (Optional but Recommended)

Add `llmcouncil.local` to your hosts file for a cleaner URL:

**macOS/Linux:**
```bash
echo "127.0.0.1 llmcouncil.local" | sudo tee -a /etc/hosts
```

**Windows:**
1. Run Notepad as Administrator
2. Open `C:\Windows\System32\drivers\etc\hosts`
3. Add line: `127.0.0.1 llmcouncil.local`
4. Save the file

### 3. Build and Start

Build the Docker images and start all services:

```bash
docker-compose up --build
```

This will:
- Build the backend container (with uv and Python dependencies)
- Build the frontend container (with Node.js and npm dependencies)
- Build the nginx reverse proxy
- Start all three services
- Set up networking between containers
- Create a persistent volume for conversation data

Wait for all services to start. You'll see logs from all three containers. Look for messages like:
- Backend: `Uvicorn running on http://0.0.0.0:9001`
- Frontend: `Local: http://localhost:5173/`
- Nginx: `start worker processes`

## Daily Usage

### Starting Services

```bash
docker-compose up
```

Or run in detached mode (background):

```bash
docker-compose up -d
```

### Accessing the Application

**Main URL (via nginx reverse proxy):**
- http://llmcouncil.local:9000 (if you added to hosts file)
- http://localhost:9000 (alternative)

**Direct access (for debugging):**
- Frontend (Vite dev server): http://localhost:5173
- Backend (FastAPI): http://localhost:9001
- API documentation (Swagger): http://localhost:9001/docs

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```

### Stopping Services

```bash
# Stop containers (keeps data)
docker-compose down

# Stop containers and remove volumes (deletes conversation data!)
docker-compose down -v
```

### Rebuilding After Changes

If you modify Dockerfile, dependencies, or configuration:

```bash
docker-compose down
docker-compose up --build
```

## Development Workflow

### Hot Reload

Both backend and frontend support hot reload:

**Backend:**
- Edit Python files in `backend/`
- Uvicorn detects changes and automatically reloads
- No need to restart containers

**Frontend:**
- Edit files in `frontend/src/`
- Vite's HMR (Hot Module Replacement) updates the browser instantly
- Changes reflect immediately

### Adding Python Dependencies

1. Edit `pyproject.toml` locally
2. Run `uv lock` locally (or let Docker rebuild handle it)
3. Rebuild backend: `docker-compose up --build backend`

### Adding Node.js Dependencies

1. Edit `frontend/package.json` locally
2. Rebuild frontend: `docker-compose up --build frontend`

## Data Persistence

Conversations are stored in a Docker named volume (`conversations-data`) which persists between container restarts.

**Viewing stored conversations:**
```bash
docker-compose exec backend ls -la /app/data/conversations/
```

**Backing up data:**
```bash
docker cp $(docker-compose ps -q backend):/app/data ./backup
```

**Restoring data:**
```bash
docker cp ./backup/conversations $(docker-compose ps -q backend):/app/data/
```

**Clearing all conversations:**
```bash
docker-compose down -v
docker-compose up
```

**Warning:** The `-v` flag deletes all conversation data!

## Troubleshooting

### Port Already in Use

If you see errors like "port is already allocated":

**Option 1:** Stop the conflicting service
```bash
# Find what's using the port
lsof -i :9000  # or :9001, :5173

# Kill the process
kill <PID>
```

**Option 2:** Change ports in `docker-compose.yml`
```yaml
ports:
  - "9002:9000"  # Change host port (left side)
```

### Environment Variable Not Loaded

Ensure `.env` file exists in project root and contains:
```
OPENROUTER_API_KEY=your_actual_key
```

Restart containers after creating/editing `.env`:
```bash
docker-compose down
docker-compose up
```

### Backend Module Import Errors

The backend uses relative imports and must be run as a module. The Dockerfile is configured correctly, but if you see import errors:

1. Check that volumes are mounted correctly in `docker-compose.yml`
2. Ensure the entire project root is mounted to `/app`
3. Rebuild: `docker-compose up --build backend`

### Frontend Not Hot Reloading

1. Ensure `node_modules` volume is mounted in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./frontend:/app
     - /app/node_modules  # This prevents host from overwriting container's node_modules
   ```

2. Check Vite is running with `--host 0.0.0.0` in the Dockerfile

3. Rebuild: `docker-compose up --build frontend`

### Nginx 502 Bad Gateway

This means nginx can't reach the backend or frontend:

1. Check all services are running:
   ```bash
   docker-compose ps
   ```

2. Check service logs:
   ```bash
   docker-compose logs backend
   docker-compose logs frontend
   ```

3. Ensure services are on the same network:
   ```bash
   docker network inspect llm-council_llmcouncil-network
   ```

4. Restart all services:
   ```bash
   docker-compose restart
   ```

### Clearing Docker Cache

If you encounter weird issues, try clearing Docker cache:

```bash
# Remove all containers, networks, and volumes for this project
docker-compose down -v

# Remove unused images
docker image prune -a

# Rebuild from scratch
docker-compose up --build
```

### Permission Issues (Linux)

On Linux, you might encounter permission issues with mounted volumes. Fix by running containers with your user ID:

Add to `docker-compose.yml` under each service:
```yaml
user: "${UID}:${GID}"
```

Then run:
```bash
UID=$(id -u) GID=$(id -g) docker-compose up
```

## Architecture

```
User Browser (llmcouncil.local:9000)
          ↓
    Nginx Reverse Proxy
     ↓            ↓
Frontend        Backend
(Vite:5173)   (FastAPI:9001)
     ↓            ↓
  (mounted)   data/conversations
   source        (volume)
```

**Network:**
- All services communicate via `llmcouncil-network` (Docker bridge network)
- Only nginx port (9000) is required for normal use
- Ports 5173 and 9001 are exposed for debugging but optional

**Volumes:**
- Backend: Entire project mounted to `/app` for hot reload
- Frontend: `frontend/` mounted to `/app` with anonymous `node_modules` volume
- Data: Named volume `conversations-data` for persistence

## Alternative: Running Without Custom Hostname

If you prefer not to modify your hosts file:

1. Access via `http://localhost:9000` instead of `http://llmcouncil.local:9000`
2. Update CORS in `backend/main.py` if needed (though it should work as-is)

## Cleaning Up

To completely remove all Docker resources for this project:

```bash
# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove built images
docker rmi llm-council-backend llm-council-frontend llm-council-nginx
```

## Getting Help

- **Check logs:** `docker-compose logs -f`
- **Inspect containers:** `docker-compose ps`
- **Enter a container:** `docker-compose exec backend bash`
- **Network debugging:** `docker network inspect llm-council_llmcouncil-network`

For application-specific issues, see the main README.md.
