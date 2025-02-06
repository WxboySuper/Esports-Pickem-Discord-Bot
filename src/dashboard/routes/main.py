from flask import Blueprint, render_template, request
from dashboard.models import user

bp = Blueprint('main', __name__)

# Remove leaderboard route as it's now in admin.py
# ...rest of existing code...
