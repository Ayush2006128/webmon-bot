import discord
from discord.ext import commands

from commands import setup_commands
from config import load_settings
from handlers import setup_message_handler
from state import user_sessions

settings = load_settings()

intents = discord.Intents.default()
intents.message_content = True


class WebmonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()


bot = WebmonBot()
setup_commands(bot=bot, settings=settings, user_sessions=user_sessions)
setup_message_handler(bot=bot, settings=settings, user_sessions=user_sessions)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


if __name__ == "__main__":
    bot.run(settings.discord_token)
