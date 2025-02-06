class Match:
    def __init__(self, match_id, team_a, team_b, best_of, date):
        self.match_id = match_id
        self.team_a = team_a
        self.team_b = team_b
        self.best_of = best_of
        self.date = date
        self.winner = None
        self.score = None

    def set_winner(self, winner, score):
        self.winner = winner
        self.score = score

    def get_match_info(self):
        return {
            "match_id": self.match_id,
            "team_a": self.team_a,
            "team_b": self.team_b,
            "best_of": self.best_of,
            "date": self.date,
            "winner": self.winner,
            "score": self.score,
        }