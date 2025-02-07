import os
from dotenv import load_dotenv

load_dotenv()

from typing import Literal, Union

class Config:
    """Base configuration class"""
    ENV_TYPE = Literal['prod', 'test']
    BOT_ENV: ENV_TYPE = os.getenv('BOT_ENV', 'prod').lower()
    
    def __init__(self) -> None:
        if self.BOT_ENV not in ('prod', 'test'):
            raise ValueError(f"Invalid BOT_ENV value: {self.BOT_ENV}. Must be 'prod' or 'test'")
    
    @staticmethod
    def get_config() -> Union['ProdConfig', 'TestConfig']:
        """Factory method to get correct config"""
        if Config.BOT_ENV == 'test':
            return TestConfig()
        return ProdConfig()
class ProdConfig(Config):
    """Production configuration"""
    DISCORD_TOKEN = os.getenv('PROD_DISCORD_TOKEN')
    APP_ID = os.getenv('PROD_APP_ID')
    PUBLIC_KEY = os.getenv('PROD_PUBLIC_KEY')
    CLIENT_SECRET = os.getenv('PROD_CLIENT_SECRET')
    
    # Database configuration
    DB_NAME = os.getenv('PROD_DB_NAME')
    
    # Logging configuration
    LOG_LEVEL = 'INFO'
    
    @property
    def is_production(self):
        return True

class TestConfig(Config):
    """Test configuration"""
    DISCORD_TOKEN = os.getenv('TEST_DISCORD_TOKEN')
    APP_ID = os.getenv('TEST_APP_ID')
    PUBLIC_KEY = os.getenv('TEST_PUBLIC_KEY')
    CLIENT_SECRET = os.getenv('TEST_CLIENT_SECRET')
    
    # Database configuration
    DB_NAME = os.getenv('TEST_DB_NAME')
    
    # Logging configuration
    LOG_LEVEL = 'DEBUG'
    
    @property
    def is_production(self):
        return False