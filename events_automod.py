from shared import *

# ---------- XP GAIN + AUTO-MOD ON MESSAGE ----------

async def handle_auto_violation(
    message: discord.Message,
    *,
    reason: str,
    rule_label: str
):
    """
    Core auto-mod handler:
    - deletes the message
    - applies strike ladder
    - posts public embed
    - DMs user
    - logs to mod-logs

    Used by:
      - hard-banned words
      - anti-spam
      - caps filter
      - link/invite filter
    """
    if not message.guild:
        return

    user = message.author
    guild = message.guild

    # Delete message
    try:
        await message.delete()
    except Exception as e:
        print(f"Failed to delete bad message: {e}")

    strikes = add_strike(user.id)
    muted_role = get(guild.roles, name="🔇 Muted")

    # Default action text
    action_text = ""

    if strikes == 1:
        action_text = "Warning issued (1st strike)."
    elif strikes == 2:
        # Mute with role
        if muted_role:
            try:
                await user.add_roles(muted_role, reason=f"Auto-moderation ({rule_label}): 2nd strike")
            except Exception as e:
                print(f"Failed to add muted role: {e}")
        action_text = "User auto-muted (2nd strike)."
    elif strikes == 3:
        # Kick
        try:
            await guild.kick(user, reason=f"Auto-moderation ({rule_label}): 3rd strike")
            action_text = "User auto-kicked (3rd strike)."
        except Exception as e:
            print(f"Failed to kick: {e}")
            action_text = "Tried to kick user (3rd strike), but lacked permission."
    else:
        # Ban
        try:
            await guild.ban(user, reason=f"Auto-moderation ({rule_label}): repeated strikes")
            action_text = "User auto-banned (4th strike+)."
        except Exception as e:
            print(f"Failed to ban: {e}")
            action_text = "Tried to ban user (4th strike+), but lacked permission."

    # Always censor banned words so we never re-post slurs in embeds/logs
    censored = censor_banned_words(message.content)

    # PUBLIC CHANNEL NOTICE
    try:
        public_embed = build_embed(
            kind="warning",
            title="🛡️ Message Removed by Auto-Moderation",
            description=f"{user.mention}, your message violated server rules."
        )

        public_embed.add_field(
            name="Rule",
            value=rule_label,
            inline=True
        )

        public_embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )

        public_embed.add_field(
            name="Your Message",
            value=censored or "*No content*",
            inline=False
        )

        public_embed.add_field(
            name="Strike Count",
            value=f"`{strikes}`",
            inline=True
        )

        public_embed.add_field(
            name="Action Taken",
            value=action_text or "Warning",
            inline=True
        )

        await message.channel.send(embed=public_embed, delete_after=30)

    except Exception as e:
        print(f"Failed to send public auto-mod message: {e}")

    # DM user (if possible)
    try:
        dm_embed = build_embed(
            kind="error",
            title="🛡️ Message Blocked by Auto-Moderation",
            description=(
                "Your message was removed for breaking server rules.\n"
                "Repeated violations can lead to mutes, kicks, or bans."
            )
        )
        dm_embed.add_field(name="Rule", value=rule_label, inline=False)
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Your Message", value=censored or "*No content*", inline=False)
        dm_embed.add_field(name="Strike Count", value=f"`{strikes}`", inline=False)
        dm_embed.add_field(name="Action Taken", value=action_text or "Warning", inline=False)
        await user.send(embed=dm_embed)
    except Exception:
        pass

    # Log to mod-logs
    log_embed = build_embed(
        kind="error",
        title="🛡️ Auto-Moderation Triggered",
        description=f"A message by {user.mention} was blocked."
    )
    log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    log_embed.add_field(name="Rule", value=rule_label, inline=True)
    log_embed.add_field(name="Strikes", value=f"`{strikes}`", inline=True)
    content_preview = (message.content[:200] + "...") if len(message.content) > 200 else message.content
    log_embed.add_field(name="Message Content", value=content_preview or "*No content*", inline=False)
    log_embed.add_field(name="Action", value=action_text or "Warning", inline=False)

    await log_to_modlogs(guild, log_embed)


async def handle_bad_message(message: discord.Message):
    """Wrapper kept for hard-banned words; uses shared handler."""
    await handle_auto_violation(
        message,
        reason="Use of hard-banned word(s).",
        rule_label="BANNED_WORD"
    )

