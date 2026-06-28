import os

from dotenv import load_dotenv


class Settings:
    def __init__(self, discord_token: str, api_url: str, api_key: str):
        self.discord_token = discord_token
        self.api_url = api_url
        self.api_key = api_key


def load_settings() -> Settings:
    load_dotenv()

    discord_token = os.environ.get("DISCORD_BOT_TOKEN")
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    api_key = os.environ.get("API_KEY")

    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable not set. Make sure it is set in Doppler.")
    if not api_url:
        raise ValueError("API_URL environment variable not set. Make sure it is set in Doppler.")
    if not api_key:
        raise ValueError("API_KEY or X_API_KEY environment variable not set. Make sure it is set in Doppler.")

    return Settings(discord_token=discord_token, api_url=api_url.rstrip("/"), api_key=api_key)
