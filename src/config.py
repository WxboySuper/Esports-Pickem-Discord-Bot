import os
from pathlib import Path

ANNOUNCEMENT_GUILD_ID = int(os.getenv("ANNOUNCEMENT_GUILD_ID", 0))
DATA_PATH = Path(os.getenv("DATA_PATH", "data"))
