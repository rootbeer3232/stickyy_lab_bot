from .shared import *
from .commands_setup import VerificationView

# ---------- MOD-LOGS FOR EDITED MESSAGES ----------

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Ignore bot edits
    if before.author.bot:
        return

    # Only log server messages (not DMs)
    if not before.guild:
        return

    # If content didn't actually change (only embed or pin change), skip
    if before.content == after.content:
        return

    embed = build_embed(
        kind="info",
        title="✏️ Message Edited",
        description=f"A message was edited in {before.channel.mention}"
    )

    embed.add_field(name="Author", value=before.author.mention, inline=True)
    embed.add_field(name="Channel", value=before.channel.mention, inline=True)

    before_text = before.content or "*No content*"
    after_text = after.content or "*No content*"

    # Safety: keep fields from getting too massive
    if len(before_text) > 1000:
        before_text = before_text[:1000] + "..."
    if len(after_text) > 1000:
        after_text = after_text[:1000] + "..."

    embed.add_field(name="Before", value=before_text, inline=False)
    embed.add_field(name="After", value=after_text, inline=False)

    await log_to_modlogs(before.guild, embed)


# ---------- MOD-LOGS FOR DELETED MESSAGES ----------

@bot.event
async def on_message_delete(message):
    # ignore bot deletes & bot messages
    if message.author.bot:
        return

    if not message.guild:
        return

    embed = build_embed(
        kind="warning",
        title="🗑️ Message Deleted",
        description=f"A message was deleted in {message.channel.mention}"
    )

    embed.add_field(name="Author", value=message.author.mention, inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)

    content = message.content or "*No content*"
    if len(content) > 1000:
        content = content[:1000] + "..."

    embed.add_field(
        name="Message Content",
        value=content,
        inline=False
    )

    await log_to_modlogs(message.guild, embed)

    # ---------- GHOST PING DETECTION (2 warnings then strike) ----------
    if message.mentions and not message.author.bot:
        try:
            user = message.author
            uid = str(user.id)

            # Track ghost ping count in xp_data
            user_info = get_user_data(user.id)
            gp_count = user_info.get("ghost_pings", 0) + 1
            user_info["ghost_pings"] = gp_count
            xp_data[uid] = user_info
            save_config()

            # ---------------------------------------
            # 1–2 = warning, 3rd = strike
            # ---------------------------------------
            if gp_count <= 2:
                # Warning only
                warn_embed = build_embed(
                    kind="warning",
                    title="👻 Ghost Ping Detected",
                    description=(
                        f"{user.mention}, you deleted a message that mentioned "
                        f"{', '.join(m.mention for m in message.mentions)}."
                    )
                )
                warn_embed.add_field(
                    name="Message Content",
                    value=censor_banned_words(message.content) or "*No content*",
                    inline=False
                )
                warn_embed.add_field(
                    name="Warning",
                    value=f"This is ghost ping warning **{gp_count}/2**.\n"
                          f"On the 3rd ghost ping, you will receive a **strike**.",
                    inline=False
                )

                await message.channel.send(embed=warn_embed, delete_after=25)

                action_note = f"Warning {gp_count}/2"

            else:
                # 3rd ghost ping → strike added
                strikes = add_strike(user.id)

                strike_embed = build_embed(
                    kind="error",
                    title="👻 Ghost Ping – Strike Issued",
                    description=f"{user.mention} continued ghost pinging after two warnings."
                )
                strike_embed.add_field(
                    name="Message Content",
                    value=censor_banned_words(message.content) or "*No content*",
                    inline=False
                )
                strike_embed.add_field(
                    name="Strike Count",
                    value=f"`{strikes}`",
                    inline=False
                )
                strike_embed.add_field(
                    name="Reason",
                    value="Repeated ghost pinging after warnings.",
                    inline=False
                )

                await message.channel.send(embed=strike_embed, delete_after=30)

                action_note = f"Strike given (ghost ping offense #{gp_count})"

            # ---------- LOG TO MOD-LOGS ----------
            log_embed = build_embed(
                kind="warning",
                title="👻 Ghost Ping Logged",
                description="A deleted message contained mentions."
            )
            log_embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
            log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)

            mentioned_users = ", ".join(f"{m} (`{m.id}`)" for m in message.mentions)
            log_embed.add_field(name="Mentioned Users", value=mentioned_users, inline=False)

            content = message.content or "*No content*"
            if len(content) > 1000: 
                content = content[:1000] + "..."
            log_embed.add_field(name="Message Content", value=content, inline=False)

            log_embed.add_field(name="Action Taken", value=action_note, inline=False)

            await log_to_modlogs(message.guild, log_embed)

        except Exception as e:
            print(f"Ghost ping detection error: {e}")



