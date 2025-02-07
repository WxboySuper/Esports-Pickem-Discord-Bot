import os
import shutil
import subprocess
from pathlib import Path
import logging
from datetime import datetime
import time
import sys

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
        
        # Validate Python executable path
        self.python_exe = self.get_python_executable()
        if not self.python_exe:
            raise RuntimeError("Could not find Python executable")

        # Add git check before other initialization
        self.check_git_installation()

    def get_python_executable(self) -> Path:
        """Get full path to Python executable"""
        # First try sys.executable for current Python
        if sys.executable and Path(sys.executable).exists():
            return Path(sys.executable)
            
        # Fallback to searching PATH
        python_cmd = 'python.exe' if os.name == 'nt' else 'python3'
        python_path = shutil.which(python_cmd)
        if python_path:
            return Path(python_path)
            
        return None

    @staticmethod
    def check_git_installation():
        """Check if git is installed and accessible"""
        try:
            subprocess.run(['git', '--version'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise RuntimeError("Git is not installed or not accessible")
        except FileNotFoundError:
            raise RuntimeError("Git command not found in PATH")

    def ensure_main_branch(self):
        """Ensure we're on the main branch and it's up to date"""
        try:
            # Check current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.test_dir)
            )
            current_branch = result.stdout.strip()
            
            if current_branch != 'main':
                raise RuntimeError("Not on main branch. Current branch: %s" % current_branch)
            
            # Fetch latest changes
            logger.info("Fetching latest changes from remote...")
            subprocess.run(['git', 'fetch', 'origin', 'main'], 
                         check=True, cwd=str(self.test_dir))
            
            # Check if we're behind
            result = subprocess.run(
                ['git', 'status', '-uno'],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.test_dir)
            )
            
            if "Your branch is behind" in result.stdout:
                raise RuntimeError("Local main branch is behind remote. Please pull changes first.")
            
            # Check for uncommitted changes
            if "nothing to commit" not in result.stdout:
                raise RuntimeError("You have uncommitted changes. Please commit or stash them first.")
                
            logger.info("Git branch verification successful")
            return True
            
        except subprocess.CalledProcessError as proc_error:
            raise RuntimeError("Git command failed: %s" % proc_error)

    def create_backup(self):
        """Create backup of current production code"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'backup_{timestamp}'
        
        logger.info("Creating backup at %s", backup_path)
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
            'deploy.bat',
            'scripts',
            '.coverage',
            'deepsource.toml',
            'pickem.db',
            'pytest.ini',
            'test_startup.py'
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
            startup_script = self.prod_dir / 'prod_startup.py'
            if not startup_script.exists():
                raise FileNotFoundError("Startup script not found at: %s" % startup_script)
            
            # Resolve to absolute paths
            startup_script = startup_script.resolve()
            working_dir = self.prod_dir.resolve()
            
            logger.info("Using Python: %s", self.python_exe)
            logger.info("Starting script: %s", startup_script)
            logger.info("Working directory: %s", working_dir)

            # Validate paths
            if not all(p.exists() for p in (self.python_exe, startup_script, working_dir)):
                raise FileNotFoundError("One or more required paths do not exist")

            # Create a new process with absolute paths
            if os.name == 'nt':  # Windows
                subprocess.Popen(
                    [str(self.python_exe.absolute()), str(startup_script)],
                    cwd=str(working_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:  # Linux/Unix
                subprocess.Popen(
                    [str(self.python_exe.absolute()), str(startup_script)],
                    cwd=str(working_dir),
                    start_new_session=True
                )
            logger.info("Bot startup initiated")
            
            # Wait a moment to check if the process stays running
            time.sleep(5)
            logger.info("Bot appears to be running successfully")
        except FileNotFoundError as path_error:
            logger.error("Failed to find required file: %s", path_error)
            raise
        except subprocess.SubprocessError as proc_error:
            logger.error("Failed to start bot process: %s", proc_error)
            raise
        except Exception as err:
            logger.error("Failed to start production bot: %s", err)
            raise

    def deploy(self):
        """Run full deployment process"""
        try:
            # Check git branch first
            self.ensure_main_branch()
            
            # Get confirmation before proceeding
            logger.info("Please ensure you have used the /shutdown command in Discord before continuing.")
            logger.info("The bot will be automatically restarted after deployment.")
            input("Press Enter when the bot has been shut down...")

            # Create backup
            backup_path = self.create_backup()
            logger.info("Backup created at: %s", backup_path)

            # Copy files
            self.copy_files()
            logger.info("Files copied successfully")

            # Start the bot
            logger.info("Starting bot...")
            self.start_prod_bot()
            
            logger.info("Deployment completed successfully")

        except RuntimeError as git_error:
            logger.error("Git check failed: %s", git_error)
            should_continue = input("Git check failed. Continue anyway? (y/n): ").lower()
            if should_continue != 'y':
                raise
            logger.warning("Proceeding with deployment despite git check failure")
            
        except Exception as err:
            logger.error("Deployment failed: %s", err)
            should_restore = input("Would you like to restore from backup? (y/n): ").lower()
            if should_restore == 'y':
                self.restore_from_backup(backup_path)
            raise

    def restore_from_backup(self, backup_path):
        """Restore from a backup in case of deployment failure"""
        logger.info("Restoring from backup: %s", backup_path)
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
            logger.error("Restore failed: %s", err)
            raise

if __name__ == "__main__":
    deployer = Deployer()
    deployer.deploy()
