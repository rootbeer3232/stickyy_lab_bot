import os
import json
import random
import time
from datetime import datetime, timedelta

import re
from collections import defaultdict, deque

import discord
from discord.ext import commands
from discord.utils import get

from keep_alive import keep_alive

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"
CONFIG_FILE = "bot_config.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.reactions = True


# Disable default help so we can use our own clean help menu
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Store reaction role message IDs and verification settings
reaction_role_messages = {}
verification_enabled = False
verification_channel_id = None
verified_role_id = None
tiktok_username = None
tiktok_live_channel_id = None

# XP / Level / Economy / Strikes system
# xp_data = {
#   "user_id": {
#       "xp": int,
#       "level": int,
#       "coins": int,
#       "last_daily": str (ISO),
#       "strikes": int
#   }
# }
xp_data = {}

# Matchmaking queue (in-memory)
match_queue = []  # list of user_ids

# Ticket config
TICKET_CATEGORY_NAME = "🎫┃Support Tickets"

# OG role cap
OG_DAY_ONE_MAX = 25
og_day_one_claims = []  # list of user_ids who successfully claimed OG

# Auto-moderation banned words (hard filter)
# IMPORTANT: You must fill this with your own list of words in your own editor.
# I cannot legally paste the real slurs here.
BANNED_WORDS = [
    "word1",
    "word2",
    # Add your strongest banned words here (slurs, hate, etc.)
]

# ---------- AUTO-ADMIN FILTER CONSTANTS / STATE ----------

# ----- Message Spam (already existed) -----
SPAM_WINDOW_SECONDS = 5       # time window to count messages
SPAM_MESSAGE_LIMIT = 7        # max messages allowed in the window

# ----- Caps Filter -----
MIN_CAPS_LENGTH = 12          # min length before we even check caps
MAX_CAPS_RATIO = 0.7          # 70%+ letters are caps => strike

# ----- Ping Spam -----
# How many mentions in a single message before we punish
MAX_MENTIONS_PER_MESSAGE = 5          # tweak as you like

# Time window for "ping-heavy" messages (in seconds)
PING_WINDOW_SECONDS = 10

# How many ping-heavy messages allowed in that window
MAX_PING_MESSAGES_IN_WINDOW = 3

# Track per-guild per-user timestamps for anti-spam (message count)
spam_tracker = defaultdict(lambda: defaultdict(lambda: deque()))

# Track per-guild per-user timestamps for ping spam (only messages with mentions)
ping_tracker = defaultdict(lambda: defaultdict(lambda: deque()))


# Simple link / invite regex
LINK_REGEX = re.compile(
    r"(https?://\S+|discord\.gg/\S+|discord\.com/invite/\S+)",
    re.IGNORECASE
)

# Channels where links are allowed (by name)
LINK_ALLOWED_CHANNEL_NAMES = set()  # e.g. {"🎞️┃clips-and-highlights", "🎁┃giveaways"}

# Bot boot time (set in on_ready)
BOOT_TIME = None


# ----- New Account Restrictions -----
# Any account younger than this (in days) is treated as "new"
NEW_ACCOUNT_MIN_DAYS = 7

# Role given to new accounts automatically
NEW_ACCOUNT_ROLE_NAME = "🆕 New Account"

# Channel names where new accounts ARE allowed to talk
NEW_ACCOUNT_ALLOWED_CHANNELS = {
    "👋┃welcome",
    "✅┃verification",
    "📜┃rules",
    "📢┃lab-announcements",
    "🧬┃introduce-yourself",
}



# ---------- PERSISTENCE ----------

def load_config():
    """Load bot configuration from file"""
    global reaction_role_messages, verification_enabled, verification_channel_id
    global verified_role_id, tiktok_username, tiktok_live_channel_id, xp_data
    global og_day_one_claims

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            reaction_role_messages = config.get("reaction_role_messages", {})
            # Convert string keys back to int for message IDs
            reaction_role_messages = {int(k): v for k, v in reaction_role_messages.items()}
            verification_enabled = config.get("verification_enabled", False)
            verification_channel_id = config.get("verification_channel_id")
            verified_role_id = config.get("verified_role_id")
            tiktok_username = config.get("tiktok_username")
            tiktok_live_channel_id = config.get("tiktok_live_channel_id")
            xp_data = config.get("xp_data", {})
            og_day_one_claims = config.get("og_day_one_claims", [])
            print("Loaded bot configuration")
    except FileNotFoundError:
        print("No config file found, starting fresh")
    except Exception as e:
        print(f"Error loading config: {e}")


