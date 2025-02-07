import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class"""
    BOT_ENV = os.getenv('BOT_ENV', 'prod').lower()
    
    @staticmethod
    def get_config():
        """Factory method to get correct config"""
        if os.getenv('BOT_ENV', 'prod').lower() == 'test':
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