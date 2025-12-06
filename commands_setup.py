from .shared import *

# ---------- TICKET HELPERS ----------

async def open_ticket(ctx, details: str, is_report: bool):
    """Create (or reuse) a private ticket channel for this user."""
    guild = ctx.guild
    if not guild:
        await ctx.send("This command only works in the server.")
        return

    lab_owner = get(guild.roles, name="👑 Lab Owner")
    lab_tech = get(guild.roles, name="🧪 Lab Tech")

    # Get or create ticket category
    ticket_category = get(guild.categories, name=TICKET_CATEGORY_NAME)
    if ticket_category is None:
        ticket_category = await guild.create_category(TICKET_CATEGORY_NAME)
        print(f"Created ticket category: {TICKET_CATEGORY_NAME}")

    # See if user already has an open ticket in this category
    existing_channel = None
    for ch in ticket_category.text_channels:
        if ch.topic and f"user_id:{ctx.author.id}" in ch.topic:
            existing_channel = ch
            break

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True
        )
    }
    if lab_owner:
        overwrites[lab_owner] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            manage_channels=True
        )
    if lab_tech:
        overwrites[lab_tech] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True
        )

    if existing_channel:
        ticket_channel = existing_channel
        created = False
    else:
        # Clean channel name
        base_name = f"ticket-{ctx.author.name}".lower()
        safe_name = "".join(c for c in base_name if c.isalnum() or c in "-")[:90]
        topic_text = f"{'Report' if is_report else 'Support'} ticket | user_id:{ctx.author.id}"

        ticket_channel = await guild.create_text_channel(
            name=safe_name,
            category=ticket_category,
            overwrites=overwrites,
            topic=topic_text
        )
        created = True

    # Build ticket embed
    embed = build_embed(
        kind="warning" if is_report else "info",
        title="🚨 New Report" if is_report else "💬 Help Request",
        description=details
    )
    embed.add_field(name="From", value=ctx.author.mention, inline=True)
    embed.add_field(name="Opened From", value=ctx.channel.mention, inline=True)

    staff_ping = " ".join(
        r.mention for r in [lab_owner, lab_tech] if r is not None
    )

    await ticket_channel.send(content=staff_ping or None, embed=embed)

    # Log to mod-logs
    log_embed = build_embed(
        kind="warning" if is_report else "info",
        title="📂 Ticket Opened",
        description=f"Type: {'Report' if is_report else 'Support'}"
    )
    log_embed.add_field(name="User", value=ctx.author.mention, inline=True)
    log_embed.add_field(name="Channel", value=ticket_channel.mention, inline=True)
    await log_to_modlogs(guild, log_embed)

    confirm = build_embed(
        kind="success",
        title="✅ Ticket Opened" if created else "✅ Ticket Updated",
        description=(
            f"{'A new' if created else 'Your'} ticket is in {ticket_channel.mention}.\n\n"
            "Only **you** and **Lab Staff** can see it."
        )
    )
    await ctx.send(embed=confirm, delete_after=25)


# ---------- SETUP COMMAND ----------