def save_config():
    """Save bot configuration to file"""
    config = {
        "reaction_role_messages": reaction_role_messages,
        "verification_enabled": verification_enabled,
        "verification_channel_id": verification_channel_id,
        "verified_role_id": verified_role_id,
        "tiktok_username": tiktok_username,
        "tiktok_live_channel_id": tiktok_live_channel_id,
        "xp_data": xp_data,
        "og_day_one_claims": og_day_one_claims,
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print("Saved bot configuration")
    except Exception as e:
        print(f"Error saving config: {e}")


# ---------- HELPER FUNCTIONS ----------

def censor_banned_words(text: str) -> str:
    """
    Return the message content with banned words replaced by ***
    so we don't re-post slurs in chat.
    """
    if not text:
        return text

    lowered = text.lower()
    result = list(text)

    for bad in BANNED_WORDS:
        if not bad:
            continue
        bad_lower = bad.lower()
        start = 0
        while True:
            idx = lowered.find(bad_lower, start)
            if idx == -1:
                break
            end = idx + len(bad_lower)
            for i in range(idx, min(end, len(result))):
                result[i] = "*"
            start = end

    return "".join(result)


async def get_or_create_role(guild, name, **kwargs):
    role = get(guild.roles, name=name)
    if role is None:
        role = await guild.create_role(name=name, **kwargs)
        print(f"Created role: {name}")
    return role


async def get_or_create_category(guild, name, overwrites=None):
    category = get(guild.categories, name=name)
    if category is None:
        if overwrites is not None:
            category = await guild.create_category(name=name, overwrites=overwrites)
        else:
            category = await guild.create_category(name=name)
        print(f"Created category: {name}")
    else:
        # Update overwrites if provided
        if overwrites is not None:
            try:
                await category.edit(overwrites=overwrites)
            except discord.HTTPException as e:
                print(f"Couldn't update overwrites for category {name}: {e}")
    return category


async def get_or_create_text_channel(guild, category, name, overwrites=None):
    """
    Get or create a text channel.
    - If it exists anywhere, reuse it.
    - If it's in the wrong category, move it.
    - If overwrites are given, apply them (update perms).
    """
    channel = get(guild.text_channels, name=name)
    if channel is None:
        if overwrites is not None:
            channel = await guild.create_text_channel(
                name=name,
                category=category,
                overwrites=overwrites
            )
        else:
            channel = await guild.create_text_channel(
                name=name,
                category=category
            )
        print(f"Created text channel: {name}")
    else:
        kwargs = {}
        if channel.category != category:
            kwargs["category"] = category
        if overwrites is not None:
            kwargs["overwrites"] = overwrites
        if kwargs:
            try:
                await channel.edit(**kwargs)
                print(f"Updated existing text channel: {name}")
            except discord.HTTPException as e:
                print(f"Couldn't edit text channel {name}: {e}")
        else:
            print(f"Using existing text channel: {name}")
    return channel


async def get_or_create_voice_channel(guild, category, name, overwrites=None):
    """
    Get or create a voice channel.
    - If it exists anywhere, reuse it.
    - If it's in the wrong category, move it.
    - If overwrites are given, apply them (update perms).
    """
    channel = get(guild.voice_channels, name=name)
    if channel is None:
        if overwrites is not None:
            channel = await guild.create_voice_channel(
                name=name,
                category=category,
                overwrites=overwrites
            )
        else:
            channel = await guild.create_voice_channel(
                name=name,
                category=category
            )
        print(f"Created voice channel: {name}")
    else:
        kwargs = {}
        if channel.category != category:
            kwargs["category"] = category
        if overwrites is not None:
            kwargs["overwrites"] = overwrites
        if kwargs:
            try:
                await channel.edit(**kwargs)
                print(f"Updated existing voice channel: {name}")
            except discord.HTTPException as e:
                print(f"Couldn't edit voice channel {name}: {e}")
        else:
            print(f"Using existing voice channel: {name}")
    return channel


def get_user_data(user_id: int):
    """Ensure xp_data entry exists and return it."""
    uid = str(user_id)
    info = xp_data.get(uid, {})
    if "xp" not in info:
        info["xp"] = 0
    if "level" not in info:
        info["level"] = 0
    if "coins" not in info:
        info["coins"] = 0
    if "strikes" not in info:
        info["strikes"] = 0
    xp_data[uid] = info
    return info


# ---------- EMBED STYLE HELPERS ----------

def build_embed(kind="info", title=None, description=None):
    """
    kind: 'info', 'success', 'error', 'warning', 'live'
    """
    colors = {
        "info": discord.Color.blurple(),
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.gold(),
        "live": discord.Color.from_rgb(254, 44, 85),  # TikTok style
    }
    color = colors.get(kind, discord.Color.blurple())
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Chris2stickyy's Lab 🧪")
    # Time + date on every embed
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_live_embed(message, tiktok_name=None, author=None):
    """Clean, branded live embed for !golive."""
    embed = build_embed(
        kind="live",
        title="🔴 CHRIS2STICKYY IS LIVE!",
        description=message
    )

    embed.add_field(name="📺 Platform", value="TikTok Live", inline=True)

    if tiktok_name:
        embed.add_field(
            name="🔗 Watch Now",
            value=f"[Tap to join](https://tiktok.com/@{tiktok_name}/live)",
            inline=True
        )

    if author:
        embed.add_field(
            name="👤 Going Live",
            value=author.mention,
            inline=False
        )

    return embed


async def get_modlog_channel(guild: discord.Guild):
    """Get or create the 📂┃mod-logs channel."""
    channel = get(guild.text_channels, name="📂┃mod-logs")
    if channel:
        return channel

    staff_cat = get(guild.categories, name="🔧┃Lab Control Room")
    if staff_cat is None:
        staff_cat = await guild.create_category("🔧┃Lab Control Room")

    everyone = guild.default_role
    lab_owner_role = get(guild.roles, name="👑 Lab Owner")
    lab_tech_role = get(guild.roles, name="🧪 Lab Tech")

    staff_only = {
        everyone: discord.PermissionOverwrite(view_channel=False),
    }
    if lab_owner_role:
        staff_only[lab_owner_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    if lab_tech_role:
        staff_only[lab_tech_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    channel = await guild.create_text_channel(
        name="📂┃mod-logs",
        category=staff_cat,
        overwrites=staff_only
    )
    return channel


async def log_to_modlogs(guild: discord.Guild, embed: discord.Embed):
    try:
        ch = await get_modlog_channel(guild)
        if ch:
            await ch.send(embed=embed)
    except Exception as e:
        print(f"Error logging to mod-logs: {e}")


async def log_bot_status_all_guilds(kind: str, title: str, description: str):
    """
    Send a simple status embed to #📂┃mod-logs in every guild.
    Used for startup / reconnect logs.
    """
    for guild in bot.guilds:
        try:
            embed = build_embed(kind=kind, title=title, description=description)
            await log_to_modlogs(guild, embed)
        except Exception as e:
            print(f"Error logging bot status in {guild.name}: {e}")


# ---------- XP / LEVEL HELPERS ----------

def add_xp(user_id: int, amount: int):
    """
    Give XP to a user and handle level-ups.
    Returns: (xp, level, leveled_up: bool, old_level)
    """
    global xp_data
    uid = str(user_id)
    user_info = get_user_data(user_id)

    # Add XP
    user_info["xp"] = user_info.get("xp", 0) + amount
    old_level = user_info.get("level", 0)

    # Level formula: every 100 XP = 1 level
    new_level = user_info["xp"] // 100
    leveled_up = new_level > old_level

    if leveled_up:
        user_info["level"] = new_level

    xp_data[uid] = user_info
    save_config()
    return user_info["xp"], user_info.get("level", 0), leveled_up, old_level


def add_strike(user_id: int):
    """Add a moderation strike to a user and save."""
    info = get_user_data(user_id)
    info["strikes"] = info.get("strikes", 0) + 1
    xp_data[str(user_id)] = info
    save_config()
    return info["strikes"]


# ---------- STAFF-ONLY CHECK ----------

def is_lab_staff():
    """Only allow 👑 Lab Owner and 🧪 Lab Tech (or Admins if roles not created yet)."""
    async def predicate(ctx):
        if not ctx.guild:
            raise commands.CheckFailure("No guild")

        lab_owner = get(ctx.guild.roles, name="👑 Lab Owner")
        lab_tech = get(ctx.guild.roles, name="🧪 Lab Tech")

        # If roles don't exist yet, allow server admins to run setup
        if not lab_owner and not lab_tech:
            if ctx.author.guild_permissions.administrator:
                return True

        if (lab_owner and lab_owner in ctx.author.roles) or (lab_tech and lab_tech in ctx.author.roles):
            return True

        raise commands.CheckFailure("Not lab staff")

    return commands.check(predicate)


def is_staff_member(member: discord.Member) -> bool:
    """
    Treat Lab Owner / Lab Tech / Admins as staff for auto-mod exemptions
    (for spam/caps/link filters). They are still subject to hard-banned words.
    """
    guild = member.guild
    lab_owner = get(guild.roles, name="👑 Lab Owner")
    lab_tech = get(guild.roles, name="🧪 Lab Tech")

    if lab_owner and lab_owner in member.roles:
        return True
    if lab_tech and lab_tech in member.roles:
        return True

    perms = member.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_messages:
        return True

    return False


def is_new_account(member: discord.Member) -> bool:
    """
    Returns True if the Discord account is younger than NEW_ACCOUNT_MIN_DAYS.
    """
    now = discord.utils.utcnow()
    age = now - member.created_at
    return age.days < NEW_ACCOUNT_MIN_DAYS


@bot.event
async def on_command_error(ctx, error):
    # Already handled in some commands
    if isinstance(error, commands.CheckFailure):
        embed = build_embed(
            kind="error",
            title="⛔ Command Locked",
            description="Only **Lab Owner** and **Lab Techs** can use this command."
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = build_embed(
            kind="error",
            title="❌ Missing Arguments",
            description="You're missing some info for that command. Try running `!help` for usage."
        )
        await ctx.send(embed=embed)
    else:
        # Optionally log other errors
        print(f"Unhandled error: {error}")


