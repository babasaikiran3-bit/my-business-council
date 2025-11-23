"""Discord bot for LLM Council."""

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any

from .council import run_full_council
from .storage import get_conversation, create_conversation, add_user_message, add_assistant_message

load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Discord message length limit
MAX_MESSAGE_LENGTH = 2000


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Split a long message into chunks that fit Discord's limit.

    Args:
        text: The text to split
        max_length: Maximum length per chunk

    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                # Single line is too long, split it
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
        else:
            current_chunk += ('\n' if current_chunk else '') + line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def create_stage1_embed(model: str, response: str, index: int, total: int) -> discord.Embed:
    """Create an embed for a Stage 1 response."""
    # Truncate if needed (embed descriptions have 4096 char limit)
    truncated = response[:4000] + "..." if len(response) > 4000 else response

    embed = discord.Embed(
        title=f"📝 Stage 1: Individual Response ({index}/{total})",
        description=truncated,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Model: {model}")
    return embed


def create_stage2_embed(model: str, ranking: str, parsed_ranking: List[str], index: int, total: int) -> discord.Embed:
    """Create an embed for a Stage 2 ranking."""
    # Truncate if needed
    truncated = ranking[:4000] + "..." if len(ranking) > 4000 else ranking

    embed = discord.Embed(
        title=f"🎯 Stage 2: Peer Review ({index}/{total})",
        description=truncated,
        color=discord.Color.orange()
    )

    # Add parsed ranking as field
    if parsed_ranking:
        ranking_text = "\n".join([f"{i+1}. {label}" for i, label in enumerate(parsed_ranking)])
        embed.add_field(name="Extracted Ranking", value=ranking_text, inline=False)

    embed.set_footer(text=f"Reviewer: {model}")
    return embed


def create_stage3_embed(model: str, response: str) -> discord.Embed:
    """Create an embed for the Stage 3 final synthesis."""
    # Truncate if needed
    truncated = response[:4000] + "..." if len(response) > 4000 else response

    embed = discord.Embed(
        title="✅ Stage 3: Final Synthesis",
        description=truncated,
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Chairman: {model}")
    return embed


def create_aggregate_rankings_embed(rankings: List[Dict[str, Any]]) -> discord.Embed:
    """Create an embed showing aggregate rankings."""
    embed = discord.Embed(
        title="📊 Aggregate Rankings",
        description="Average ranking across all peer reviews (lower is better):",
        color=discord.Color.purple()
    )

    for i, rank_data in enumerate(rankings, 1):
        model = rank_data['model']
        avg_rank = rank_data['average_rank']
        count = rank_data['rankings_count']

        embed.add_field(
            name=f"{i}. {model}",
            value=f"Average Position: **{avg_rank}** ({count} votes)",
            inline=False
        )

    return embed


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f'✅ Bot logged in as {bot.user.name} (ID: {bot.user.id})')
    print(f'🎯 Ready to receive council queries!')
    print('---')


@bot.command(name='council', help='Submit a question to the LLM Council')
async def council_command(ctx, *, question: str):
    """
    Main command to run the LLM Council.

    Usage: !council <your question>
    """
    await process_council_query(ctx, question)


async def process_council_query(ctx, question: str):
    """Process a council query and send results to Discord."""
    # Create a thread for this query to keep things organized
    thread_name = question[:100] if len(question) <= 100 else question[:97] + "..."

    try:
        # Send initial message
        initial_msg = await ctx.send(f"🤔 **Consulting the LLM Council...**\nQuestion: {question}")

        # Create thread
        thread = await initial_msg.create_thread(name=thread_name)

        # Send processing message
        await thread.send("⏳ Stage 1: Collecting individual responses from council members...")

        # Run the full council process
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(question)

        # Check for errors
        if not stage1_results:
            await thread.send("❌ All models failed to respond. Please try again later.")
            return

        # === STAGE 1: Individual Responses ===
        await thread.send("### 📝 Stage 1: Individual Responses")

        for idx, result in enumerate(stage1_results, 1):
            embed = create_stage1_embed(
                model=result['model'],
                response=result['response'],
                index=idx,
                total=len(stage1_results)
            )
            await thread.send(embed=embed)
            await asyncio.sleep(0.5)  # Small delay to avoid rate limits

        # === STAGE 2: Peer Reviews ===
        await thread.send("\n⏳ Stage 2: Collecting peer reviews and rankings...")
        await thread.send("### 🎯 Stage 2: Peer Reviews")

        for idx, result in enumerate(stage2_results, 1):
            embed = create_stage2_embed(
                model=result['model'],
                ranking=result['ranking'],
                parsed_ranking=result.get('parsed_ranking', []),
                index=idx,
                total=len(stage2_results)
            )
            await thread.send(embed=embed)
            await asyncio.sleep(0.5)

        # Show aggregate rankings
        if metadata.get('aggregate_rankings'):
            aggregate_embed = create_aggregate_rankings_embed(metadata['aggregate_rankings'])
            await thread.send(embed=aggregate_embed)

        # === STAGE 3: Final Synthesis ===
        await thread.send("\n⏳ Stage 3: Chairman synthesizing final answer...")
        await thread.send("### ✅ Stage 3: Final Answer")

        embed = create_stage3_embed(
            model=stage3_result['model'],
            response=stage3_result['response']
        )
        await thread.send(embed=embed)

        # Final completion message
        await thread.send("---\n✨ **Council deliberation complete!**")

    except Exception as e:
        error_msg = f"❌ An error occurred: {str(e)}"
        print(f"Error in process_council_query: {e}")

        # Try to send error to thread if it exists, otherwise to channel
        try:
            if 'thread' in locals():
                await thread.send(error_msg)
            else:
                await ctx.send(error_msg)
        except:
            await ctx.send(error_msg)


@bot.event
async def on_message(message):
    """Handle mentions of the bot."""
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

    # If bot is mentioned (but not a command), treat as council query
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        # Remove the mention from the message
        question = message.content.replace(f'<@{bot.user.id}>', '').strip()
        question = message.content.replace(f'<@!{bot.user.id}>', '').strip()

        if question:
            await process_council_query(message, question)


@bot.command(name='help_council', help='Show help for the LLM Council bot')
async def help_council(ctx):
    """Display help information."""
    help_embed = discord.Embed(
        title="🏛️ LLM Council Bot - Help",
        description="A multi-stage deliberation system where multiple LLMs collaboratively answer your questions.",
        color=discord.Color.blue()
    )

    help_embed.add_field(
        name="How to Use",
        value=(
            "**Method 1:** Use the command\n"
            "`!council <your question>`\n\n"
            "**Method 2:** Mention the bot\n"
            "`@LLMCouncil <your question>`"
        ),
        inline=False
    )

    help_embed.add_field(
        name="How It Works",
        value=(
            "**Stage 1:** All council members respond individually\n"
            "**Stage 2:** Each member reviews and ranks all responses (anonymized)\n"
            "**Stage 3:** The Chairman synthesizes a final answer"
        ),
        inline=False
    )

    help_embed.add_field(
        name="Example",
        value="`!council What are the key differences between async and threading in Python?`",
        inline=False
    )

    await ctx.send(embed=help_embed)


def main():
    """Run the Discord bot."""
    token = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        print("❌ Error: DISCORD_BOT_TOKEN not found in environment variables")
        print("Please add DISCORD_BOT_TOKEN to your .env file")
        return

    print("🚀 Starting Discord Council Bot...")
    bot.run(token)


if __name__ == "__main__":
    main()