@bot.command(name="setup_lab")
@is_lab_staff()
async def setup_lab(ctx):
    guild = ctx.guild

    # Send initial embed
    setup_embed = build_embed(
        kind="info",
        title="🧪 Setting Up Chris2stickyy's Lab",
        description="Creating categories, channels, roles, and permissions..."
    )
    setup_embed.set_footer(text="This may take a moment...")
    status_msg = await ctx.send(embed=setup_embed)

    # ---- ROLES ----
    # Brand roles
    lab_owner_role = await get_or_create_role(
        guild, "👑 Lab Owner", colour=discord.Colour.gold()
    )
    lab_tech_role = await get_or_create_role(
        guild, "🧪 Lab Tech", colour=discord.Colour.green()
    )
    test_subject_role = await get_or_create_role(
        guild, "🧬 Test Subject", colour=discord.Colour.purple()
    )

    # Functional roles
    notif_role = await get_or_create_role(
        guild, "📣 Notifications", colour=discord.Colour.orange()
    )
    ps5_role = await get_or_create_role(
        guild, "🎮 PS5", colour=discord.Colour.blue()
    )
    xbox_role = await get_or_create_role(
        guild, "🎮 Xbox", colour=discord.Colour.dark_green()
    )
    pc_role = await get_or_create_role(
        guild, "🎮 PC", colour=discord.Colour.dark_blue()
    )

    # New special roles
    og_role = await get_or_create_role(
        guild, "🥇 OG Day One", colour=discord.Colour.from_rgb(255, 215, 0)
    )
    nms_role = await get_or_create_role(
        guild, "📉 No Money Spent", colour=discord.Colour.dark_blue()
    )
    ptw_role = await get_or_create_role(
        guild, "💰 Paid to Win", colour=discord.Colour.dark_orange()
    )

    # Muted role for auto-moderation
    muted_role = await get_or_create_role(
        guild, "🔇 Muted", colour=discord.Colour.dark_grey()
    )

    # everyone role
    everyone = guild.default_role

    # Make the command user the Lab Owner if they don't have it yet
    if lab_owner_role not in ctx.author.roles:
        await ctx.author.add_roles(lab_owner_role, reason="Setup Lab command used")

    # ---- CATEGORIES ----
    info_cat = await get_or_create_category(guild, "📢┃Lab Info")
    mut_cat = await get_or_create_category(guild, "🧪┃MUT Lab")
    community_cat = await get_or_create_category(guild, "💬┃Lab Lounge")
    match_cat = await get_or_create_category(guild, "🏆┃Lab Matchmaking")
    stream_cat = await get_or_create_category(guild, "📺┃Stream Zone")
    voice_cat = await get_or_create_category(guild, "🔊┃Voice Channels")
    staff_cat = await get_or_create_category(guild, "🔧┃Lab Control Room")
    ticket_cat = await get_or_create_category(guild, TICKET_CATEGORY_NAME)

    # ---- PERMISSION TEMPLATES ----
    default_read_write = {
        everyone: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    read_only_staff_write = {
        everyone: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        lab_owner_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        lab_tech_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }

    staff_only = {
        everyone: discord.PermissionOverwrite(read_messages=False),
        lab_owner_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        lab_tech_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }

    # Tickets category: hidden by default, but channels themselves also have overwrites
    try:
        await ticket_cat.edit(overwrites={
            everyone: discord.PermissionOverwrite(view_channel=False),
            lab_owner_role: discord.PermissionOverwrite(view_channel=True),
            lab_tech_role: discord.PermissionOverwrite(view_channel=True),
        })
    except discord.HTTPException as e:
        print(f"Couldn't update ticket category overwrites: {e}")

    # ---- LAB INFO CHANNELS ----
    await get_or_create_text_channel(guild, info_cat, "👋┃welcome", read_only_staff_write)
    await get_or_create_text_channel(guild, info_cat, "📜┃rules", read_only_staff_write)
    await get_or_create_text_channel(guild, info_cat, "📢┃lab-announcements", read_only_staff_write)
    await get_or_create_text_channel(guild, info_cat, "🎭┃roles", default_read_write)
    await get_or_create_text_channel(guild, info_cat, "❓┃faq", default_read_write)

    # ---- MUT LAB CHANNELS ----
    await get_or_create_text_channel(guild, mut_cat, "📰┃mut-updates", default_read_write)
    await get_or_create_text_channel(guild, mut_cat, "💳┃card-drops", default_read_write)
    await get_or_create_text_channel(guild, mut_cat, "📋┃lineup-advice", default_read_write)
    await get_or_create_text_channel(guild, mut_cat, "💰┃coin-methods", read_only_staff_write)  # staff posts methods
    await get_or_create_text_channel(guild, mut_cat, "📈┃market-watch", default_read_write)
    await get_or_create_text_channel(guild, mut_cat, "📚┃gameplay-tips", default_read_write)

    # ---- LAB LOUNGE / COMMUNITY ----
    await get_or_create_text_channel(guild, community_cat, "💬┃general-chat", default_read_write)
    await get_or_create_text_channel(guild, community_cat, "🏈┃madden-chat", default_read_write)
    await get_or_create_text_channel(guild, community_cat, "🎞️┃clips-and-highlights", default_read_write)
    await get_or_create_text_channel(guild, community_cat, "😂┃memes", default_read_write)
    await get_or_create_text_channel(guild, community_cat, "🧬┃introduce-yourself", default_read_write)

    # ---- MATCHMAKING ----
    await get_or_create_text_channel(guild, match_cat, "⚔️┃head-to-head", default_read_write)
    await get_or_create_text_channel(guild, match_cat, "👥┃squads-lfg", default_read_write)
    await get_or_create_text_channel(guild, match_cat, "🏆┃tournaments", default_read_write)
    await get_or_create_text_channel(guild, match_cat, "📘┃league-info", default_read_write)
    await get_or_create_text_channel(guild, match_cat, "📝┃league-games", default_read_write)

    # ---- STREAM ZONE ----
    await get_or_create_text_channel(guild, stream_cat, "🔴┃live-notifications", read_only_staff_write)
    await get_or_create_text_channel(guild, stream_cat, "💭┃stream-chat", default_read_write)
    await get_or_create_text_channel(guild, stream_cat, "🎁┃giveaways", read_only_staff_write)
    await get_or_create_text_channel(guild, stream_cat, "💡┃suggestions", default_read_write)

    # ---- VOICE CHANNELS ----
    await get_or_create_voice_channel(guild, voice_cat, "🔊┃Lab Lobby")
    await get_or_create_voice_channel(guild, voice_cat, "🎮┃Game Chat 1")
    await get_or_create_voice_channel(guild, voice_cat, "🎮┃Game Chat 2")
    await get_or_create_voice_channel(guild, voice_cat, "🎥┃Watch Party")

    # ---- STAFF / CONTROL ROOM ----
    await get_or_create_text_channel(guild, staff_cat, "🔧┃staff-chat", staff_only)
    await get_or_create_text_channel(guild, staff_cat, "🚨┃reports", staff_only)
    await get_or_create_text_channel(guild, staff_cat, "📂┃mod-logs", staff_only)

    # ---- ADD CHANNEL DESCRIPTIONS (TOPICS) ----
    # Helper to safely set topic
    async def safe_set_topic(channel, topic):
        if channel is None:
            return
        try:
            await channel.edit(topic=topic)
        except discord.HTTPException as e:
            print(f"Couldn't set topic for {channel.name}: {e}")

    # Lab Info
    await safe_set_topic(get(guild.text_channels, name="👋┃welcome"),
                         "Welcome to Chris2stickyy's Lab! Start here and learn how the server works.")
    await safe_set_topic(get(guild.text_channels, name="📜┃rules"),
                         "Official server rules. Please read before chatting.")
    await safe_set_topic(get(guild.text_channels, name="📢┃lab-announcements"),
                         "Important Lab announcements, updates, and events.")
    await safe_set_topic(get(guild.text_channels, name="🎭┃roles"),
                         "Pick your roles here! Console roles, special roles, notifications, and more.")
    await safe_set_topic(get(guild.text_channels, name="❓┃faq"),
                         "Frequently asked questions about MUT & the Lab.")

    # MUT Lab
    await safe_set_topic(get(guild.text_channels, name="📰┃mut-updates"),
                         "Latest Madden 26 MUT updates, patches, and promo info.")
    await safe_set_topic(get(guild.text_channels, name="💳┃card-drops"),
                         "Stay updated on new LTDs, Legends, AKA, TOTW drops & reveals.")
    await safe_set_topic(get(guild.text_channels, name="📋┃lineup-advice"),
                         "Post your lineup and get improvement advice from the Lab.")
    await safe_set_topic(get(guild.text_channels, name="💰┃coin-methods"),
                         "Official coin-making methods (staff posted only).")
    await safe_set_topic(get(guild.text_channels, name="📈┃market-watch"),
                         "Market trends, sniping filters, and card pricing talk.")
    await safe_set_topic(get(guild.text_channels, name="📚┃gameplay-tips"),
                         "Offense, defense, meta—learn to dominate MUT.")

    # Community
    await safe_set_topic(get(guild.text_channels, name="💬┃general-chat"),
                         "General chat — hang out with the Lab community!")
    await safe_set_topic(get(guild.text_channels, name="🏈┃madden-chat"),
                         "Talk all things Madden 26 — gameplay, cards, tips.")
    await safe_set_topic(get(guild.text_channels, name="🎞️┃clips-and-highlights"),
                         "Post your clips, pack pulls, and highlights.")
    await safe_set_topic(get(guild.text_channels, name="😂┃memes"),
                         "Football & Madden memes only. Keep it fun.")
    await safe_set_topic(get(guild.text_channels, name="🧬┃introduce-yourself"),
                         "Introduce yourself — console, MUT level, playstyle, etc.")

    # Matchmaking
    await safe_set_topic(get(guild.text_channels, name="⚔️┃head-to-head"),
                         "Find opponents for friendly games. Use !queue / !leavequeue.")
    await safe_set_topic(get(guild.text_channels, name="👥┃squads-lfg"),
                         "Looking for group? Build squads and run games.")
    await safe_set_topic(get(guild.text_channels, name="🏆┃tournaments"),
                         "Lab tournaments, sign-ups, brackets, and winners.")
    await safe_set_topic(get(guild.text_channels, name="📘┃league-info"),
                         "MUT league info, rules, and team lists.")
    await safe_set_topic(get(guild.text_channels, name="📝┃league-games"),
                         "Schedule your league games, report scores, and recap matches.")

    # Stream Zone
    await safe_set_topic(get(guild.text_channels, name="🔴┃live-notifications"),
                         "Notifications when Chris2stickyy goes LIVE.")
    await safe_set_topic(get(guild.text_channels, name="💭┃stream-chat"),
                         "Chat during streams & interact with the community.")
    await safe_set_topic(get(guild.text_channels, name="🎁┃giveaways"),
                         "Giveaway announcements, rules, and winners.")
    await safe_set_topic(get(guild.text_channels, name="💡┃suggestions"),
                         "Suggest Lab ideas or stream content!")

    # Staff Channels
    await safe_set_topic(get(guild.text_channels, name="🔧┃staff-chat"),
                         "Private staff chat for Lab Techs & Owner.")
    await safe_set_topic(get(guild.text_channels, name="🚨┃reports"),
                         "Staff-only log of tickets and issues.")
    await safe_set_topic(get(guild.text_channels, name="📂┃mod-logs"),
                         "Auto-generated logs for moderation actions, wagers, and tickets.")

    # Ensure muted role cannot send in text channels
    for channel in guild.text_channels:
        try:
            await channel.set_permissions(
                muted_role,
                send_messages=False,
                add_reactions=False
            )
        except Exception as e:
            print(f"Couldn't set muted perms for {channel.name}: {e}")

    for vch in guild.voice_channels:
        try:
            await vch.set_permissions(
                muted_role,
                speak=False
            )
        except Exception as e:
            print(f"Couldn't set muted perms for {vch.name}: {e}")

    # If verification is already enabled, re-apply lock to new channels
    if verification_enabled and verified_role_id:
        verified_role = get(guild.roles, id=verified_role_id)
        if verified_role:
            everyone = guild.default_role
            staff_channels = ["🔧┃staff-chat", "🚨┃reports", "📂┃mod-logs"]
            read_only_channels = ["👋┃welcome", "📜┃rules", "📢┃lab-announcements", "💰┃coin-methods",
                                  "🔴┃live-notifications", "🎁┃giveaways"]

            for channel in guild.text_channels:
                if channel.name in staff_channels:
                    continue
                if channel.id == verification_channel_id:
                    continue
                try:
                    await channel.set_permissions(everyone, read_messages=False)
                    if channel.name in read_only_channels:
                        await channel.set_permissions(verified_role, read_messages=True)
                    else:
                        await channel.set_permissions(verified_role, read_messages=True, send_messages=True)
                except Exception as e:
                    print(f"Error updating permissions for {channel.name}: {e}")

            for channel in guild.voice_channels:
                try:
                    await channel.set_permissions(everyone, view_channel=False)
                    await channel.set_permissions(verified_role, view_channel=True, connect=True)
                except Exception as e:
                    print(f"Error updating permissions for {channel.name}: {e}")

    # Send completion embed
    complete_embed = build_embed(
        kind="success",
        title="✅ Lab Setup Complete!",
        description="**Chris2stickyy's Lab** is now ready to go! 🧪"
    )
    complete_embed.add_field(
        name="📁 Categories Created / Updated",
        value="Lab Info • MUT Lab • Lab Lounge • Matchmaking • Stream Zone • Voice Channels • Staff Only • Support Tickets",
        inline=False
    )
    complete_embed.add_field(
        name="💬 Channels & Roles",
        value="All text channels, voice channels, and roles have been set up with proper permissions!",
        inline=False
    )
    complete_embed.add_field(
        name="🎮 Next Steps",
        value="• Run `!setup_verify` once to lock the server\n• Run `!setup_roles` and `!setup_rules`\n• Customize as needed",
        inline=False
    )

    await status_msg.edit(embed=complete_embed)


# ---------- CLEAN HELP MENU ----------

@bot.command(name="help")
async def custom_help(ctx, command_name: str = None):
    """
    Custom help command with clean embeds.
    Usage:
      !help          -> overview
      !help command  -> details for a single command
    """
    if command_name:
        cmd = bot.get_command(command_name)
        if cmd is None:
            error_embed = build_embed(
                kind="error",
                title="❌ Unknown Command",
                description=f"I couldn't find a command named `{command_name}`."
            )
            error_embed.add_field(
                name="Tip",
                value="Run `!help` to see the full command list.",
                inline=False
            )
            await ctx.send(embed=error_embed)
            return

        desc = cmd.help or "No description provided."
        detail_embed = build_embed(
            kind="info",
            title=f"🧪 Help: `{PREFIX}{cmd.name}`",
            description=desc
        )
        await ctx.send(embed=detail_embed)
        return

    embed = build_embed(
        kind="info",
        title="🧪 Chris2stickyy's Lab – Command Menu",
        description="Everything this bot can do in the Lab."
    )

    # STAFF COMMANDS
    embed.add_field(
        name="🔧 Staff Commands (👑 Lab Owner / 🧪 Lab Tech)",
        value=(
            f"`{PREFIX}setup_lab` – Create/update categories, channels, roles, topics.\n"
            f"`{PREFIX}setup_verify` – Enable verification + lock channels.\n"
            f"`{PREFIX}setup_roles` – Create/update the reaction role menu.\n"
            f"`{PREFIX}setup_rules` – Post or update the rules embed in #📜┃rules.\n"
            f"`{PREFIX}setup_tiktok <username>` – Configure TikTok username for lives.\n"
            f"`{PREFIX}golive [message]` – Send a clean TikTok live ping embed.\n"
            f"`{PREFIX}nextmatch` – Pull next 2 players from the match queue.\n"
            f"`{PREFIX}wager @user amount reason` – Log a wager to mod-logs.\n"
            f"`{PREFIX}strikes [@user]` – Show a strike list or a single user's strikes.\n"
            f"`{PREFIX}clearstrike @user [amount]` – Remove one or more strikes from a user.\n"
            f"`{PREFIX}clearstrikes @user` – Reset a user's strikes to 0.\n"
            f"`{PREFIX}labinfo` – Info about this bot & features.\n"
            f"`{PREFIX}close` – Close a support/report ticket (in a ticket channel)."
        ),
        inline=False
    )

    # MEMBER COMMANDS
    embed.add_field(
        name="🙋 Member Commands (Everyone)",
        value=(
            f"`{PREFIX}help` – Show this menu.\n"
            f"`{PREFIX}help <command>` – Details for a single command.\n"
            f"`{PREFIX}helpme <issue>` – Open a **private support ticket** with staff.\n"
            f"`{PREFIX}report <details>` – Open a **private report ticket** about a player/issue.\n"
            f"`{PREFIX}rank [@user]` – Show Lab level & XP.\n"
            f"`{PREFIX}leaderboard` / `{PREFIX}top` – XP leaderboard.\n"
            f"`{PREFIX}wallet [@user]` – See Lab Coins for you or someone else.\n"
            f"`{PREFIX}daily` – Claim your daily Lab Coins.\n"
            f"`{PREFIX}coinflip <amount> <heads/tails>` – Bet coins on a coin flip.\n"
            f"`{PREFIX}queue` – Join the matchmaking queue.\n"
            f"`{PREFIX}leavequeue` – Leave the matchmaking queue.\n"
            f"`{PREFIX}servercount` / `{PREFIX}members` – Show live member stats."
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ Auto Systems",
        value=(
            "• Auto-moderation: deletes messages with hard-banned words, adds strikes, and can auto-mute/kick/ban.\n"
            "• Auto ticket logs and wager logs in **#📂┃mod-logs**.\n"
            "• Verification gate: new users only see the verification channel until they verify."
        ),
        inline=False
    )

    await ctx.send(embed=embed)


@bot.command(name="labinfo")
async def labinfo(ctx):
    """Shows information about Chris2stickyy's Lab Bot"""
    info_embed = build_embed(
        kind="info",
        title="🧪 Chris2stickyy's Lab Bot",
        description="Your all-in-one Discord server setup, moderation, and economy bot for the Lab."
    )
    info_embed.add_field(
        name="🔧 Staff Commands",
        value=(
            "`!setup_lab` • `!setup_verify` • `!setup_roles`\n"
            "`!setup_rules` • `!setup_tiktok` • `!golive`\n"
            "`!nextmatch` • `!wager` • `!strikes` • `!clearstrike` • `!clearstrikes` • `!close`"
        ),
        inline=False
    )
    info_embed.add_field(
        name="🙋 Member Commands",
        value=(
            "`!help` • `!helpme` • `!report` • `!rank`\n"
            "`!leaderboard` • `!wallet` • `!daily`\n"
            "`!coinflip` • `!queue` • `!leavequeue` • `!servercount`"
        ),
        inline=False
    )
    info_embed.add_field(
        name="✨ Features",
        value=(
            "• Auto server setup (categories, channels, roles)\n"
            "• OG Day One / No Money Spent / Paid to Win roles\n"
            "• Auto-role reactions 🎮\n"
            "• Verification lock system ✅\n"
            "• TikTok live ping system 📺\n"
            "• XP & rank system + leaderboard 📊\n"
            "• Lab Coins, daily rewards, coinflip mini-game 💰\n"
            "• Private ticket system for help & reports 🎫\n"
            "• Auto-moderation with strikes, mute/kick/ban 🛡️\n"
            "• Mod-logs for tickets, wagers, and filters 📂"
        ),
        inline=False
    )
    info_embed.add_field(
        name="🎮 Made for",
        value="Madden 26 Ultimate Team & Chris2stickyy's Lab community.",
        inline=False
    )
    info_embed.set_thumbnail(url="https://i.imgur.com/9g0oXOh.png")
    await ctx.send(embed=info_embed)


# ---------- REACTION ROLE SYSTEM ----------

@bot.command(name="setup_roles")
@is_lab_staff()
async def setup_roles(ctx):
    """Creates or updates a reaction role message for console roles, special roles, and notifications"""
    global reaction_role_messages

    guild = ctx.guild

    # Try to use the 🎭┃roles channel if it exists, otherwise current channel
    roles_channel = get(guild.text_channels, name="🎭┃roles") or ctx.channel

    # Look for an existing reaction role message (last 100 messages in that channel)
    existing_msg = None
    async for m in roles_channel.history(limit=100):
        if m.author == bot.user and m.embeds:
            emb = m.embeds[0]
            if emb.title == "🎮 Choose Your Roles":
                existing_msg = m
                break

    # The embed we want to use (new or existing)
    embed = build_embed(
        kind="info",
        title="🎮 Choose Your Roles",
        description=(
            "React to this message to get your roles!\n\n"
            "**Console Roles:**\n"
            "🎮 = PS5\n"
            "🟢 = Xbox\n"
            "💻 = PC\n\n"
            "**Notifications:**\n"
            "📣 = Get pinged for announcements & live streams\n\n"
            "**Special Roles:**\n"
            "🥇 = OG Day One (first 25 only)\n"
            "📉 = No Money Spent\n"
            "💰 = Paid to Win"
        )
    )

    if existing_msg:
        # Edit the existing message instead of creating a new one
        msg = existing_msg
        await msg.edit(embed=embed)

        # Make sure reactions are present
        try:
            await msg.add_reaction("🎮")  # PS5
            await msg.add_reaction("🟢")  # Xbox
            await msg.add_reaction("💻")  # PC
            await msg.add_reaction("📣")  # Notifications
            await msg.add_reaction("🥇")  # OG Day One
            await msg.add_reaction("📉")  # No Money Spent
            await msg.add_reaction("💰")  # Paid to Win
        except discord.HTTPException:
            pass

        info_text = f"Updated existing reaction role message in {roles_channel.mention}"
    else:
        # Create a brand new reaction role message
        msg = await roles_channel.send(embed=embed)

        await msg.add_reaction("🎮")  # PS5
        await msg.add_reaction("🟢")  # Xbox
        await msg.add_reaction("💻")  # PC
        await msg.add_reaction("📣")  # Notifications
        await msg.add_reaction("🥇")  # OG Day One
        await msg.add_reaction("📉")  # No Money Spent
        await msg.add_reaction("💰")  # Paid to Win

        info_text = f"Created new reaction role message in {roles_channel.mention}"

    # Store message ID for reaction tracking
    reaction_role_messages[msg.id] = {
        "🎮": "🎮 PS5",
        "🟢": "🎮 Xbox",
        "💻": "🎮 PC",
        "📣": "📣 Notifications",
        "🥇": "🥇 OG Day One",
        "📉": "📉 No Money Spent",
        "💰": "💰 Paid to Win",
    }
    save_config()

    success_embed = build_embed(
        kind="success",
        title="✅ Reaction Roles Ready",
        description=info_text + "\n\nMembers can now react to get their roles automatically."
    )
    await ctx.send(embed=success_embed, delete_after=10)


@bot.event
async def on_raw_reaction_add(payload):
    """Handle reaction role additions"""
    global reaction_role_messages, og_day_one_claims

    if payload.message_id not in reaction_role_messages:
        return

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    emoji = str(payload.emoji)
    role_name = reaction_role_messages[payload.message_id].get(emoji)

    if not role_name:
        return

    role = get(guild.roles, name=role_name)
    member = guild.get_member(payload.user_id)

    if not (role and member):
        return

    # Handle OG Day One cap
    if role_name == "🥇 OG Day One":
        # If user already in claims, just give role normally
        if payload.user_id not in og_day_one_claims:
            if len(og_day_one_claims) >= OG_DAY_ONE_MAX:
                # Remove reaction and DM the user
                try:
                    channel = bot.get_channel(payload.channel_id)
                    if channel:
                        msg = await channel.fetch_message(payload.message_id)
                        for react in msg.reactions:
                            if str(react.emoji) == emoji:
                                async for u in react.users():
                                    if u.id == payload.user_id:
                                        await msg.remove_reaction(emoji, u)
                                        break
                    await member.send(
                        f"🥇 **OG Day One** is capped at the first {OG_DAY_ONE_MAX} people and is already full."
                    )
                except Exception as e:
                    print(f"Error handling OG cap: {e}")
                return
            else:
                og_day_one_claims.append(payload.user_id)
                save_config()

    await member.add_roles(role, reason="Reaction role")
    print(f"Added {role_name} to {member.name}")


@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction role removals"""
    global reaction_role_messages

    if payload.message_id not in reaction_role_messages:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    emoji = str(payload.emoji)
    role_name = reaction_role_messages[payload.message_id].get(emoji)

    if role_name:
        role = get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)

        if role and member:
            await member.remove_roles(role, reason="Reaction role removed")
            print(f"Removed {role_name} from {member.name}")


# ---------- VERIFICATION SYSTEM ----------

class VerificationView(discord.ui.View):
    """
    Persistent view for verification button.
    Defined at top level so it can be added in on_ready().
    """
    def __init__(self):
        # persistent view (timeout=None) so the button keeps working after restart
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify Me",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="verify_button"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        global verified_role_id

        if not verified_role_id:
            # Safety guard in case someone clicks before setup_verify is run
            await interaction.response.send_message(
                "Verification is not fully set up yet. Please notify staff.",
                ephemeral=True,
            )
            return

        verified_role = get(interaction.guild.roles, id=verified_role_id)

        if not verified_role:
            await interaction.response.send_message(
                "The Verified role is missing. Please notify staff.",
                ephemeral=True,
            )
            return

        # Already has the role
        if verified_role in interaction.user.roles:
            already_embed = build_embed(
                kind="info",
                title="✅ Already Verified",
                description="You’re already verified and have access to the Lab."
            )
            await interaction.response.send_message(
                embed=already_embed,
                ephemeral=True
            )
            return

        # Give the role
        await interaction.user.add_roles(
            verified_role,
            reason="Verified via button"
        )

        welcome_embed = build_embed(
            kind="success",
            title="🎉 Welcome to the Lab!",
            description="You've been verified! Explore the channels and have fun. 🧪"
        )
        welcome_embed.add_field(
            name="🎮 Get Your Roles",
            value="Head to the roles channel to pick your console and notification preferences!",
            inline=False
        )

        await interaction.response.send_message(
            embed=welcome_embed,
            ephemeral=True
        )


@bot.command(name="setup_verify")
@is_lab_staff()
async def setup_verify(ctx):
    """Enable verification system for new members"""
    global verification_enabled, verification_channel_id, verified_role_id

    guild = ctx.guild

    # Create verified role
    verified_role = await get_or_create_role(
        guild,
        "✅ Verified",
        colour=discord.Colour.green()
    )
    verified_role_id = verified_role.id

    # Create or find verification channel
    verify_channel = get(guild.text_channels, name="✅┃verification")
    if not verify_channel:
        # Create verification channel in Lab Info category
        info_cat = get(guild.categories, name="📢┃Lab Info")
        if info_cat:
            verify_channel = await guild.create_text_channel(
                name="✅┃verification",
                category=info_cat
            )
        else:
            verify_channel = await guild.create_text_channel(name="✅┃verification")

    verification_channel_id = verify_channel.id
    verification_enabled = True
    save_config()

    # Update channel permissions to require verification
    everyone = guild.default_role

    # Staff-only channels - don't give verified role access
    staff_channels = ["🔧┃staff-chat", "🚨┃reports", "📂┃mod-logs"]

    # Read-only channels - verified can read but not write
    read_only_channels = [
        "👋┃welcome",
        "📜┃rules",
        "📢┃lab-announcements",
        "💰┃coin-methods",
        "🔴┃live-notifications",
        "🎁┃giveaways",
    ]

    # Lock all text channels except verification
    for channel in guild.text_channels:
        # Skip staff-only channels entirely
        if channel.name in staff_channels:
            continue

        # Skip verification channel (handled separately)
        if channel.id == verify_channel.id:
            continue

        try:
            # Deny everyone
            await channel.set_permissions(everyone, read_messages=False)

            # Grant verified role appropriate access
            if channel.name in read_only_channels:
                await channel.set_permissions(verified_role, read_messages=True)
            else:
                await channel.set_permissions(
                    verified_role,
                    read_messages=True,
                    send_messages=True
                )
        except Exception as e:
            print(f"Error updating permissions for {channel.name}: {e}")

    # Lock all voice channels
    for channel in guild.voice_channels:
        try:
            await channel.set_permissions(everyone, view_channel=False)
            await channel.set_permissions(
                verified_role,
                view_channel=True,
                connect=True
            )
        except Exception as e:
            print(f"Error updating permissions for {channel.name}: {e}")

    # Make sure verification channel is visible to everyone but read-only
    await verify_channel.set_permissions(everyone, read_messages=True, send_messages=False)
    await verify_channel.set_permissions(verified_role, read_messages=True, send_messages=False)

    # Send verification message with button
    verify_embed = build_embed(
        kind="success",
        title="✅ Welcome to Chris2stickyy's Lab!",
        description=(
            "Click the button below to verify and gain access to the server.\n\n"
            "By verifying, you agree to follow the server rules."
        )
    )

    view = VerificationView()
    await verify_channel.send(embed=verify_embed, view=view)

    success_embed = build_embed(
        kind="success",
        title="✅ Verification System Enabled!",
        description=(
            f"New members must verify in {verify_channel.mention} to access the server.\n\n"
            "⚠️ **All channels are now locked for unverified members.**"
        )
    )
    await ctx.send(embed=success_embed)


# ---------- TIKTOK LIVE (MANUAL PING) ----------

@bot.command(name="setup_tiktok")
@is_lab_staff()
async def setup_tiktok(ctx, username: str = None):
    """Setup TikTok live stream username (used in !golive embed link)."""
    global tiktok_username, tiktok_live_channel_id

    if not username:
        error_embed = build_embed(
            kind="error",
            title="❌ Missing TikTok Username",
            description="I need your TikTok @ so I can build clean live alerts.\n\n**Usage:** `!setup_tiktok chris2stickyy`"
        )
        await ctx.send(embed=error_embed)
        return

    tiktok_username = username
    save_config()

    # Find or store live notifications channel
    live_channel = get(ctx.guild.text_channels, name="🔴┃live-notifications")
    if live_channel:
        tiktok_live_channel_id = live_channel.id
        save_config()

    success_embed = build_embed(
        kind="success",
        title="📺 TikTok Live Alerts Configured",
        description=f"TikTok username set to **@{username}**.\n\nUse `!golive` when you start streaming."
    )
    await ctx.send(embed=success_embed)


@bot.command(name="golive")
@is_lab_staff()
async def golive(ctx, *, message: str = "Come watch the stream!"):
    """
    Manually trigger a live notification with a clean embed.
    Uses TikTok username from !setup_tiktok and pings 📣 Notifications.
    """
    global tiktok_live_channel_id, tiktok_username

    if not tiktok_live_channel_id:
        missing_embed = build_embed(
            kind="error",
            title="❌ Live Channel Not Configured",
            description="I don't know where to send live alerts yet.\n\nSet me up first with:\n`!setup_tiktok your_tiktok_name`"
        )
        await ctx.send(embed=missing_embed)
        return

    live_channel = bot.get_channel(tiktok_live_channel_id)
    notif_role = get(ctx.guild.roles, name="📣 Notifications")

    if not live_channel:
        not_found_embed = build_embed(
            kind="error",
            title="❌ Live Channel Missing",
            description="I couldn't find **#🔴┃live-notifications**. Did it get renamed or deleted?"
        )
        await ctx.send(embed=not_found_embed)
        return

    live_embed = build_live_embed(
        message=message,
        tiktok_name=tiktok_username,
        author=ctx.author
    )

    ping_text = f"{notif_role.mention} 🚨" if notif_role else "@everyone 🚨"
    await live_channel.send(content=ping_text, embed=live_embed)

    confirm_embed = build_embed(
        kind="success",
        title="✅ Live Alert Sent",
        description=f"Your live card has been posted in {live_channel.mention}."
    )
    confirm_embed.add_field(
        name="🔔 Pinged",
        value=f"{notif_role.mention if notif_role else '@everyone'}",
        inline=True
    )
    if tiktok_username:
        confirm_embed.add_field(
            name="🎥 Linked TikTok",
            value=f"@{tiktok_username}",
            inline=True
        )
    await ctx.send(embed=confirm_embed)


# ---------- RULES / SERVER GUIDELINES ----------

@bot.command(name="setup_rules")
@is_lab_staff()
async def setup_rules(ctx):
    """
    Post or update a clean rules embed into #📜┃rules (or current channel if not found)
    and pin it. If a rules embed already exists, it is edited instead of duplicated.
    """
    guild = ctx.guild

    # Try to send to 📜┃rules if it exists, otherwise use the channel where the command was run
    rules_channel = get(guild.text_channels, name="📜┃rules") or ctx.channel

    rules_embed = build_embed(
        kind="info",
        title="📜 Chris2stickyy's Lab Rules",
        description=(
            "Read this before chatting or playing. Breaking these can lead to warnings, mutes, kicks, or bans.\n\n"
            "🚨 **Auto-Moderation:** Certain slurs and extreme language are hard-banned. "
            "Messages using them are deleted automatically and give strikes."
        )
    )

    # 1–6 (core rules)
    rules_embed.add_field(
        name="1️⃣ Respect Everyone",
        value=(
            "• No harassment, racism, sexism, or slurs\n"
            "• Trash talk is cool, **disrespect is not**\n"
            "• Hard-banned slurs = auto strike + message removed\n"
            "• Listen to staff decisions"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="2️⃣ Keep It Clean",
        value=(
            "• No extreme or graphic content\n"
            "• No doxxing, sharing personal info, or witch-hunts\n"
            "• No serious self-harm talk or threats"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="3️⃣ No Cheating / Scamming",
        value=(
            "• No cheating, exploiting, or abusing glitches\n"
            "• No scamming trades, games, or deals\n"
            "• If you get caught, you're gone"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="4️⃣ Chat & Voice Rules",
        value=(
            "• No mic-spam, soundboards, or blasting music in voice\n"
            "• Use the right channels (clips in clips, LFG in matchmaking, etc.)\n"
            "• No spamming or pinging staff for no reason"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="5️⃣ Stream & Content Rules",
        value=(
            "• Don’t leak stuff from private staff channels\n"
            "• Don’t troll or grief games on stream\n"
            "• Respect stream chat rules even when you're not in Discord"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="6️⃣ Staff Have Final Say",
        value=(
            "• Mods and Lab Techs can warn, mute, kick, or ban at their discretion\n"
            "• If you think something is unfair, DM staff **calmly**"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="7️⃣ No Advertising / Self-Promo",
        value=(
            "• No promoting your TikTok, YouTube, Twitch, or Discord\n"
            "• No DM advertising\n"
            "• No posting invite links without staff permission\n"
            "• Only the owner and staff can promote content"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="8️⃣ No Begging",
        value=(
            "• Don’t beg for money, points, or gifts\n"
            "• Don’t spam for giveaways or handouts\n"
            "• Ask respectfully once, then move on"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="9️⃣ Game & Match Rules",
        value=(
            "• All games and friendly matches are at your own risk\n"
            "• Record or clip important games when possible\n"
            "• Proven scammers or cheaters = instant ban"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="1️⃣0️⃣ Franchise Rules",
        value=(
            "• Follow all franchise rules set by the commissioner\n"
            "• Play your games on time and communicate if you can’t\n"
            "• No cheating, glitching, or dashboarding to avoid losses\n"
            "• Record your games when possible for proof\n"
            "• Toxic behavior toward opponents can get you removed from the franchise"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="1️⃣1️⃣ No Exploiting or Glitches",
        value=(
            "• No in-game exploits, glitch plays, or modding\n"
            "• No connection abuse or unfair lag tricks\n"
            "• If the community agrees something is cheesy/abusive, don’t spam it"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="1️⃣2️⃣ No Impersonating Staff",
        value=(
            "• Don’t pretend to be a mod or owner\n"
            "• Don’t fake warnings, bans, or announcements\n"
            "• Impersonation = instant punishment"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="1️⃣3️⃣ Reporting Rules",
        value=(
            "• Use **tickets** (`!helpme` / `!report`) to contact staff\n"
            "• Include proof: screenshots, clips, message links, etc.\n"
            "• Troll / fake reports can get **you** punished"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="1️⃣4️⃣ Privacy Rules",
        value=(
            "• No sharing real names, addresses, or private info\n"
            "• No recording voice chats just to expose people\n"
            "• No posting DMs publicly without permission (unless for staff reports)"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="1️⃣5️⃣ Common Sense Rule",
        value=(
            "• If you think it’s **borderline**, just don’t do it\n"
            "• “But it wasn’t written in the rules” is **not** an excuse\n"
            "• Staff can act on anything that hurts the community"
        ),
        inline=False
    )

    # NEW: Strike system section
    rules_embed.add_field(
        name="🚨 Strike & Punishment System",
        value=(
            "• **1st strike:** warning\n"
            "• **2nd strike:** auto mute (🔇 Muted role)\n"
            "• **3rd strike:** auto kick from the server\n"
            "• **4th+ strike:** auto ban from the server\n"
            "• Staff can review and remove strikes with `!clearstrike` / `!clearstrikes`"
        ),
        inline=False
    )

    rules_embed.add_field(
        name="✅ By being in this server...",
        value="You agree to follow these rules **and the strike system**. If you can't, the Lab isn't for you.",
        inline=False
    )

    # Try to find an existing rules embed from this bot in the channel
    existing_msg = None
    async for m in rules_channel.history(limit=50):
        if m.author == bot.user and m.embeds:
            emb = m.embeds[0]
            if emb.title == "📜 Chris2stickyy's Lab Rules":
                existing_msg = m
                break

    if existing_msg:
        await existing_msg.edit(embed=rules_embed)
        msg = existing_msg
    else:
        msg = await rules_channel.send(embed=rules_embed)
        try:
            await msg.pin()
        except (discord.Forbidden, discord.HTTPException):
            pass

    confirm = build_embed(
        kind="success",
        title="✅ Rules Posted / Updated",
        description=f"Rules have been posted/updated in {rules_channel.mention}."
    )
    await ctx.send(embed=confirm, delete_after=10)


# ---------- TICKET COMMANDS (MEMBER-FACING) ----------

@bot.command(name="helpme")
async def helpme(ctx, *, issue: str):
    """
    Members use this when they need help with anything.
    Opens (or updates) a private ticket channel visible only to them + Lab Staff.
    """
    await open_ticket(ctx, issue, is_report=False)


@bot.command(name="report")
async def report_cmd(ctx, *, details: str):
    """
    Members use this to report players / issues.
    Opens (or updates) a private report ticket visible only to them + Lab Staff.
    """
    await open_ticket(ctx, details, is_report=True)


@bot.command(name="close")
async def close_ticket(ctx):
    """
    Close the current ticket channel.
    Can be used by the ticket owner or Lab Staff inside a ticket channel.
    """
    channel = ctx.channel
    guild = ctx.guild
    if not guild or not isinstance(channel, discord.TextChannel):
        return

    if channel.category is None or channel.category.name != TICKET_CATEGORY_NAME:
        await ctx.send("This command can only be used inside a ticket channel.", delete_after=10)
        return

    lab_owner = get(guild.roles, name="👑 Lab Owner")
    lab_tech = get(guild.roles, name="🧪 Lab Tech")

    is_staff = (
        (lab_owner and lab_owner in ctx.author.roles) or
        (lab_tech and lab_tech in ctx.author.roles)
    )

    ticket_owner_id = None
    if channel.topic and "user_id:" in channel.topic:
        try:
            ticket_owner_id = int(channel.topic.split("user_id:")[1].split()[0])
        except ValueError:
            ticket_owner_id = None

    is_owner = ticket_owner_id == ctx.author.id

    if not (is_staff or is_owner):
        await ctx.send("Only Lab Staff or the ticket owner can close this ticket.", delete_after=10)
        return

    # Log to mod-logs
    log_embed = build_embed(
        kind="warning",
        title="📂 Ticket Closed",
        description=f"Ticket channel {channel.mention} closed."
    )
    if ticket_owner_id:
        user = guild.get_member(ticket_owner_id)
        if user:
            log_embed.add_field(name="User", value=user.mention, inline=True)
    log_embed.add_field(name="Closed By", value=ctx.author.mention, inline=True)
    await log_to_modlogs(guild, log_embed)

    confirm = build_embed(
        kind="warning",
        title="🔒 Ticket Closed",
        description="This ticket will be deleted in a few seconds."
    )
    await ctx.send(embed=confirm, delete_after=5)
    try:
        await channel.delete(reason="Ticket closed")
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete this channel.", delete_after=10)


