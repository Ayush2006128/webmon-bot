import discord
import httpx
from discord import app_commands
from discord.ext import commands

from config import Settings
from messages import AUTH_REQUIRED_MESSAGE


def setup_billing_commands(bot: commands.Bot, settings: Settings, user_sessions: dict[str, str]) -> None:
    @bot.tree.command(name="credits", description="Check your remaining credits and last refill date.")
    async def credits_command(interaction: discord.Interaction):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        if user_id not in user_sessions:
            await interaction.followup.send(AUTH_REQUIRED_MESSAGE)
            return

        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Authorization": f"Bearer {user_sessions[user_id]}",
        }

        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            try:
                response = await client.get(f"{settings.api_url}/credits")
                response.raise_for_status()
                data = response.json()

                credits = data.get("credits", "Unknown")
                last_refill_date = data.get("last_refill_date", "Unknown")

                await interaction.followup.send(f"💰 **Credits Remaining:** {credits}\n📅 **Last Refill Date:** {last_refill_date}")
            except Exception as e:
                await interaction.followup.send(f"An error occurred while fetching credits: {e}")

    @bot.tree.command(name="buy", description="Buy a credit bundle to top up your account.")
    @app_commands.describe(bundle="The bundle you want to buy (20, 40, or 90)")
    @app_commands.choices(bundle=[
        app_commands.Choice(name="20 Credits (₹255)", value=20),
        app_commands.Choice(name="40 Credits (₹449)", value=40),
        app_commands.Choice(name="90 Credits (₹999)", value=90),
    ])
    async def buy_command(interaction: discord.Interaction, bundle: int):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        if user_id not in user_sessions:
            await interaction.followup.send(AUTH_REQUIRED_MESSAGE)
            return

        jwt_token = user_sessions[user_id]
        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "tier": f"tier_{bundle}",
        }

        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            try:
                response = await client.post(f"{settings.api_url}/payment/create-order", json=payload)
                response.raise_for_status()
                data = response.json()

                order_id = data.get("order_id")
                amount_inr = data.get("amount_inr")
                key_id = data.get("key_id")

                if not all([order_id, amount_inr, key_id]):
                    await interaction.followup.send("Invalid response from the server while creating order.")
                    return

                checkout_url = (
                    "https://webmon-site.onrender.com/checkout.html"
                    f"?order_id={order_id}&amount={amount_inr}&key_id={key_id}&token={jwt_token}"
                )

                message = (
                    f"Your order for **{bundle} Credits** has been successfully initiated!\n\n"
                    f"🔗 **[Click here to complete your payment securely]({checkout_url})**\n\n"
                    "If you have any questions about refunds or pricing, visit our "
                    "[pricing page](https://ayush2006128.github.io/webmon-api/pricing.html)."
                )

                await interaction.followup.send(message)
            except Exception as e:
                await interaction.followup.send(f"An error occurred while creating your order: {e}")
