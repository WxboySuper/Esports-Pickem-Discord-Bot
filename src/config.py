import os

ANNOUNCEMENT_GUILD_ID = int(os.getenv("ANNOUNCEMENT_GUILD_ID", 0))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
