import os
import discord
from discord.ext import commands
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN   = os.environ["DISCORD_TOKEN"]
GEMINI_KEY      = os.environ["GEMINI_API_KEY"]
SYSTEM_PROMPT   = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant in a Discord server. Be concise and friendly.")
MAX_HISTORY     = int(os.getenv("MAX_HISTORY", "20"))
MAX_RESPONSE    = int(os.getenv("MAX_RESPONSE", "1800"))
# ─────────────────────────────────────────────────────────────────────────────

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT,
)

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Bot()

# Per-user chat sessions  {user_id: ChatSession}
sessions: dict[int, any] = {}


def get_session(user_id: int):
    """Get or create a Gemini chat session for a user."""
    if user_id not in sessions:
        sessions[user_id] = model.start_chat(history=[])
    return sessions[user_id]


async def ask_gemini(user_id: int, user_message: str) -> str:
    """Send a message to Gemini and return the reply."""
    session = get_session(user_id)
    response = session.send_message(user_message)
    reply = response.text

    # Truncate if too long for Discord
    if len(reply) > MAX_RESPONSE:
        reply = reply[:MAX_RESPONSE] + "\n…*(response truncated)*"

    return reply


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅  Logged in as {bot.user} (id: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    """Reply when the bot is mentioned or DMed."""
    if message.author.bot:
        return

    is_dm      = isinstance(message.channel, discord.DMChannel)
    is_mention = bot.user in message.mentions

    if not (is_dm or is_mention):
        return

    # Strip the mention from the text
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not content:
        await message.reply("Hey! Ask me anything 👋")
        return

    async with message.channel.typing():
        try:
            reply = await ask_gemini(message.author.id, content)
            await message.reply(reply)
        except Exception as e:
            await message.reply(f"⚠️ Something went wrong: {e}")


# ── Slash commands ─────────────────────────────────────────────────────────────

@bot.slash_command(name="ask", description="Ask the AI a question")
async def ask(ctx: discord.ApplicationContext, question: str):
    await ctx.defer()
    try:
        reply = await ask_gemini(ctx.author.id, question)
        await ctx.respond(reply)
    except Exception as e:
        await ctx.respond(f"⚠️ Error: {e}")


@bot.slash_command(name="reset", description="Clear your conversation history")
async def reset(ctx: discord.ApplicationContext):
    sessions.pop(ctx.author.id, None)
    await ctx.respond("🧹 Your conversation history has been cleared!", ephemeral=True)


@bot.slash_command(name="ping", description="Check if the bot is alive")
async def ping(ctx: discord.ApplicationContext):
    await ctx.respond(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms", ephemeral=True)


# ── Run ────────────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
