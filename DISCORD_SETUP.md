# Discord Bot Setup Guide

This guide will help you run the LLM Council as a Discord bot on your NAS or any Linux server.

## Overview

Instead of the web interface, this Discord bot allows you to interact with the LLM Council directly through Discord. The bot:
- Responds to `!council <question>` commands
- Can be mentioned directly: `@LLMCouncil <question>`
- Creates a thread for each query to keep discussions organized
- Shows all 3 stages using Discord embeds (nice formatting)
- Stores conversation history in JSON files per Discord channel

## Prerequisites

- **Python 3.10+** installed on your NAS
- **Discord account** with permissions to create a bot
- **OpenRouter API key** with credits

## Step 1: Create a Discord Bot

### 1.1 Create Application on Discord Developer Portal

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Give it a name (e.g., "LLM Council")
4. Click **"Create"**

### 1.2 Create Bot User

1. In your application, go to the **"Bot"** tab
2. Click **"Add Bot"** → Confirm
3. Under **"Token"**, click **"Reset Token"** and copy it (save this for later!)
4. Enable these **Privileged Gateway Intents**:
   - ✅ Message Content Intent
   - ✅ Server Members Intent (optional)

### 1.3 Invite Bot to Your Server

1. Go to **"OAuth2"** → **"URL Generator"**
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions:
   - ✅ Send Messages
   - ✅ Send Messages in Threads
   - ✅ Create Public Threads
   - ✅ Embed Links
   - ✅ Read Message History
4. Copy the generated URL and open it in your browser
5. Select your Discord server and authorize

## Step 2: Install Dependencies

On your NAS, navigate to the project directory:

```bash
cd /path/to/llm-council
```

### Option A: Using uv (recommended)

```bash
# Install discord.py
uv add discord.py

# Sync dependencies
uv sync
```

### Option B: Using pip

```bash
pip install discord.py httpx python-dotenv
```

## Step 3: Configure Environment Variables

Edit your `.env` file:

```bash
nano .env
```

Add both API keys:

```bash
# OpenRouter API key
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Discord bot token
DISCORD_BOT_TOKEN=your-discord-bot-token-here
```

Save and exit (`Ctrl+X`, `Y`, `Enter`).

## Step 4: Configure Models (Optional)

Edit `backend/config.py` to customize your council:

```python
# Council members - reduce this list to save costs
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
]

# Chairman model - Opus 4.1 for high-quality synthesis
CHAIRMAN_MODEL = "anthropic/claude-opus-4.1"
```

**Cost-saving tip:** Fewer models = cheaper! You can run with just 2-3 council members.

## Step 5: Run the Bot

### Manual Run (for testing)

```bash
uv run python -m backend.discord_bot
```

You should see:
```
✅ Bot logged in as LLM Council (ID: 123456789)
🎯 Ready to receive council queries!
```

Test it in Discord:
```
!council What is the capital of France?
```

### Run as Background Service (for production)

#### Option A: Using tmux (simple)

```bash
# Start tmux session
tmux new -s council-bot

# Run the bot
uv run python -m backend.discord_bot

# Detach: Press Ctrl+B, then D
# Reattach later: tmux attach -t council-bot
```

#### Option B: Using systemd (recommended for NAS)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/llm-council-bot.service
```

Add this configuration (adjust paths for your system):

```ini
[Unit]
Description=LLM Council Discord Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/llm-council
Environment="PATH=/path/to/llm-council/.venv/bin:/usr/bin"
ExecStart=/path/to/llm-council/.venv/bin/python -m backend.discord_bot
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable llm-council-bot
sudo systemctl start llm-council-bot

# Check status
sudo systemctl status llm-council-bot