async def check_new_account_restrictions(message: discord.Message) -> bool:
    """
    Limits where very new accounts can talk.

    Returns True if the message was deleted & handled.
    """
    if not message.guild:
        return False

    author = message.author

    # Staff are exempt
    if is_staff_member(author):
        return False

    # Only care about human users
    if author.bot:
        return False

    # If their account is not considered "new", let them talk freely
    if not is_new_account(author):
        return False

    # If the channel is in the allowed list, let it through
    if message.channel.name in NEW_ACCOUNT_ALLOWED_CHANNELS:
        return False

    # Otherwise, delete and warn
    try:
        await message.delete()
    except Exception as e:
        print(f"Failed to delete message in new-account filter: {e}")

    # Friendly notice in-channel (short-lived)
    try:
        notice = build_embed(
            kind="warning",
            title="🛡️ New Account Restrictions",
            description=(
                f"{author.mention}, your Discord account is very new, so you are currently "
                f"limited to a few channels until your account is at least **{NEW_ACCOUNT_MIN_DAYS} days** old "
                "or staff manually review you.\n\n"
                "You can talk in: "
                + ", ".join(f"`{name}`" for name in NEW_ACCOUNT_ALLOWED_CHANNELS)
            )
        )
        await message.channel.send(embed=notice, delete_after=25)
    except Exception as e:
        print(f"Failed to send new-account notice message: {e}")

    # DM them too (if possible)
    try:
        dm_embed = build_embed(
            kind="info",
            title="👋 Welcome to the Lab (New Account Detected)",
            description=(
                "Your Discord account is very new, so we temporarily limit where you can send messages "
                f"to help protect the server from spam and raids.\n\n"
                f"Once your account is at least **{NEW_ACCOUNT_MIN_DAYS} days** old (or staff review your account), "
                "these limits can be lifted."
            )
        )
        dm_embed.add_field(
            name="Where you can talk right now",
            value=", ".join(f"`{name}`" for name in NEW_ACCOUNT_ALLOWED_CHANNELS),
            inline=False
        )
        await author.send(embed=dm_embed)
    except Exception:
        pass

    # Log to mod-logs
    log_embed = build_embed(
        kind="warning",
        title="🛡️ New Account Message Blocked",
        description=f"A message from a **new account** was blocked outside allowed channels."
    )
    log_embed.add_field(name="User", value=f"{author.mention} (`{author.id}`)", inline=False)
    log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    content_preview = message.content or "*No content*"
    if len(content_preview) > 500:
        content_preview = content_preview[:500] + "..."
    log_embed.add_field(name="Message Content", value=content_preview, inline=False)
    log_embed.add_field(
        name="Reason",
        value=f"Account younger than {NEW_ACCOUNT_MIN_DAYS} days; channel not in NEW_ACCOUNT_ALLOWED_CHANNELS.",
        inline=False
    )

    await log_to_modlogs(message.guild, log_embed)

    return True


# ---------- PING SPAM PROTECTION ----------


async def check_anti_spam(message: discord.Message) -> bool:
    """
    Simple message flood protection.
    Returns True if the message was deleted & punished.
    """
    if not message.guild:
        return False

    # Staff are exempt from spam filter (still hit by hard-banned words)
    if is_staff_member(message.author):
        return False

    # Don't track empty messages
    content = message.content or ""
    if not content.strip():
        return False

    guild_id = message.guild.id
    user_id = message.author.id
    now = time.time()

    user_deque = spam_tracker[guild_id][user_id]
    user_deque.append(now)

    # Drop timestamps older than the spam window
    while user_deque and now - user_deque[0] > SPAM_WINDOW_SECONDS:
        user_deque.popleft()

    # Too many messages in the time window
    if len(user_deque) > SPAM_MESSAGE_LIMIT:
        await handle_auto_violation(
            message,
            reason=(
                f"Sending too many messages in {SPAM_WINDOW_SECONDS} seconds "
                f"({len(user_deque)} messages)."
            ),
            rule_label="SPAM"
        )
        # Clear so they don't instantly re-trigger on next message
        user_deque.clear()
        return True

    return False


async def check_caps_filter(message: discord.Message) -> bool:
    """
    Block messages that are mostly ALL CAPS (shouting).
    Returns True if the message was deleted & punished.
    """
    if not message.guild:
        return False

    # Staff exempt from caps filter
    if is_staff_member(message.author):
        return False

    content = message.content or ""
    if len(content) < MIN_CAPS_LENGTH:
        # too short to care
        return False

    # Only look at letters
    letters = [c for c in content if c.isalpha()]
    if not letters:
        return False

    caps_count = sum(1 for c in letters if c.isupper())
    total_letters = len(letters)
    caps_ratio = caps_count / total_letters

    if caps_ratio >= MAX_CAPS_RATIO:
        percent = int(caps_ratio * 100)
        await handle_auto_violation(
            message,
            reason=f"Too much ALL CAPS in one message ({percent}% of letters are uppercase).",
            rule_label="ALL_CAPS"
        )
        return True

    return False

