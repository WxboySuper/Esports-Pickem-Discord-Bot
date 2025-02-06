import sys
from pathlib import Path

# Get the src directory path
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from flask import Flask
from flask_cors import CORS
from dashboard.routes import admin, api
import os
from utils.db import PickemDB
from utils.bot_instance import BotInstance

def create_app():
    # skipcq: PYL-W0621
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Configure CORS
    CORS(app)
    
    print("\n=== Flask App Initialization ===")
    bot = BotInstance.get_bot()
    print(f"Got bot instance: {bot}")
    if bot:
        print(f"Bot announcer exists: {bot.announcer is not None}")
    
    # Ensure database has access to announcer
    @app.before_request
    def ensure_announcer():
        print("\n=== Before Request ===")
        db = PickemDB()
        print(f"Created DB instance: {db}")
        if not db.announcer:
            print("No announcer found, attempting to refresh")
            success = db.refresh_announcer()
            print(f"Refresh result: {success}")
            if success:
                print(f"Announcer after refresh: {db.announcer}")
        else:
            print(f"Announcer already exists: {db.announcer}")
        print("=== Before Request Complete ===\n")

    # Basic configuration
    app.config.update(
        DEBUG=True,
        JSON_SORT_KEYS=False
    )

    # Register routes
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)

    @app.route('/')
    def home():
        return "Welcome to the Discord Esports Pickem Dashboard!"

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(
        host='127.0.0.1',  # Change to specifically use IPv4 localhost
        port=5000,       # Use port 5000
        debug=True       # Enable debug mode
    )