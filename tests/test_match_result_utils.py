import pytest
from unittest.mock import MagicMock, AsyncMock
from src.match_result_utils import save_result_and_update_picks
from src.models import Match, Pick, Result


@pytest.mark.asyncio
async def test_save_result_and_update_picks_updates_status_and_score():
    # Setup
    session = AsyncMock()
    match = Match(id=1, team1="T1", team2="Gen.G", best_of=3)
    winner = "T1"
    score_str = "2-0"

    # Mock existing picks
    # Pick 1: Correct
    pick1 = Pick(
        id=1, match_id=1, chosen_team="T1", user_id=101, status="pending"
    )
    # Pick 2: Incorrect
    pick2 = Pick(
        id=2, match_id=1, chosen_team="Gen.G", user_id=102, status="pending"
    )

    mock_result_proxy = MagicMock()
    mock_result_proxy.all.return_value = [pick1, pick2]
    session.exec.return_value = mock_result_proxy

    # Execute
    result = await save_result_and_update_picks(
        session, match, winner, score_str
    )

    # Verify Result creation
    assert isinstance(result, Result)
    assert result.winner == "T1"
    assert result.score == "2-0"
    session.add.assert_any_call(result)

    # Verify Pick updates
    # Pick 1 should be correct, status="correct", score=10
    assert pick1.is_correct is True
    assert pick1.status == "correct"
    assert pick1.score == 10
    session.add.assert_any_call(pick1)

    # Pick 2 should be incorrect, status="incorrect", score=0
    assert pick2.is_correct is False
    assert pick2.status == "incorrect"
    assert pick2.score == 0
    session.add.assert_any_call(pick2)
