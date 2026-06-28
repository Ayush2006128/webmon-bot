from discord.ext import commands

from commands.ai import setup_ai_commands
from commands.auth import setup_auth_commands
from commands.billing import setup_billing_commands
from config import Settings


def setup_commands(bot: commands.Bot, settings: Settings, user_sessions: dict[str, str]) -> None:
    setup_auth_commands(bot=bot, settings=settings, user_sessions=user_sessions)
    setup_ai_commands(bot=bot, settings=settings, user_sessions=user_sessions)
    setup_billing_commands(bot=bot, settings=settings, user_sessions=user_sessions)
