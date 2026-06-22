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

# Store user sessions in memory (user_id -> jwt_token)
user_sessions = {}

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
    
    user_id = str(interaction.user.id)
    if user_id not in user_sessions:
        await interaction.followup.send("Please use `/register` then `/login` or just `/login` to authenticate first.")
        return

    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {user_sessions[user_id]}",
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

@bot.tree.command(name="register", description="Register for an account.")
@app_commands.describe(email="Your email", password="Your password")
async def register_command(interaction: discord.Interaction, email: str, password: str):
    await interaction.response.defer(ephemeral=True)
    
    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.post(f"{API_URL}/register", json={"email": email, "password": password})
            response.raise_for_status()
            await interaction.followup.send("Registration successful! You can now use `/login`.")
        except Exception as e:
            await interaction.followup.send(f"An error occurred during registration: {e}")

@bot.tree.command(name="login", description="Login to your account.")
@app_commands.describe(email="Your email", password="Your password")
async def login_command(interaction: discord.Interaction, email: str, password: str):
    await interaction.response.defer(ephemeral=True)
    
    headers = {
        "accept": "application/json"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            # Send as application/x-www-form-urlencoded by using 'data=' parameter
            # standard FastAPI OAuth2 uses 'username' and 'password' keys
            response = await client.post(f"{API_URL}/token", data={"username": email, "password": password})
            
            # If they expect 'email' key instead of standard 'username', fallback here
            if response.status_code == 422:
                response = await client.post(f"{API_URL}/token", data={"email": email, "password": password})
                
            response.raise_for_status()
            data = response.json()
            
            # Typical JWT response contains access_token
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

@bot.tree.command(name="credits", description="Check your remaining credits and last refill date.")
async def credits_command(interaction: discord.Interaction):
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    if user_id not in user_sessions:
        await interaction.followup.send("Please use `/register` then `/login` or just `/login` to authenticate first.")
        return

    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {user_sessions[user_id]}"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.get(f"{API_URL}/credits")
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
    app_commands.Choice(name="90 Credits (₹999)", value=90)
])
async def buy_command(interaction: discord.Interaction, bundle: int):
    # Defer response, ephemeral so checkout link is private
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    if user_id not in user_sessions:
        await interaction.followup.send("Please use `/register` then `/login` or just `/login` to authenticate first.")
        return

    jwt_token = user_sessions[user_id]
    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "tier": f"tier_{bundle}"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.post(f"{API_URL}/payment/create-order", json=payload)
            response.raise_for_status()
            data = response.json()
            
            order_id = data.get("order_id")
            amount_inr = data.get("amount_inr")
            key_id = data.get("key_id")
            
            if not all([order_id, amount_inr, key_id]):
                await interaction.followup.send("Invalid response from the server while creating order.")
                return
                
            checkout_url = f"https://webmon-site.onrender.com/checkout.html?order_id={order_id}&amount={amount_inr}&key_id={key_id}&token={jwt_token}"
            
            message = (
                f"Your order for **{bundle} Credits** has been successfully initiated!\n\n"
                f"🔗 **[Click here to complete your payment securely]({checkout_url})**\n\n"
                f"If you have any questions about refunds or pricing, visit our [pricing page](https://ayush2006128.github.io/webmon-api/pricing.html)."
            )
            
            await interaction.followup.send(message)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred while creating your order: {e}")

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
        
    user_id = str(message.author.id)
    if user_id not in user_sessions:
        await message.channel.send("Please use the `/register` then `/login` or `/login` slash commands to authenticate first.")
        return
    
    # Match the exact headers from the working curl command
    headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {user_sessions[user_id]}",
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
                
                if "insufficient credits" in str(reply).lower():
                    reply = (
                        "Sorry I can't process your request. Please buy a credit bundle or comeback after one month. "
                        "Use `/buy [bundle]` to buy new credits!\n\n"
                        "**Available Bundles:**\n"
                        "• **20 Credits** - ₹255\n"
                        "• **40 Credits** - ₹449\n"
                        "• **90 Credits** - ₹999\n\n"
                        "For refund policy and other queries, please visit our [pricing page](https://ayush2006128.github.io/webmon-api/pricing.html)."
                    )
                else:
                    # Discord messages have a 2000 character limit. If it's too long, we slice it for now.
                    if len(str(reply)) > 2000:
                        reply = str(reply)[:1996] + "..."
                    
                await message.channel.send(reply)
                
            except httpx.HTTPStatusError as e:
                if "insufficient credits" in e.response.text.lower():
                    reply = (
                        "Sorry I can't process your request. Please buy a credit bundle or comeback after one month. "
                        "Use `/buy [bundle]` to buy new credits!\n\n"
                        "**Available Bundles:**\n"
                        "• **20 Credits** - ₹255\n"
                        "• **40 Credits** - ₹449\n"
                        "• **90 Credits** - ₹999\n\n"
                        "For refund policy and other queries, please visit our [pricing page](https://ayush2006128.github.io/webmon-api/pricing.html)."
                    )
                    await message.channel.send(reply)
                else:
                    await message.channel.send(f"Error communicating with API: {e}")
            except Exception as e:
                await message.channel.send(f"Error communicating with API: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
