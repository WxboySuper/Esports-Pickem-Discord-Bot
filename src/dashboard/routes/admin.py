import os
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
import sys
import logging
import traceback

# Import directly from utils
from utils.db import PickemDB
from models.user import User as user

bp = Blueprint('admin', __name__, url_prefix='/admin')
db = PickemDB()


@bp.route('/')
def index():
    try:
        picks = db.get_recent_picks(20)  # Get last 20 picks
        return render_template('dashboard.html', picks=picks)
    except Exception as e:
        logging.error("Error loading dashboard %s", e)
        return render_template('error.html', error=str(e), current_year=datetime.now().year), 500

@bp.route('/stats')
def admin_stats():
    """Admin statistics page"""
    try:
        stats = db.get_global_stats()
        guilds = db.get_guild_list()
        
        return render_template(
            'admin/stats.html',
            stats=stats,
            guilds=guilds,
            current_year=datetime.now().year
        )
    except Exception as e:
        logging.error("Error loading admin stats %s", e)
        return f"Error loading stats: {str(e)}", 500

@bp.route('/api/stats')
def api_stats():
    """JSON API endpoint for admin statistics"""
    try:
        stats = db.get_global_stats()
        guilds = db.get_guild_list()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'guilds': [{'id': g[0], 'picks': g[1]} for g in guilds]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)}
        ), 500

@bp.route('/matches')
def matches_page():
    try:
        matches = db.get_all_matches()
        leagues = db.get_leagues(active_only=True)  # Get active leagues
        leagues_data = [
            {
                'league_id': league[0],
                'name': league[1],
                'region': league[3]
            }
            for league in leagues
        ]
        return render_template(
            'admin/matches.html', 
            matches=matches,
            leagues=leagues_data,
            current_year=datetime.now().year
        )
    except Exception as e:
        logging.error(f"Error loading matches: {str(e)}")
        return f"Error loading matches: {str(e)}", 500

@bp.route('/matches', methods=['POST'])
def create_match():
    try:
        print("\n=== Creating Match ===")
        data = request.get_json()
        print(f"Received data: {data}")

        league_id = data.get('league_id')
        team_a = data.get('team_a')
        team_b = data.get('team_b')
        match_date = data.get('match_date')

        if not all([league_id, team_a, team_b, match_date]):
            print("Missing required fields")
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            match_date = datetime.fromisoformat(match_date.replace('T', ' '))
        except ValueError as e:
            print(f"Invalid date format: {e}")
            return jsonify({'error': 'Invalid date format'}), 400

        match_id = db.add_match(int(league_id), team_a, team_b, match_date)
        if match_id:
            print(f"Match created successfully: {match_id}")
            return jsonify({'id': match_id}), 201
        else:
            print("Failed to create match")
            return jsonify({'error': 'Failed to create match'}), 400

    except Exception as e:
        print(f"Error creating match: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@bp.route('/matches/<int:match_id>', methods=['PUT'])
def update_match(match_id):
    try:
        data = request.get_json()
        print(f"Received update data: {data}")

        # Check if this is a winner update
        if 'winner' in data:
            success = db.update_match_result(match_id, data['winner'])
        else:
            # Parse the date string for regular updates
            try:
                match_date = datetime.strptime(data['match_date'], '%Y-%m-%d %H:%M')
            except ValueError as e:
                print(f"Date parsing error: {e}")
                return jsonify({'error': 'Invalid date format. Expected YYYY-MM-DD HH:MM'}), 400

            success = db.update_match(match_id, data['team_a'], data['team_b'], match_date)

        if success:
            return jsonify({'success': True}), 200
        return jsonify({'error': 'Failed to update match'}), 400

    except KeyError as e:
        print(f"Missing required field: {e}")
        return jsonify({'error': f'Missing required field: {str(e)}'}), 400
    except Exception as e:
        print(f"Error updating match: {e}")
        return jsonify({'error': str(e)}), 400

@bp.route('/leaderboard')
def leaderboard():
    """Admin leaderboard management page"""
    try:
        board_type = request.args.get('type', 'global')
        guild_id = request.args.get('guild_id', type=int)
        
        # Get leaderboard data directly from user model
        leaderboard_data = user.get_leaderboard(guild_id if board_type == 'guild' else None)
        
        # Format leaderboard data for template
        formatted_leaderboard = [
            {
                'user_id': entry[0],
                'user_name': f"User {entry[0]}",  # TODO: Get actual username
                'total_picks': entry[1],
                'correct_picks': entry[2],
                'accuracy': entry[2] / entry[1] if entry[1] > 0 else 0,
                'guild_count': entry[3] if len(entry) > 3 else 1
            }
            for entry in leaderboard_data
        ]
        
        # Get global stats for sidebar
        global_stats = db.get_global_stats()
        stats = {
            'total_players': global_stats['total_users'],
            'total_picks': global_stats['total_picks'],
            'avg_accuracy': global_stats['global_accuracy']
        }
        
        # Get list of guilds for dropdown
        guilds = db.get_guild_list()
        
        return render_template(
            'admin/leaderboard.html',
            leaderboard=formatted_leaderboard,
            guilds=guilds,
            stats=stats,
            current_guild=guild_id,
            current_year=datetime.now().year
        )
    except Exception as e:
        logging.error(f"Error loading admin leaderboard: {str(e)}")
        return f"Error loading leaderboard: {str(e)}", 500

@bp.route('/leagues')
def leagues_page():
    """League management page"""
    try:
        leagues_data = db.get_leagues(active_only=False)
        # Convert tuples to dictionaries for template
        leagues_info = [
            {
                'league_id': league[0],
                'name': league[1],
                'description': league[2],
                'region': league[3],
                'is_active': league[4]
            }
            for league in leagues_data
        ]
        return render_template(
            'admin/leagues.html',
            leagues=leagues_info,
            current_year=datetime.now().year
        )
    except Exception as e:
        logging.error(f"Error loading leagues: {str(e)}")
        return f"Error loading leagues: {str(e)}", 500

@bp.route('/leagues', methods=['POST'])
def add_league():
    """Add a new league"""
    data = request.json
    try:
        league_id = db.add_league(
            name=data['name'],
            description=data['description'],
            region=data['region']
        )
        return jsonify({'success': True, 'league_id': league_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/leagues/<int:league_id>', methods=['PUT'])
def update_league(league_id):
    """Update league details"""
    data = request.json
    try:
        success = db.update_league(
            league_id=league_id,
            name=data['name'],
            description=data['description'],
            region=data['region'],
            is_active=data['is_active']
        )
        return jsonify({'success': success}), 200 if success else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400