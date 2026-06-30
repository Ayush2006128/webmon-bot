import discord
import httpx
from discord import app_commands
from discord.ext import commands

from config import Settings
from messages import AUTH_REQUIRED_MESSAGE


def setup_ai_commands(bot: commands.Bot, settings: Settings, user_sessions: dict[str, str]) -> None:
    @bot.tree.command(name="model", description="Fetch or set the model.")
    @app_commands.describe(model_name="The name of the model to use (optional)")
    async def model_command(interaction: discord.Interaction, model_name: str = None):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        if user_id not in user_sessions:
            await interaction.followup.send(AUTH_REQUIRED_MESSAGE)
            return

        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Authorization": f"Bearer {user_sessions[user_id]}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            try:
                if model_name:
                    response = await client.post(f"{settings.api_url}/model", json={"model_name": model_name})
                    response.raise_for_status()
                    await interaction.followup.send(f"Successfully set model to `{model_name}`.")
                else:
                    response = await client.get(f"{settings.api_url}/models")
                    response.raise_for_status()
                    data = response.json()
                    await interaction.followup.send(f"Current model info: `{data}`")
            except Exception as e:
                await interaction.followup.send(f"An error occurred while communicating with the API: {e}")