# ---------- MOD-LOGS FOR ROLE UPDATES ----------

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # Ignore bots
    if after.bot:
        return

    guild = after.guild
    if not guild:
        return

    # Compare roles before and after
    before_roles = set(before.roles)
    after_roles = set(after.roles)

    added_roles = after_roles - before_roles
    removed_roles = before_roles - after_roles

    # Don't count @everyone
    everyone = guild.default_role
    if everyone in added_roles:
        added_roles.remove(everyone)
    if everyone in removed_roles:
        removed_roles.remove(everyone)

    # If no actual change in roles, skip
    if not added_roles and not removed_roles:
        return

    embed = build_embed(
        kind="info",
        title="🎭 Roles Updated",
        description=f"Roles updated for {after.mention}"
    )

    # Build nice text lists
    if added_roles:
        added_text = ", ".join(r.mention for r in added_roles)
    else:
        added_text = "`None`"

    if removed_roles:
        removed_text = ", ".join(r.mention for r in removed_roles)
    else:
        removed_text = "`None`"

    embed.add_field(name="Roles Added", value=added_text, inline=False)
    embed.add_field(name="Roles Removed", value=removed_text, inline=False)

    # Optional: show avatar
    try:
        embed.set_thumbnail(url=after.display_avatar.url)
    except Exception:
        pass

    await log_to_modlogs(guild, embed)


# ---------- MOD-LOGS FOR MEMBER JOIN ----------

@bot.event
async def on_member_join(member):
    """Welcome new members, prompt verification, and log join."""
    # DM welcome
    try:
        dm_embed = build_embed(
            kind="info",
            title="👋 Welcome to Chris2stickyy's Lab!",
            description=(
                "Thanks for joining the Lab!\n\n"
                "1️⃣ Go to the **verification channel** in the server.\n"
                "2️⃣ Click **Verify Me** to unlock the channels.\n"
                "3️⃣ Grab your roles in 🎭┃roles and start chatting."
            )
        )
        await member.send(embed=dm_embed)
    except Exception:
        pass

    # Post a small welcome in the verification channel (if enabled)
    if verification_enabled and verification_channel_id:
        verify_channel = bot.get_channel(verification_channel_id)
        if verify_channel:
            welcome_embed = build_embed(
                kind="info",
                title=f"👋 Welcome {member.name}!",
                description=f"Welcome to **Chris2stickyy's Lab**! Please verify to access the server."
            )
            await verify_channel.send(
                f"{member.mention}",
                embed=welcome_embed,
                delete_after=30
            )

    # ---------- MOD-LOG: JOIN + ACCOUNT AGE ----------
    try:
        now = discord.utils.utcnow()
        account_age = now - member.created_at
        days_old = account_age.days
        age_text = f"{days_old} day(s) old"

        if days_old < 1:
            flag = "⚠ Account is less than **24 hours** old."
        elif days_old < 7:
            flag = "⚠ New account (under **7 days** old)."
        else:
            flag = "✅ Account older than 7 days."

        # New: auto-tag very new accounts with the New Account role
        new_account_status = "Not flagged as new"
        if is_new_account(member):
            try:
                new_role = await get_or_create_role(
                    member.guild,
                    NEW_ACCOUNT_ROLE_NAME,
                    colour=discord.Colour.dark_grey()
                )
                await member.add_roles(new_role, reason=f"Account under {NEW_ACCOUNT_MIN_DAYS} days old")
                new_account_status = f"New Account role applied (under {NEW_ACCOUNT_MIN_DAYS} days)."
            except Exception as e:
                print(f"Failed to assign New Account role: {e}")
                new_account_status = "Attempted to assign New Account role, but failed."

        log_embed = build_embed(
            kind="info",
            title="✅ Member Joined",
            description=f"{member.mention} joined the server."
        )

        log_embed.add_field(
            name="User",
            value=f"{member} (`{member.id}`)",
            inline=False
        )
        log_embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            inline=True
        )
        log_embed.add_field(
            name="Account Age",
            value=f"{age_text}\n{flag}",
            inline=True
        )
        log_embed.add_field(
            name="New Account Status",
            value=new_account_status,
            inline=False
        )
        log_embed.add_field(
            name="Member Count",
            value=str(member.guild.member_count),
            inline=False
        )

        try:
            log_embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

        await log_to_modlogs(member.guild, log_embed)
    except Exception as e:
        print(f"Failed to log member join: {e}")



