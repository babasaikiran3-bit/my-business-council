# Composio MCP Gateway Setup Guide

This guide walks you through setting up Composio MCP Gateway integration with LLM Council to enable tool-augmented deliberation.

## What is Composio?

Composio is a managed MCP (Model Context Protocol) Gateway that provides instant access to 500+ enterprise-grade integrations. By integrating Composio with LLM Council, your council members can access external tools like GitHub, Slack, Google Workspace, and more during deliberation.

## Benefits

- **Instant Tool Access**: 500+ pre-built integrations ready to use
- **Managed Authentication**: OAuth 2.1 flows handled automatically
- **Zero Maintenance**: Composio maintains all integrations
- **Enterprise-Ready**: SOC2/ISO certified, RBAC, audit trails included
- **Cost Optimization**: Built-in caching and rate limiting

## Prerequisites

1. A Composio account (sign up at [composio.dev](https://composio.dev))
2. Python 3.8+ installed
3. LLM Council backend running

## Step 1: Create a Composio Account

1. Visit [composio.dev](https://composio.dev) and sign up for an account
2. Navigate to your dashboard and copy your API key
3. Save this API key - you'll need it for configuration

## Step 2: Create an MCP Server Configuration

You can create an MCP server configuration either through the Composio dashboard or programmatically.

### Option A: Using Composio Dashboard

1. Log in to your Composio dashboard
2. Navigate to **MCP Configs** section
3. Click **Create New MCP Server**
4. Configure your server:
   - **Name**: `llm-council-gateway` (or any name you prefer)
   - **Toolkits**: Select the toolkits you want to enable
     - Recommended starters: GitHub, Slack, Google Drive
5. For each toolkit, create an **Auth Config**:
   - Click **Create Auth Config** for the toolkit
   - Follow the OAuth flow to authenticate
   - Save the auth config ID
6. Copy your **MCP Server ID** from the dashboard

### Option B: Programmatically (Advanced)

```python
from composio import Composio

# Initialize Composio client
composio = Composio(api_key="your_api_key")

# Create MCP server
server = composio.mcp.create(
    name="llm-council-gateway",
    toolkits=[
        {"toolkit": "github", "auth_config": "ac_github_xxx"},
        {"toolkit": "slack", "auth_config": "ac_slack_xxx"},
        {"toolkit": "googledrive", "auth_config": "ac_drive_xxx"}
    ]
)

print(f"MCP Server ID: {server.id}")
```

## Step 3: Configure LLM Council

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Composio credentials:
   ```bash
   # OpenRouter Configuration
   OPENROUTER_API_KEY=your_openrouter_api_key_here

   # Composio Configuration
   COMPOSIO_API_KEY=your_composio_api_key_here
   COMPOSIO_MCP_SERVER_ID=your_mcp_server_id_here

   # Enable tool-augmented deliberation
   ENABLE_TOOLS=true
   ```

3. Install the Composio SDK:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

## Step 4: Verify Installation

1. Start the LLM Council backend:
   ```bash
   cd backend
   python -m backend.main
   ```

2. Check the logs for Composio initialization:
   ```
   INFO: Composio client initialized
   INFO: MCP Server ID: your_server_id
   INFO: Tools enabled: true
   ```

3. Test a query that could benefit from tools:
   ```
   Query: "What are the latest commits in the main branch of our repository?"
   ```

   The council members should now have access to GitHub tools and can fetch real-time information.

## Step 5: User Authentication (Optional)

For user-specific tool access, you need to authenticate users with Composio:

1. Generate a user-specific MCP URL:
   ```python
   from backend.composio_client import get_composio_client

   composio = get_composio_client()
   mcp_url = composio.generate_user_mcp_url(user_id="user_123")
   print(f"User MCP URL: {mcp_url}")
   ```

2. Direct users to authenticate via Composio's hosted auth:
   - Visit the Composio dashboard
   - Navigate to **Connected Accounts**
   - Authenticate with the desired services

3. Once authenticated, the council will have access to user-specific data and can perform actions on behalf of the user.

## Available Toolkits

Composio provides 500+ integrations across various categories:

### Development & Code
- **GitHub**: Repository management, PR reviews, issue tracking
- **GitLab**: CI/CD pipelines, merge requests
- **Bitbucket**: Code hosting, pull requests

### Communication
- **Slack**: Send messages, create channels, manage users
- **Microsoft Teams**: Team collaboration, meetings
- **Discord**: Server management, messaging

### Productivity
- **Google Workspace**: Gmail, Drive, Calendar, Docs
- **Microsoft 365**: Outlook, OneDrive, SharePoint
- **Notion**: Database queries, page creation

### Project Management
- **Jira**: Issue tracking, sprint management
- **Linear**: Task management, project tracking
- **Asana**: Team collaboration, workflows

### Cloud & Infrastructure
- **AWS**: EC2, S3, Lambda management
- **Azure**: Resource management, deployments
- **GCP**: Compute, storage, databases

### CRM & Sales
- **Salesforce**: Lead management, opportunity tracking
- **HubSpot**: Marketing automation, CRM
- **Zendesk**: Customer support, ticketing

For a complete list, visit [composio.dev/integrations](https://composio.dev/integrations)

## How It Works

When tool-augmented deliberation is enabled:

1. **Stage 1 Enhancement**: Each council member receives a prompt that includes:
   - The original user query
   - A list of available tools with descriptions
   - Instructions on how to use tools

2. **Tool Discovery**: The system queries Composio for available tools based on:
   - Configured MCP server toolkits
   - User authentication status
   - RBAC permissions

3. **Tool Mention Tracking**: The system tracks which tools each council member mentions in their response using the format:
   ```
   [TOOL: tool_name with parameters]
   ```

4. **Transparency**: Tool usage is displayed in the UI, showing which council members used which tools.

## Example: Tool-Augmented Query

**User Query**: "Review the latest PR in our repository and summarize the changes"

**Without Tools**:
- Council members can only provide generic advice based on their training data
- No access to actual PR data
- Responses are theoretical

**With Composio Tools**:
- Council members can use `GITHUB_GET_PULL_REQUEST` to fetch PR details
- Council members can use `GITHUB_GET_DIFF` to analyze code changes
- Responses are grounded in real, current data
- Final synthesis includes actual PR information

## Troubleshooting

### Issue: "COMPOSIO_API_KEY must be set"

**Solution**: Ensure your `.env` file contains a valid Composio API key:
```bash
COMPOSIO_API_KEY=your_actual_api_key_here
```

### Issue: "Tools will not be available"

**Solution**: This warning appears when `COMPOSIO_MCP_SERVER_ID` is not set. Either:
1. Set the MCP Server ID in `.env`
2. Or set `ENABLE_TOOLS=false` to disable tool-augmented deliberation

### Issue: "Could not list tools"

**Solution**: Check that:
1. Your Composio API key is valid
2. Your MCP server has toolkits configured
3. You have network connectivity to Composio's API

### Issue: Tools not appearing in prompts

**Solution**: Verify that:
1. `ENABLE_TOOLS=true` in your `.env` file
2. The backend has been restarted after configuration changes
3. Your MCP server has at least one toolkit configured

## Advanced Configuration

### Custom Tool Selection

You can limit which tools are exposed to the council by specifying `allowed_tools` when creating the MCP server:

```python
server = composio.mcp.create(
    name="llm-council-gateway",
    toolkits=[
        {"toolkit": "github", "auth_config": "ac_github_xxx"}
    ],
    allowed_tools=[
        "GITHUB_GET_REPO",
        "GITHUB_GET_PULL_REQUEST",
        "GITHUB_LIST_COMMITS"
    ]
)
```

### Role-Based Access Control (RBAC)

Implement RBAC by creating different MCP servers for different user roles:

```python
# Admin MCP server with full access
admin_server = composio.mcp.create(
    name="llm-council-admin",
    toolkits=[{"toolkit": "github", "auth_config": "ac_github_xxx"}]
)

# Read-only MCP server for standard users
readonly_server = composio.mcp.create(
    name="llm-council-readonly",
    toolkits=[{"toolkit": "github", "auth_config": "ac_github_xxx"}],
    allowed_tools=["GITHUB_GET_REPO", "GITHUB_GET_PULL_REQUEST"]
)
```

### Cost Management

Monitor and control costs using Composio's built-in features:

1. **Caching**: Enable caching for frequently accessed data
2. **Rate Limiting**: Set rate limits per user or per tool
3. **Budget Alerts**: Configure alerts at 50%, 75%, 90% of budget
4. **Usage Analytics**: Track tool usage in Composio dashboard

## Security Best Practices

1. **Never commit `.env` files**: Keep your API keys secure
2. **Use environment variables**: Store sensitive data in environment variables
3. **Rotate keys regularly**: Update API keys periodically
4. **Audit logs**: Review audit logs in Composio dashboard
5. **Least privilege**: Only enable tools that are necessary

## Next Steps

- Explore the [Composio documentation](https://docs.composio.dev)
- Join the [Composio Discord community](https://discord.gg/composio)
- Check out [example workflows](https://composio.dev/examples)
- Read about [MCP Gateway architecture](https://composio.dev/blog/mcp-gateways-guide)

## Support

For issues related to:
- **LLM Council**: Open an issue on the GitHub repository
- **Composio**: Visit [help.composio.dev](https://help.composio.dev) or join their Discord

## References

- [Composio MCP Gateway Documentation](https://docs.composio.dev/docs/mcp-quickstart)
- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [Composio Integrations Catalog](https://composio.dev/integrations)
