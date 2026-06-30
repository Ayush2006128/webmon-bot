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
            try:
                async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                    response = await client.post(f"{settings.api_url}/chat", json={"thread_id": thread_id, "message": content})
                    
                    reply = None
                    sources = []
                    
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            for key in ("response", "reply", "message"):
                                if key in data:
                                    reply = data[key]
                                    break
                            sources = data.get("sources", [])
                    except ValueError:
                        data = None

                    if response.status_code >= 400 and reply is None:
                        response.raise_for_status()
                        
                    if reply is None:
                        reply = str(data) if data is not None else response.text

                    reply_str = str(reply)
                    if sources:
                        reply_str += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in sources)

            except httpx.HTTPStatusError as e:
                if "insufficient credits" in e.response.text.lower():
                    await message.channel.send(INSUFFICIENT_CREDITS_MESSAGE)
                else:
                    await message.channel.send(f"Error communicating with API: {e}")
                return
            except Exception as e:
                await message.channel.send(f"Error communicating with API: {e}")
                return

        if "insufficient credits" in reply_str.lower():
            reply_str = INSUFFICIENT_CREDITS_MESSAGE
        elif len(reply_str) > 2000:
            reply_str = reply_str[:1996] + "..."

        if not reply_str.strip():
            reply_str = "*(Empty response)*"

        try:
            await message.channel.send(reply_str)
        except Exception as e:
            try:
                await message.channel.send(f"Discord API error: {e}")
            except:
                pass
