import discord
import httpx
from discord.ext import commands

from config import Settings
from messages import INSUFFICIENT_CREDITS_MESSAGE


def setup_message_handler(bot: commands.Bot, settings: Settings, user_sessions: dict[str, str]) -> None:
    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user:
            return

        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.process_commands(message)
            return

        thread_id = str(message.channel.id)
        content = message.content

        if not content.strip():
            return

        user_id = str(message.author.id)
        if user_id not in user_sessions:
            await message.channel.send("Please use the `/register` then `/login` or `/login` slash commands to authenticate first.")
            return

        headers = {
            "accept": "application/json",
            "X-API-Key": settings.api_key,
            "Authorization": f"Bearer {user_sessions[user_id]}",
            "Content-Type": "application/json",
        }

        async with message.channel.typing():
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                try:
                    response = await client.post(f"{settings.api_url}/chat", json={"thread_id": thread_id, "message": content})
                    response.raise_for_status()

                    try:
                        data = response.json()
                        reply = data.get("response") or data.get("reply") or data.get("message") or str(data)
                        
                        sources = data.get("sources", [])
                        if sources:
                            reply += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in sources)
                    except ValueError:
                        reply = response.text

                    if "insufficient credits" in str(reply).lower():
                        reply = INSUFFICIENT_CREDITS_MESSAGE
                    elif len(str(reply)) > 2000:
                        reply = str(reply)[:1996] + "..."

                    await message.channel.send(reply)

                except httpx.HTTPStatusError as e:
                    if "insufficient credits" in e.response.text.lower():
                        await message.channel.send(INSUFFICIENT_CREDITS_MESSAGE)
                    else:
                        await message.channel.send(f"Error communicating with API: {e}")
                except Exception as e:
                    await message.channel.send(f"Error communicating with API: {e}")
