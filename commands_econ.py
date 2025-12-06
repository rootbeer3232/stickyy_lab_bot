from shared import *

# ---------- RANK / LEADERBOARD ----------

@bot.command(name="rank")
async def rank_cmd(ctx, member: discord.Member = None):
    """
    Show your current Lab level & XP.
    Usage: !rank or !rank @user
    """
    if member is None:
        member = ctx.author

    info = get_user_data(member.id)
    xp = info.get("xp", 0)
    level = info.get("level", 0)

    # Each level = 100 XP
    next_level_total = (level + 1) * 100
    current_level_floor = level * 100
    progress = max(xp - current_level_floor, 0)
    to_next = max(next_level_total - xp, 0)

    # Simple text progress bar
    bar_segments = 10
    ratio = min(max(progress / 100, 0), 1)
    filled = int(bar_segments * ratio)
    bar = "█" * filled + "─" * (bar_segments - filled)

    embed = build_embed(
        kind="info",
        title=f"📊 Lab Rank – {member.display_name}",
        description=f"**Level:** `{level}`\n**Total XP:** `{xp}`"
    )
    embed.add_field(
        name="Progress to next level",
        value=f"`[{bar}]` `{progress}/100 XP` (Need `{to_next}` more)",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["top"])
async def leaderboard_cmd(ctx):
    """
    Show top 10 members by XP.
    """
    members = []
    for m in ctx.guild.members:
        if m.bot:
            continue
        info = xp_data.get(str(m.id))
        if info:
            members.append((m, info.get("xp", 0), info.get("level", 0)))

    if not members:
        await ctx.send("No XP data yet.")
        return

    members.sort(key=lambda t: t[1], reverse=True)
    top10 = members[:10]

    lines = []
    for idx, (member, xp, level) in enumerate(top10, start=1):
        lines.append(f"**{idx}.** {member.mention} — Level `{level}` • XP `{xp}`")

    embed = build_embed(
        kind="info",
        title="🏆 Lab XP Leaderboard",
        description="\n".join(lines)
    )
    await ctx.send(embed=embed)


# ---------- ECONOMY: WALLET / DAILY / COINFLIP ----------

@bot.command(name="wallet")
async def wallet_cmd(ctx, member: discord.Member = None):
    """
    Show Lab Coins for yourself or another user.
    Usage: !wallet or !wallet @user
    """
    if member is None:
        member = ctx.author

    info = get_user_data(member.id)
    coins = info.get("coins", 0)

    embed = build_embed(
        kind="info",
        title=f"💰 Wallet – {member.display_name}",
        description=f"**Lab Coins:** `{coins}`"
    )
    await ctx.send(embed=embed)


@bot.command(name="daily")
async def daily_cmd(ctx):
    """
    Claim your daily Lab Coins (24h cooldown).
    """
    user_id = ctx.author.id
    info = get_user_data(user_id)
    now = datetime.utcnow()

    last_str = info.get("last_daily")
    if last_str:
        try:
            last_time = datetime.fromisoformat(last_str)
            if now - last_time < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last_time)
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                embed = build_embed(
                    kind="warning",
                    title="⏳ Daily Already Claimed",
                    description=f"You can claim again in **{hours}h {minutes}m**."
                )
                await ctx.send(embed=embed)
                return
        except Exception:
            pass

    reward = 100  # Daily reward amount
    info["coins"] = info.get("coins", 0) + reward
    info["last_daily"] = now.isoformat()
    xp_data[str(user_id)] = info
    save_config()

    embed = build_embed(
        kind="success",
        title="✅ Daily Claimed",
        description=f"You received **{reward} Lab Coins**!"
    )
    embed.add_field(name="New Balance", value=f"`{info['coins']}` coins", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="coinflip", aliases=["coin"])
