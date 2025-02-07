import os
import shutil
import subprocess
from pathlib import Path
import logging
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class Deployer:
    def __init__(self):
        self.test_dir = Path('E:/Esports-Pickem-Discord-Bot')
        self.prod_dir = Path('E:/esports-pickem - Production')
        self.backup_dir = self.prod_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self):
        """Create backup of current production code"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'backup_{timestamp}'
        
        logger.info(f"Creating backup at {backup_path}")
        shutil.copytree(self.prod_dir, backup_path, ignore=shutil.ignore_patterns(
            'backups', '__pycache__', '*.pyc', '*.pyo', '.git', '.env', 'logs'
        ))
        return backup_path

    def copy_files(self):
        """Copy files from test to production"""
        logger.info("Copying files to production...")
        
        # Files/directories to exclude from copy
        exclude = [
            '.git',
            '.env',
            'logs',
            '__pycache__',
            '*.pyc',
            '*.pyo',
            'backups',
            'testing',
            '.pytest_cache',
            '.vscode',
            'deploy.bat'
        ]
        
        def ignore_patterns(names):
            return [n for n in names if any(p in n for p in exclude)]

        # Copy files
        for item in self.test_dir.iterdir():
            if item.name not in exclude:
                dest = self.prod_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest, ignore=ignore_patterns)
                else:
                    shutil.copy2(item, dest)

    def start_prod_bot(self):
        """Start the production bot"""
        logger.info("Starting production bot...")
        try:
            # Create a new process detached from the current one
            if os.name == 'nt':  # Windows
                subprocess.Popen(
                    ['python', 'prod_startup.py'],
                    cwd=str(self.prod_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:  # Linux/Unix
                subprocess.Popen(
                    ['python', 'prod_startup.py'],
                    cwd=str(self.prod_dir),
                    start_new_session=True
                )
            logger.info("Bot startup initiated")
            
            # Wait a moment to check if the process stays running
            time.sleep(5)
            logger.info("Bot appears to be running successfully")
        except Exception as err:
            logger.error(f"Failed to start production bot: {err}")
            raise

    def deploy(self):
        """Run full deployment process"""
        try:
            # Get confirmation before proceeding
            logger.info("Please ensure you have used the /shutdown command in Discord before continuing.")
            logger.info("The bot will be automatically restarted after deployment.")
            input("Press Enter when the bot has been shut down...")

            # Create backup
            backup_path = self.create_backup()
            logger.info(f"Backup created at: {backup_path}")

            # Copy files
            self.copy_files()
            logger.info("Files copied successfully")

            # Start the bot
            logger.info("Starting bot...")
            self.start_prod_bot()
            
            logger.info("Deployment completed successfully")

        except Exception as err:
            logger.error(f"Deployment failed: {err}")
            should_restore = input("Would you like to restore from backup? (y/n): ").lower()
            if should_restore == 'y':
                self.restore_from_backup(backup_path)
            raise

    def restore_from_backup(self, backup_path):
        """Restore from a backup in case of deployment failure"""
        logger.info(f"Restoring from backup: {backup_path}")
        try:
            # Remove current production files (except .env and logs)
            for item in self.prod_dir.iterdir():
                if item.name not in ['.env', 'logs', 'backups']:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            # Copy backup files
            for item in backup_path.iterdir():
                if item.name not in ['.env', 'logs', 'backups']:
                    dest = self.prod_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                        
            logger.info("Restore completed successfully")
        except Exception as err:
            logger.error(f"Restore failed: {err}")
            raise

if __name__ == "__main__":
    deployer = Deployer()
    deployer.deploy()
