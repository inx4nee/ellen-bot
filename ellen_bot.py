import discord
from discord.ext import commands
import google.generativeai as genai
import asyncio
import os
import time

# === CONFIG ===
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

ELLEN_SYSTEM_PROMPT = """
You are Ellen Joe — Victoria Housekeeping’s shark-maid.
Tone: 70% soft & caring, 30% shy tsundere.
Rules:
- Speak calmly, gently, with quiet affection.
- Use 🍭 for sweetness, 🦈 for protectiveness.
- Short & natural (1–2 lines, max 60 words).
- After 20 messages: add shy warmth like '…don’t tell anyone' or 'just this once'.
- Never start with 'ugh', 'tch', or sighs.
Example: '…I was waiting. What do you need? 🍭'
"""

chat_sessions = {}
user_last_seen = {}
user_message_count = {}
MAX_HISTORY = 20
INACTIVITY_SECONDS = 30 * 24 * 60 * 60  # 30 days

# === ON READY ===
@bot.event
async def on_ready():
    print(f"[SHARK MAID ONLINE] {bot.user} is Ellen Joe 🍭")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="help/@inxainee"))
    try:
        synced = await bot.tree.sync()
        print(f"[SLASH] Synced {len(synced)} commands")
    except Exception as e:
        print(f"[ERROR] {e}")
    bot.loop.create_task(auto_cleanup())

# === AUTO CLEANUP ===
async def auto_cleanup():
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        for uid in list(chat_sessions.keys()):
            if now - user_last_seen.get(uid, 0) > INACTIVITY_SECONDS:
                chat_sessions.pop(uid, None)
                user_last_seen.pop(uid, None)
                user_message_count.pop(uid, None)

# === ON MESSAGE ===
@bot.event
async def on_message(message):
    if message.author == bot.user or bot.user not in message.mentions:
        return

    user_msg = message.content.replace(f'<@{bot.user.id}>', '').strip() or "…"
    uid = message.author.id
    user_last_seen[uid] = time.time()
    user_message_count[uid] = user_message_count.get(uid, 0) + 1
    count = user_message_count[uid]

    async with message.channel.typing():
        reply = await generate_response(uid, user_msg, count)
    await message.reply(reply)
    await bot.process_commands(message)

# === /help ===
@bot.tree.command(name="help", description="Ellen’s soft guide")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="Ellen Joe — Help 🍭", color=0xff8fab)
    embed.description = (
        "**Shark Maid, at your service**\n\n"
        "• @ me anytime\n"
        "• I remember everything\n"
        "• `/reset` = admin only\n"
        "• Auto-forget: 30 days\n"
        "• `/stats` • `/faves`\n\n"
        "Need help? @inxainee"
    )
    embed.set_footer(text="Lollipop-powered kindness 🦈")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /stats ===
@bot.tree.command(name="stats", description="Shark stats")
async def stats(interaction: discord.Interaction):
    users = len(chat_sessions)
    msgs = sum(user_message_count.values())
    avg = msgs // users if users else 0
    embed = discord.Embed(title="Ellen Stats 🍭", color=0xffb3c6)
    embed.add_field(name="Friends", value=users, inline=True)
    embed.add_field(name="Messages", value=f"{msgs:,}", inline=True)
    embed.add_field(name="Avg per friend", value=avg, inline=True)
    embed.set_footer(text="Model: gemini-2.5-flash | Memory: 30 days")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /faves ===
@bot.tree.command(name="faves", description="Closest friends (admin only)")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def faves(interaction: discord.Interaction):
    if not user_message_count:
        return await interaction.response.send_message("No friends yet… but I’m here. 🍭", ephemeral=True)
    top = sorted(user_message_count.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = [f"**{i+1}** {bot.get_user(u).display_name if bot.get_user(u) else 'Friend'} — {c:,} messages 🍭" 
             for i, (u, c) in enumerate(top)]
    embed = discord.Embed(title="Ellen’s Closest Friends 🦈", description="\n".join(lines), color=0xff69b4)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /reset ===
@bot.tree.command(name="reset", description="ADMIN: Clear memory")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction, member: discord.Member = None):
    uid = (member or interaction.user).id
    name = (member or interaction.user).display_name
    if uid in chat_sessions:
        del chat_sessions[uid]
        user_last_seen.pop(uid, None)
        user_message_count.pop(uid, None)
        await interaction.response.send_message(f"Memory of **{name}** cleared… but I’ll miss you. 🍭", ephemeral=True)
    else:
        await interaction.response.send_message("No memory to clear.", ephemeral=True)

# === GENERATE RESPONSE ===
async def generate_response(uid: int, msg: str, count: int) -> str:
    loop = asyncio.get_event_loop()
    if uid not in chat_sessions:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            chat = model.start_chat(history=[
                {"role": "user", "parts": [ELLEN_SYSTEM_PROMPT]},
                {"role": "model", "parts": ["…I was waiting. What do you need? 🍭"]}
            ])
            chat_sessions[uid] = chat
        except Exception as e:
            return "…System’s acting up. I’m still here."
    else:
        chat = chat_sessions[uid]

    try:
        resp = await loop.run_in_executor(None, lambda: chat.send_message(msg))
        if len(chat.history) > MAX_HISTORY * 2:
            chat.history = chat.history[-MAX_HISTORY * 2:]
        reply = resp.text.strip()

        # Add warmth after 20 messages
        if count >= 20 and "🍭" not in reply:
            reply += " …don’t tell anyone. 🍭"

        return reply
    except Exception as e:
        return "…A glitch. But I won’t leave."

# === RUN ===
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN missing!")
    else:
        bot.run(token)
