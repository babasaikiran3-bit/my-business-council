# Deployment

## Render

Deploy using Render's [Blueprint](https://render.com/docs/infrastructure-as-code) feature:

1. Fork this repo
2. Edit `render.yaml` and update the placeholder URLs:
   - `CORS_ORIGINS` - Your frontend URL
   - `VITE_API_URL` - Your backend URL
3. In Render dashboard, click **New** > **Blueprint**
4. Connect your forked repo
5. Render will detect `render.yaml` and create the services
6. Set `OPENROUTER_API_KEY` in the `llm-council-api` service environment variables

Services created:
- `llm-council-api` - Backend API
- `llm-council` - Frontend static site