async def coinflip_cmd(ctx, amount: int, choice: str):
    """
    Bet Lab Coins on a coin flip.
    Usage: !coinflip 50 heads
    """
    choice = choice.lower()
    if choice not in ["heads", "tails", "head", "tail", "h", "t"]:
        await ctx.send("Please choose `heads` or `tails`.")
        return

    if amount <= 0:
        await ctx.send("Bet amount must be positive.")
        return

    info = get_user_data(ctx.author.id)
    coins = info.get("coins", 0)

    if amount > coins:
        await ctx.send("You don't have enough Lab Coins for that bet.")
        return

    normalized_choice = "heads" if choice.startswith("h") else "tails"
    result = random.choice(["heads", "tails"])

    if result == normalized_choice:
        info["coins"] = coins + amount
        outcome = "win"
    else:
        info["coins"] = coins - amount
        outcome = "lose"

    xp_data[str(ctx.author.id)] = info
    save_config()

    embed = build_embed(
        kind="info",
        title="🪙 Coinflip Result",
        description=f"**You chose:** `{normalized_choice}`\n**Coin landed on:** `{result}`"
    )
    if outcome == "win":
        embed.add_field(name="Result", value=f"✅ You won `{amount}` coins!", inline=False)
    else:
        embed.add_field(name="Result", value=f"❌ You lost `{amount}` coins.", inline=False)
    embed.add_field(name="New Balance", value=f"`{info['coins']}` coins", inline=False)

    await ctx.send(embed=embed)


# ---------- MATCHMAKING QUEUE & WAGERS ----------

@bot.command(name="queue")
async def queue_cmd(ctx):
    """
    Join the matchmaking queue.
    """
    global match_queue

    if ctx.author.id in match_queue:
        embed = build_embed(
            kind="info",
            title="🎮 You're Already in Queue",
            description="You're already waiting for a match."
        )
        await ctx.send(embed=embed)
        return

    match_queue.append(ctx.author.id)
    position = len(match_queue)

    embed = build_embed(
        kind="success",
        title="✅ Joined Match Queue",
        description=f"You are now in the queue at position **{position}**."
    )
    await ctx.send(embed=embed)


@bot.command(name="leavequeue")
async def leavequeue_cmd(ctx):
    """
    Leave the matchmaking queue.
    """
    global match_queue

    if ctx.author.id not in match_queue:
        embed = build_embed(
            kind="warning",
            title="❌ Not in Queue",
            description="You're not currently in the matchmaking queue."
        )
        await ctx.send(embed=embed)
        return

    match_queue = [uid for uid in match_queue if uid != ctx.author.id]

    embed = build_embed(
        kind="success",
        title="✅ Left Match Queue",
        description="You have been removed from the matchmaking queue."
    )
    await ctx.send(embed=embed)


@bot.command(name="nextmatch")
@is_lab_staff()
async def nextmatch_cmd(ctx):
    """
    Staff: pull the next 2 players from the queue and announce a match.
    """
    global match_queue

    if len(match_queue) < 2:
        embed = build_embed(
            kind="warning",
            title="⚠️ Not Enough Players",
            description="Need at least 2 players in the queue to make a match."
        )
        await ctx.send(embed=embed)
        return

    id1 = match_queue.pop(0)
    id2 = match_queue.pop(0)

    p1 = ctx.guild.get_member(id1)
    p2 = ctx.guild.get_member(id2)

    embed = build_embed(
        kind="info",
        title="🏈 New Lab Match",
        description=f"{p1.mention if p1 else 'Player 1'} vs {p2.mention if p2 else 'Player 2'}"
    )
    embed.add_field(name="Instructions", value="Set up your game and report the result afterwards.", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="wager")
async def wager_cmd(ctx, opponent: discord.Member, amount: int, *, reason: str = "No reason provided"):
    """
    Log a wager between you and another user. Sends details to #📂┃mod-logs.
    Usage: !wager @user 500 friendly series
    """
    if amount <= 0:
        await ctx.send("Wager amount must be positive.")
        return

    guild = ctx.guild
    embed = build_embed(
        kind="info",
        title="📂 Wager Logged",
        description=reason
    )
    embed.add_field(name="Player 1", value=ctx.author.mention, inline=True)
    embed.add_field(name="Player 2", value=opponent.mention, inline=True)
    embed.add_field(name="Amount", value=f"`{amount}`", inline=False)
    embed.add_field(name="Channel", value=ctx.channel.mention, inline=False)

    await log_to_modlogs(guild, embed)

    confirm = build_embed(
        kind="success",
        title="✅ Wager Logged",
        description="Your wager has been recorded in the mod-logs channel."
    )
    await ctx.send(embed=confirm)


