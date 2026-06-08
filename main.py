import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import httpx

load_dotenv()

# Load environment variables (provided by Doppler)
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
API_URL = os.environ.get("API_URL")
API_KEY = os.environ.get("API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set. Make sure it is set in Doppler.")
if not API_URL:
    raise ValueError("API_URL environment variable not set. Make sure it is set in Doppler.")
if not API_KEY:
    raise ValueError("API_KEY or X_API_KEY environment variable not set. Make sure it is set in Doppler.")

# Ensure the URL doesn't have a trailing slash so we can append routes nicely
API_URL = API_URL.rstrip("/")

# Set up intents
# message_content intent is required to read standard messages
intents = discord.Intents.default()
intents.message_content = True 

class WebmonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Sync the application commands to Discord globally. 
        # (Note: Global sync can take up to an hour to update on Discord's side, 
        # but for a newly created command it often appears quickly upon restart).
        await self.tree.sync()

bot = WebmonBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

@bot.tree.command(name="model", description="Fetch or set the model.")
@app_commands.describe(model_name="The name of the model to use (optional)")
async def model_command(interaction: discord.Interaction, model_name: str = None):
    # Defer the response since API calls might take a second, 
    # preventing the interaction from failing due to timeout.
    await interaction.response.defer()
    
    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            if model_name:
                # 2. If an argument is provided, POST model_name parameter to /model route
                response = await client.post(f"{API_URL}/model", json={"model_name": model_name})
                response.raise_for_status()
                await interaction.followup.send(f"Successfully set model to `{model_name}`.")
            else:
                # 1. If no arguments are provided, fetch the GET route for /models
                response = await client.get(f"{API_URL}/models")
                response.raise_for_status()
                data = response.json()
                
                # Try to format it nicely depending on the expected JSON schema. 
                # For now, we will return the raw data stringified.
                await interaction.followup.send(f"Current model info: `{data}`")
                
        except Exception as e:
            await interaction.followup.send(f"An error occurred while communicating with the API: {e}")

@bot.event
async def on_message(message: discord.Message):
    # Ignore messages sent by the bot itself to avoid infinite loops
    if message.author == bot.user:
        return
        
    # Ensure slash commands and prefix commands (if any) still work
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return
    
    # 3. No slash command: POST thread id and message to /chat route
    # We use the channel's ID as the "thread_id". This works for both regular channels and Discord threads.
    thread_id = str(message.channel.id)
    content = message.content
    
    if not content.strip():
        return
    
    # Match the exact headers from the working curl command
    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Send a "typing..." indicator in the channel while waiting for the API
    async with message.channel.typing():
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            try:
                response = await client.post(f"{API_URL}/chat", json={
                    "thread_id": thread_id,
                    "message": content
                })
                response.raise_for_status()
                
                # Assuming the API returns JSON with a response or reply field.
                # If it's pure text, we fall back to response.text
                try:
                    data = response.json()
                    # Try a few common keys for chat responses
                    reply = data.get("response") or data.get("reply") or data.get("message") or str(data)
                except ValueError:
                    reply = response.text
                
                # Discord messages have a 2000 character limit. If it's too long, we slice it for now.
                if len(reply) > 2000:
                    reply = reply[:1996] + "..."
                    
                await message.channel.send(reply)
                
            except Exception as e:
                await message.channel.send(f"Error communicating with API: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
