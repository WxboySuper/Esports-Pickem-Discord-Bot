from datetime import datetime, timedelta
import sqlite3

def test_db_initialization(test_db):
    """Test database initialization"""
    assert test_db is not None
    assert isinstance(test_db.db_path, str)
    assert test_db.db_path.startswith("test_pickem_")
    assert test_db.db_path.endswith(".db")

def test_add_match(test_db, sample_match_data):
    """Test adding a match"""
    match_id = test_db.add_match(
        league_id=1,
        team_a=sample_match_data['team_a'],
        team_b=sample_match_data['team_b'],
        match_date=sample_match_data['match_date'],
        match_name=sample_match_data['match_name']
    )
    assert match_id is not None
    assert match_id > 0

def test_make_pick(test_db, sample_match_data):
    """Test making a pick"""
    # Add a match first
    match_id = test_db.add_match(
        league_id=1,
        team_a=sample_match_data['team_a'],
        team_b=sample_match_data['team_b'],
        match_date=datetime.now() + timedelta(days=1),
        match_name=sample_match_data['match_name']
    )
    
    # Make a pick
    success = test_db.make_pick(
        guild_id=123,
        user_id=456,
        match_id=match_id,
        pick=sample_match_data['team_a']
    )
    assert success is True

    # Verify pick
    pick = test_db.get_user_pick(123, 456, match_id)
    assert pick == sample_match_data['team_a']

def test_update_match_result(test_db, sample_match_data):
    """Test updating match result"""
    # Add a match
    match_id = test_db.add_match(
        league_id=1,
        team_a=sample_match_data['team_a'],
        team_b=sample_match_data['team_b'],
        match_date=datetime.now(),
        match_name=sample_match_data['match_name']
    )
    
    # Update result
    success = test_db.update_match_result(match_id, sample_match_data['team_a'])
    assert success is True

def test_get_leaderboard(test_db, sample_match_data):
    """Test leaderboard functionality"""
    # Add matches with all correct picks
    match_ids = []
    base_date = datetime.now() - timedelta(hours=1)  # Set base date 1 hour ago
    
    for i in range(10):
        match_id = test_db.add_match(
            league_id=1,
            team_a=f"Team A{i}",
            team_b=f"Team B{i}",
            match_date=base_date + timedelta(minutes=i),  # Spread matches across time
            match_name=sample_match_data['match_name']
        )
        match_ids.append(match_id)
        
        # Verify match was created
        assert match_id is not None, f"Failed to create match {i}"
        
        # Make pick and verify database state
        with sqlite3.connect(test_db.db_path) as conn:
            c = conn.cursor()
            
            # Verify match exists and is open
            match_exists = c.execute("""
                SELECT COUNT(*) FROM matches 
                WHERE match_id = ? AND winner IS NULL
            """, (match_id,)).fetchone()[0]
            assert match_exists == 1, f"Match {match_id} not found or already closed"
            
            # Make pick
            pick_success = test_db.make_pick(123, 456, match_id, f"Team A{i}")
            assert pick_success, f"Failed to make pick for match {match_id}"
            
            # Verify pick was recorded
            pick_recorded = c.execute("""
                SELECT COUNT(*) FROM picks 
                WHERE match_id = ? AND guild_id = ? AND user_id = ?
            """, (match_id, 123, 456)).fetchone()[0]
            assert pick_recorded == 1, f"Pick not found for match {match_id}"
        
        # Update match result
        result_success = test_db.update_match_result(match_id, f"Team A{i}")
        assert result_success, f"Failed to update result for match {match_id}"

    # Verify the database state
    with sqlite3.connect(test_db.db_path) as conn:
        c = conn.cursor()
        
        # Check matches
        # skipcq: PYL-C0209
        matches_count = c.execute("SELECT COUNT(*) FROM matches WHERE match_id IN ({})".format(
            ','.join('?' * len(match_ids))
        ), match_ids).fetchone()[0]
        assert matches_count == 10, f"Expected 10 matches, got {matches_count}"
        
        # Check picks
        picks_count = c.execute(
            "SELECT COUNT(*) FROM picks WHERE guild_id = ? AND match_id IN ({})"  # skipcq: PYL-C0209
            .format(','.join('?' * len(match_ids))), 
            [123] + match_ids
        ).fetchone()[0]
        assert picks_count == 10, f"Expected 10 picks, got {picks_count}"
        
        # Check winners are set
        winners_count = c.execute(
            "SELECT COUNT(*) FROM matches WHERE winner IS NOT NULL AND match_id IN ({})"  # skipcq: PYL-C0209
            .format(','.join('?' * len(match_ids))),
            match_ids
        ).fetchone()[0]
        assert winners_count == 10, f"Expected 10 winners set, got {winners_count}"
        
        # Check correct picks
        # skipcq: PYL-C0209
        correct_picks = c.execute("""
            SELECT COUNT(*) 
            FROM picks p
            JOIN matches m ON p.match_id = m.match_id
            WHERE p.guild_id = ? 
            AND p.is_correct = 1
            AND m.match_id IN ({})
        """.format(','.join('?' * len(match_ids))), 
        [123] + match_ids
        ).fetchone()[0]
        assert correct_picks == 10, f"Expected 10 correct picks, got {correct_picks}"
    
    # Get leaderboard and verify results
    leaderboard = test_db.get_leaderboard_by_timeframe(123, 'all')
    assert len(leaderboard) > 0, "Leaderboard should have entries"
    
    # Verify first entry
    entry = leaderboard[0]
    assert entry[0] == 456, "Expected user_id 456"
    assert entry[1] == 10, "Expected 10 completed picks"
    assert entry[2] == 10, "Expected 10 correct picks"
    assert entry[3] == 1.0, "Expected perfect accuracy"

def test_invalid_operations(test_db):
    """Test handling of invalid operations"""
    # Test invalid match ID
    assert test_db.get_match_details(999) is None
    
    # Test invalid pick
    assert test_db.make_pick(123, 456, 999, "Invalid Team") is False