# ---------- STRIKES / MOD TOOLS ----------

@bot.command(name="strikes")
@is_lab_staff()
async def strikes_cmd(ctx, member: discord.Member = None):
    """
    Staff: check automod strikes.
    - !strikes @user  -> show that user's strikes
    - !strikes        -> show a list of everyone with strikes
    """
    # If a specific member was provided, just show theirs
    if member is not None:
        info = get_user_data(member.id)
        strikes = info.get("strikes", 0)

        embed = build_embed(
            kind="info",
            title="⚠️ User Strikes",
            description=f"{member.mention} has **{strikes}** strike(s)."
        )
        await ctx.send(embed=embed)
        return

    # No member given -> show a list
    if not xp_data:
        await ctx.send("No users have any data yet.")
        return

    rows = []
    for uid, data in xp_data.items():
        s = data.get("strikes", 0)
        if s > 0:
            try:
                rows.append((int(uid), s))
            except ValueError:
                continue

    if not rows:
        await ctx.send("Nobody has any strikes right now. ✅")
        return

    rows.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for user_id, s in rows[:20]:  # cap at 20 rows
        m = ctx.guild.get_member(user_id)
        name = m.mention if m else f"User `{user_id}`"
        lines.append(f"{name} – **{s}** strike(s)")

    embed = build_embed(
        kind="info",
        title="⚠️ Strike List",
        description="\n".join(lines)
    )
    await ctx.send(embed=embed)


@bot.command(name="clearstrike")
@is_lab_staff()
async def clearstrike_cmd(ctx, member: discord.Member, amount: int = 1):
    """
    Staff: clear a specific number of strikes from a user.
    - !clearstrike @user        -> remove 1 strike
    - !clearstrike @user 2      -> remove 2 strikes
    """
    if amount < 1:
        await ctx.send("Amount must be at least 1.")
        return

    info = get_user_data(member.id)
    before = info.get("strikes", 0)

    if before == 0:
        embed = build_embed(
            kind="info",
            title="ℹ️ No Strikes",
            description=f"{member.mention} already has **0** strikes."
        )
        await ctx.send(embed=embed)
        return

    removed = min(amount, before)
    info["strikes"] = max(0, before - amount)
    xp_data[str(member.id)] = info
    save_config()

    after = info["strikes"]

    embed = build_embed(
        kind="success",
        title="✅ Strikes Updated",
        description=(
            f"{member.mention}'s strikes were reduced by **{removed}**.\n"
            f"**Before:** {before}\n"
            f"**Now:** {after}"
        )
    )
    await ctx.send(embed=embed)


@bot.command(name="clearstrikes")
@is_lab_staff()
async def clearstrikes_cmd(ctx, member: discord.Member):
    """Staff: reset a user's strikes to zero (full wipe)."""
    info = get_user_data(member.id)
    before = info.get("strikes", 0)
    info["strikes"] = 0
    xp_data[str(member.id)] = info
    save_config()

    embed = build_embed(
        kind="success",
        title="✅ All Strikes Cleared",
        description=(
            f"All strikes cleared for {member.mention}.\n"
            f"**Before:** {before}\n"
            "**Now:** 0"
        )
    )
    await ctx.send(embed=embed)


# ---------- SERVER COUNT ----------

@bot.command(name="servercount", aliases=["members"])
async def servercount_cmd(ctx):
    """
    Show live server member stats.
    """
    guild = ctx.guild
    total = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    humans = total - bots

    embed = build_embed(
        kind="info",
        title=f"📊 Server Stats – {guild.name}",
        description=f"**Total Members:** `{total}`"
    )
    embed.add_field(name="Humans", value=f"`{humans}`", inline=True)
    embed.add_field(name="Bots", value=f"`{bots}`", inline=True)
    await ctx.send(embed=embed)





