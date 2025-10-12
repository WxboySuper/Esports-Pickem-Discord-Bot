import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://lol.fandom.com/api.php"


async def make_request(session, params):
    async with session.get(BASE_URL, params=params) as response:
        response.raise_for_status()
        return await response.json()


async def get_tournaments(session, tournament_name):
    params = {
        "action": "query",
        "format": "json",
        "list": "tournaments",
        "tournaments_where": "T.Name = ?",
        "tournaments_params": tournament_name,
    }
    return await make_request(session, params)


async def get_matches(session, tournament_name):
    params = {
        "action": "query",
        "format": "json",
        "list": "matchschedule",
        "matchschedule_where": "MS.Tournament = ?",
        "matchschedule_params": tournament_name,
    }
    return await make_request(session, params)


async def get_match_results(session, tournament_name, team1, team2):
    params = {
        "action": "query",
        "format": "json",
        "list": "matchschedule",
        "matchschedule_where": (
            "MS.Tournament = ? AND MS.Team1 = ? AND MS.Team2 = ?"
        ),
        "matchschedule_params": f"{tournament_name},{team1},{team2}",
    }
    response = await make_request(session, params)
    results = response.get("query", {}).get("matchschedule")

    if isinstance(results, list):
        return results
    elif results:
        return [results]
    else:
        return []
