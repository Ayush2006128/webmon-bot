import discord
import httpx
from discord import app_commands
from discord.ext import commands

from config import Settings


def setup_auth_commands(bot: commands.Bot, settings: Settings, user_sessions: dict[str, str]) -> None:
    @bot.tree.command(name="register", description="Register for an account.")
    @app_commands.describe(email="Your email", password="Your password")
    async def register_command(interaction: discord.Interaction, email: str, password: str):
        await interaction.response.defer(ephemeral=True)

        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            try:
                response = await client.post(f"{settings.api_url}/register", json={"email": email, "password": password})
                response.raise_for_status()
                await interaction.followup.send("Registration successful! You can now use `/login`.")
            except Exception as e:
                await interaction.followup.send(f"An error occurred during registration: {e}")

    @bot.tree.command(name="login", description="Login to your account.")
    @app_commands.describe(email="Your email", password="Your password")
    async def login_command(interaction: discord.Interaction, email: str, password: str):
        await interaction.response.defer(ephemeral=True)

        headers = {
            "accept": "application/json",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            try:
                response = await client.post(f"{settings.api_url}/token", data={"username": email, "password": password})

                if response.status_code == 422:
                    response = await client.post(f"{settings.api_url}/token", data={"email": email, "password": password})

                response.raise_for_status()
                data = response.json()

                token = data.get("access_token") or data.get("token")
                if not token and isinstance(data, str):
                    token = data

                if token:
                    user_sessions[str(interaction.user.id)] = token
                    await interaction.followup.send("Login successful!")
                else:
                    await interaction.followup.send("Login succeeded but no token was returned in the expected format.")
            except Exception as e:
                await interaction.followup.send(f"An error occurred during login: {e}")
