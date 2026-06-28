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

    @bot.tree.command(name="delete_account", description="Permanently delete your account.")
    async def delete_account_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        token = user_sessions.get(user_id)
        if not token:
            await interaction.followup.send("You must be logged in to delete your account. Use `/login` first.")
            return

        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Authorization": f"Bearer {token}",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            try:
                response = await client.delete(f"{settings.api_url}/me")
                if response.status_code == 401:
                    user_sessions.pop(user_id, None)
                    await interaction.followup.send("Your session has expired or is invalid. Please `/login` again.")
                    return
                response.raise_for_status()
                user_sessions.pop(user_id, None)
                await interaction.followup.send("Your account has been successfully deleted.")
            except Exception as e:
                await interaction.followup.send(f"An error occurred during account deletion: {e}")

    @bot.tree.command(name="update_password", description="Update your account password.")
    @app_commands.describe(old_password="Your current password", new_password="Your new password")
    async def update_password_command(interaction: discord.Interaction, old_password: str, new_password: str):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        token = user_sessions.get(user_id)
        if not token:
            await interaction.followup.send("You must be logged in to update your password. Use `/login` first.")
            return

        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            try:
                response = await client.put(f"{settings.api_url}/password", json={"old_password": old_password, "new_password": new_password})
                if response.status_code == 401:
                    user_sessions.pop(user_id, None)
                    await interaction.followup.send("Your session has expired or is invalid. Please `/login` again.")
                    return
                
                if response.status_code == 400:
                    try:
                        detail = response.json().get("detail", "Invalid request.")
                    except ValueError:
                        detail = response.text
                    await interaction.followup.send(f"Password update failed: {detail}")
                    return

                response.raise_for_status()
                await interaction.followup.send("Your password has been successfully updated.")
            except Exception as e:
                await interaction.followup.send(f"An error occurred while updating your password: {e}")