# ---------- MOD-LOGS FOR MEMBER LEAVE ----------

@bot.event
async def on_member_remove(member):
    """Log when a member leaves / is kicked / is banned."""
    guild = member.guild
    if not guild:
        return

    try:
        now = discord.utils.utcnow()
        account_age = now - member.created_at
        days_old = account_age.days
        age_text = f"{days_old} day(s) old"

        # Flag for suspiciously new accounts
        if days_old < 1:
            flag = "⚠ Account is less than **24 hours** old."
        elif days_old < 7:
            flag = "⚠ New account (under **7 days** old)."
        else:
            flag = "✅ Account older than 7 days."

        log_embed = build_embed(
            kind="warning",
            title="🚪 Member Left",
            description=f"{member} has left the server."
        )

        log_embed.add_field(
            name="User",
            value=f"{member} (`{member.id}`)",
            inline=False
        )
        log_embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            inline=True
        )
        log_embed.add_field(
            name="Account Age",
            value=f"{age_text}\n{flag}",
            inline=True
        )
        log_embed.add_field(
            name="Member Count",
            value=str(guild.member_count),
            inline=False
        )

        try:
            log_embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

        await log_to_modlogs(guild, log_embed)
    except Exception as e:
        print(f"Failed to log member leave: {e}")


# ---------- BOT READY / CONNECTION EVENTS ----------

@bot.event
async def on_ready():
    global BOOT_TIME

    # Load saved configuration
    load_config()

    # Re-register the persistent verification button view
    if verification_enabled:
        bot.add_view(VerificationView())

    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Chris2stickyy's Lab 🧪 | !help"
        )
    )

    BOOT_TIME = discord.utils.utcnow()

    # Log startup / restart to mod-logs in every guild
    started_str = BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S UTC")
    await log_bot_status_all_guilds(
        kind="success",
        title="🤖 Bot Online",
        description=f"Bot started or restarted at `{started_str}`."
    )

    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Ready to build: Chris2stickyy's Lab")
    print("------")


@bot.event
async def on_resumed():
    """
    Called when the bot successfully resumes a lost WebSocket connection.
    Log this to mod-logs so staff can see when the bot came back after a hiccup.
    """
    resumed_at = discord.utils.utcnow()
    resumed_str = resumed_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    await log_bot_status_all_guilds(
        kind="info",
        title="🔄 Bot Connection Resumed",
        description=f"Discord connection was resumed at `{resumed_str}`."
    )
    print("Connection to Discord resumed")
