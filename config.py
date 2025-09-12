import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DEFAULT_MIN_INTERVAL = float(os.getenv("DEFAULT_MIN_INTERVAL", "2.0"))

if not BOT_TOKEN or OWNER_ID == 0:
    raise SystemExit(
        "Please set DISCORD_BOT_TOKEN and OWNER_ID correctly in .env"
    )
  
