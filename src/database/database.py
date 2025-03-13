import os
import aiosqlite
from typing import List, Dict, Any
from src.utils.logging_config import configure_logging

log = configure_logging()

# TODO: Add Docstrings

class Database:
    def __init__(self, db_path: str = "data/pickem.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)