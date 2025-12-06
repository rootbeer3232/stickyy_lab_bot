import os
import time

from keep_alive import keep_alive
from shared import TOKEN, bot

# Import all command and event modules so their decorators register with the bot
import commands_setup  # noqa: F401
import commands_econ  # noqa: F401
import events_automod  # noqa: F401
import events_logs_and_lifecycle  # noqa: F401


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set.")

if __name__ == "__main__":
    keep_alive()  # start the health server in the background

    while True:
        try:
            bot.run(TOKEN, reconnect=True)
        except Exception as e:
            print("Bot crashed with error:", e)
            print("Restarting in 5 seconds...")
            time.sleep(5)