# View logs
sudo journalctl -u llm-council-bot -f
```

## Step 6: Usage in Discord

### Commands

**Submit a question:**
```
!council What are the key differences between async and threading in Python?
```

**Mention the bot:**
```
@LLMCouncil Explain quantum computing in simple terms
```

**Get help:**
```
!help_council
```

### How It Works

1. **Thread Creation:** The bot creates a thread for each question to keep things organized
2. **Stage 1:** Individual responses from all council members (shown in blue embeds)
3. **Stage 2:** Peer reviews and rankings (shown in orange embeds)
4. **Aggregate Rankings:** Summary of which models performed best
5. **Stage 3:** Final synthesis from Chairman (shown in green embed)

## Data Storage

Conversations are stored in:
```
data/discord_channels/{channel_id}.json
```

Each file contains:
- Channel ID and name
- All questions asked in that channel
- Complete stage 1, 2, 3 results
- User information (ID, username)

You can back these up or analyze them later.

## Troubleshooting

### Bot doesn't respond

1. **Check if bot is running:**
   ```bash
   systemctl status llm-council-bot
   # or
   tmux ls
   ```

2. **Check logs:**
   ```bash
   journalctl -u llm-council-bot -n 50
   ```

3. **Verify permissions:** Make sure bot has Send Messages and Create Threads permissions in the channel

### Rate limiting errors

Discord has rate limits. The bot includes small delays between messages (`asyncio.sleep(0.5)`). If you hit limits:
- Reduce council size (fewer models = fewer messages)
- Increase delays in `discord_bot.py`

### Model errors

If specific models fail:
- Check OpenRouter status and credits
- Remove problematic models from `COUNCIL_MODELS` in `config.py`
- The system gracefully handles failures (continues with successful responses)

### Environment issues on NAS

Some NAS systems (Synology, QNAP) have quirks:

1. **Python version:** Make sure you have Python 3.10+
   ```bash
   python3 --version
   ```

2. **Path issues:** Use absolute paths in systemd service file

3. **Permissions:** Make sure your user can access the project directory

## Cost Optimization

Each council query costs money on OpenRouter. To reduce costs:

1. **Fewer council members:**
   ```python
   COUNCIL_MODELS = [
       "openai/gpt-5.1",
       "anthropic/claude-sonnet-4.5",
   ]
   ```

2. **Use cheaper chairman:**
   ```python
   CHAIRMAN_MODEL = "anthropic/claude-sonnet-4.5"  # Instead of Opus
   ```

3. **Monitor usage:** Check your OpenRouter dashboard regularly

4. **Limit users:** Only allow certain Discord roles to use the bot (modify `discord_bot.py` to add permission checks)

## Advanced: Permission Control

To restrict bot usage to specific roles, add this to `discord_bot.py`:

```python
@bot.command(name='council', help='Submit a question to the LLM Council')
@commands.has_role("Council Member")  # Only users with this role can use it
async def council_command(ctx, *, question: str):
    await process_council_query(ctx, question)
```

Or check in the command:
```python
async def process_council_query(ctx, question: str):
    # Check if user has required role
    allowed_role = discord.utils.get(ctx.guild.roles, name="Council Member")
    if allowed_role not in ctx.author.roles:
        await ctx.send("❌ You don't have permission to use the Council.")
        return

    # ... rest of code
```

## Stopping the Bot

**If using tmux:**
```bash
tmux attach -t council-bot
# Press Ctrl+C to stop
```

**If using systemd:**
```bash
sudo systemctl stop llm-council-bot
```

## Updates

To update the bot after making changes:

```bash
# Pull latest code (if using git)
git pull

# Restart the service
sudo systemctl restart llm-council-bot
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start bot (manual) | `uv run python -m backend.discord_bot` |
| Start service | `sudo systemctl start llm-council-bot` |
| Stop service | `sudo systemctl stop llm-council-bot` |
| View logs | `sudo journalctl -u llm-council-bot -f` |
| Check status | `sudo systemctl status llm-council-bot` |
| Discord command | `!council <your question>` |
| Discord mention | `@LLMCouncil <your question>` |

---

Enjoy your Discord-based LLM Council! 🏛️
