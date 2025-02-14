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

class BaseEnvConfig(Config):
    """Base class for environment-specific configs"""
    def __init__(self, env_prefix: str) -> None:
        super().__init__()
        self.env_prefix = env_prefix
        self._validate_required_env()
    
    def _validate_required_env(self) -> None:
        """Validate all required environment variables are set"""
        required_vars = [
            f'{self.env_prefix}_DISCORD_TOKEN',
            f'{self.env_prefix}_APP_ID',
            f'{self.env_prefix}_PUBLIC_KEY',
            f'{self.env_prefix}_CLIENT_SECRET',
            f'{self.env_prefix}_DB_NAME',
            'OWNER_USER_DISCORD_ID'  # Add owner ID to required vars
        ]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    @property
    def DISCORD_TOKEN(self) -> str:
        return os.getenv(f'{self.env_prefix}_DISCORD_TOKEN', '')
    
    @property
    def APP_ID(self) -> str:
        return os.getenv(f'{self.env_prefix}_APP_ID', '')
    
    @property
    def PUBLIC_KEY(self) -> str:
        return os.getenv(f'{self.env_prefix}_PUBLIC_KEY', '')
    
    @property
    def CLIENT_SECRET(self) -> str:
        return os.getenv(f'{self.env_prefix}_CLIENT_SECRET', '')
    
    @property
    def DB_NAME(self) -> str:
        return os.getenv(f'{self.env_prefix}_DB_NAME', '')
    
    @property
    def OWNER_ID(self) -> int:
        """Get owner ID as integer"""
        owner_id = os.getenv('OWNER_USER_DISCORD_ID', '')
        try:
            return int(owner_id)
        except ValueError as val_error:
            raise ValueError("OWNER_USER_DISCORD_ID must be a valid integer") from val_error

class ProdConfig(BaseEnvConfig):
    def __init__(self) -> None:
        super().__init__('PROD')
    
    @property
    def LOG_LEVEL(self) -> str:
        return os.getenv('PROD_LOG_LEVEL', 'INFO')
    
    @property
    def is_production(self) -> bool:
        return True

class TestConfig(BaseEnvConfig):
    """Test configuration"""
    def __init__(self) -> None:
        super().__init__('TEST')
    
    @property
    def LOG_LEVEL(self) -> str:
        return os.getenv('TEST_LOG_LEVEL', 'DEBUG')
    
    @property
    def is_production(self) -> bool:
        return False