async def check_link_filter(message: discord.Message) -> bool:
    """
    Blocks links / Discord invites outside approved channels.
    Returns True if the message was deleted & punished.
    """
    if not message.guild:
        return False

    # Staff exempt from link filter (still hit by hard-banned words)
    if is_staff_member(message.author):
        return False

    content = message.content or ""
    if not content:
        return False

    # If this channel is allowed for links, skip the filter
    if message.channel.name in LINK_ALLOWED_CHANNEL_NAMES:
        return False

    # If no link / invite detected, nothing to do
    if not LINK_REGEX.search(content):
        return False

    await handle_auto_violation(
        message,
        reason="Links and invites are not allowed in this channel.",
        rule_label="LINK_SPAM"
    )
    return True


async def check_ping_spam(message: discord.Message) -> bool:
    """
    Returns True if the message was deleted & punished.

    Two ways to trigger:
      1) Too many mentions in a single message.
      2) Too many 'ping-heavy' messages in a short time window.

    Uses the same strike ladder + public embed + DM + mod-log
    via handle_auto_violation().
    """
    if not message.guild:
        return False

    # Staff are exempt from ping spam filter (but still hit by hard-banned words)
    if is_staff_member(message.author):
        return False

    content = message.content or ""
    if not content:
        return False

    # ----- Count mentions in this message -----
    # We treat:
    #   • unique mentioned users
    #   • unique mentioned roles
    #   • @everyone / @here as a heavy ping (counts as 3)
    mention_count = 0

    # Distinct users
    mention_count += len(message.mentions)

    # Distinct roles
    mention_count += len(message.role_mentions)

    # @everyone / @here
    if message.mention_everyone:
        mention_count += 3

    # 1) Too many mentions in a single message
    if mention_count >= MAX_MENTIONS_PER_MESSAGE:
        await handle_auto_violation(
            message,
            reason=f"Too many mentions in a single message ({mention_count} mentions).",
            rule_label="PING_SPAM"
        )
        return True

    # If there are no mentions, no need to track for ping spam burst
    if mention_count == 0:
        return False

    # 2) Burst of ping-heavy messages over time
    guild_id = message.guild.id
    user_id = message.author.id
    now = time.time()

    user_deque = ping_tracker[guild_id][user_id]
    user_deque.append(now)

    # Remove timestamps outside the ping spam window
    while user_deque and now - user_deque[0] > PING_WINDOW_SECONDS:
        user_deque.popleft()

    # If user has sent too many ping-heavy messages in the window, punish
    if len(user_deque) > MAX_PING_MESSAGES_IN_WINDOW:
        await handle_auto_violation(
            message,
            reason=(
                f"Too many ping-heavy messages in {PING_WINDOW_SECONDS} seconds "
                f"({len(user_deque)} messages with mentions)."
            ),
            rule_label="PING_SPAM"
        )
        # Clear so they don't instantly re-trigger
        user_deque.clear()
        return True

    return False



@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return

    # -------- HARD-BANNED WORDS (highest priority) --------
    if message.guild:
        content_lower = message.content.lower()
        if any(bad for bad in BANNED_WORDS if bad and bad.lower() in content_lower):
            await handle_bad_message(message)
            return  # Do not give XP or process commands for blocked message

        # -------- NEW ACCOUNT RESTRICTIONS --------
        # If a very new account talks in a restricted channel, block it.
        if await check_new_account_restrictions(message):
            return

        # -------- ANTI-SPAM / PING SPAM / CAPS / LINK FILTERS --------
        # If any of these delete the message, we stop there.

        # Generic message-count spam
        if await check_anti_spam(message):
            return

        # New: Ping spam (too many mentions or ping bursts)
        if await check_ping_spam(message):
            return

        # Caps lock / shouting
        if await check_caps_filter(message):
            return

        # Link / invite filter
        if await check_link_filter(message):
            return


    # -------- XP GAIN --------
    # Give XP only in guild text channels with at least a little content
    if message.guild and isinstance(message.channel, discord.TextChannel):
        content = message.content.strip()
        if len(content) >= 3:
            xp, level, leveled_up, old_level = add_xp(message.author.id, 10)
            if leveled_up:
                lvl_embed = build_embed(
                    kind="success",
                    title="⭐ Level Up!",
                    description=f"{message.author.mention} reached **Level {level}**!"
                )
                await message.channel.send(embed=lvl_embed, delete_after=20)

    # -------- COMMAND HANDLING --------
    await bot.process_commands(message)


