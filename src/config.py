import os
from pathlib import Path

DATA_PATH = Path(os.getenv("DATA_PATH", "data"))

# Leaguepedia API Credentials
LEAGUEPEDIA_USER = os.getenv("LEAGUEPEDIA_USER")
LEAGUEPEDIA_PASS = os.getenv("LEAGUEPEDIA_PASS")

# PandaScore API Key
PANDASCORE_API_KEY = os.getenv("PANDASCORE_API_KEY")
