from flask import Blueprint, jsonify, request
from dashboard.models import user
from dashboard.models import pick  # Use absolute imports instead of relative
import asyncio

from bot.bot import bot

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/')
def index():
    return {'message': 'API endpoint'}


@bp.route('/picks/<user_id>', methods=['GET'])
def get_user_picks(user_id):
    try:
        user_id_int = int(user_id)
    except ValueError:
        return jsonify({'error': 'Invalid user ID'}), 400
    user_info = user.get_user_by_id(user_id_int)
    if user_info:
        picks = pick.get_picks_by_user(user_id)
        return jsonify({'user_id': user_id, 'picks': picks}), 200
    return jsonify({'error': 'User not found'}), 404


@bp.route('/leaderboard')
def get_leaderboard():
    """Get global or guild-specific leaderboard"""
    guild_id = request.args.get('guild_id', type=int)
    limit = request.args.get('limit', default=10, type=int)

    try:
        leaderboard = user.get_leaderboard(guild_id, limit)
        return jsonify({
            'success': True,
            'leaderboard': [
                {
                    'user_id': entry[0],
                    'total_picks': entry[1],
                    'correct_picks': entry[2],
                    'guild_count': entry[3] if len(entry) > 3 else 1
                }
                for entry in leaderboard
            ]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# TODO: Complete the implementation
@bp.route('/match/<match_id>/result', methods=['POST'])
# skipcq: PYL-W0613
def submit_match_result(match_id):
    data = request.json
    winner = data.get('winner')
    if winner:
        # Logic to update match result in the database
        return jsonify({'message': 'Match result submitted successfully'}), 200
    return jsonify({'error': 'Winner not provided'}), 400


@bp.route('/match/create', methods=['POST'])
def create_match():
    """Create a new match and trigger announcement"""
    try:
        data = request.json
        team_a = data.get('team_a')
        team_b = data.get('team_b')
        match_date = data.get('match_date')
        league_id = data.get('league_id', 1)  # Default to league_id 1 if not provided

        # Create match in database
        match_id = bot.db.add_match(league_id, team_a, team_b, match_date)

        if match_id and bot.is_ready():
            # Get league name for announcement
            league_name = "Unknown League"  # Default value
            with bot.db.conn as conn:  # Assuming you have a connection property
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM leagues WHERE league_id = ?", (league_id,))
                result = cursor.fetchone()
                if result:
                    league_name = result[0]

            # Create announcement if neither team is TBD
            if "tbd" not in team_a.lower() and "tbd" not in team_b.lower():
                asyncio.run_coroutine_threadsafe(
                    bot.announcer.announce_new_match(
                        match_id, team_a, team_b, match_date, league_name
                    ),
                    bot.loop
                )

        return jsonify({
            'success': True,
            'match_id': match_id,
            'message': 'Match created successfully'
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
