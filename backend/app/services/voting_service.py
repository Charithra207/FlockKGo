from collections import defaultdict


class RankedChoiceVoting:
    def __init__(self, ml_scores=None):
        self.ml_scores = ml_scores or {}

    def _next_choice(self, ballot, eliminated):
        for item in sorted(ballot, key=lambda x: x["rank"]):
            candidate_id = str(item["recommendation_id"])
            if candidate_id not in eliminated:
                return candidate_id
        return None

    def run_election(self, votes) -> dict:
        if not votes:
            return {"error": "No votes submitted"}

        all_candidates = set()
        for ballot in votes:
            for item in ballot:
                all_candidates.add(str(item["recommendation_id"]))

        eliminated = set()
        rounds = []
        total_voters = len(votes)
        current_tally = {}

        for round_number in range(1, 21):
            tally = defaultdict(int)
            for ballot in votes:
                choice = self._next_choice(ballot, eliminated)
                if choice:
                    tally[choice] += 1

            current_tally = dict(tally)
            if not current_tally:
                break

            for candidate, count in current_tally.items():
                if count / total_voters > 0.5:
                    ml_top = max(self.ml_scores, key=self.ml_scores.get) if self.ml_scores else None
                    rounds.append({"round": round_number, "tally": current_tally, "winner": candidate})
                    return {
                        "winner": candidate,
                        "rounds_taken": round_number,
                        "round_by_round": rounds,
                        "final_tally": current_tally,
                        "total_voters": total_voters,
                        "ml_top_pick": ml_top,
                        "ml_vote_agreement": "agreement" if ml_top == candidate else "disagreement",
                    }

            min_votes = min(current_tally.values())
            lowest = [candidate for candidate, count in current_tally.items() if count == min_votes]
            eliminated_candidate = lowest[0]
            if len(lowest) > 1:
                eliminated_candidate = min(lowest, key=lambda cid: self.ml_scores.get(cid, 0.0))

            eliminated.add(eliminated_candidate)
            rounds.append({"round": round_number, "tally": current_tally, "eliminated": eliminated_candidate})

            remaining = all_candidates - eliminated
            if len(remaining) <= 1:
                winner = list(remaining)[0] if remaining else eliminated_candidate
                ml_top = max(self.ml_scores, key=self.ml_scores.get) if self.ml_scores else None
                return {
                    "winner": winner,
                    "rounds_taken": round_number,
                    "round_by_round": rounds,
                    "final_tally": current_tally,
                    "total_voters": total_voters,
                    "ml_top_pick": ml_top,
                    "ml_vote_agreement": "agreement" if ml_top == winner else "disagreement",
                }

        ml_top = max(self.ml_scores, key=self.ml_scores.get) if self.ml_scores else None
        winner = max(current_tally, key=current_tally.get) if current_tally else None
        return {
            "winner": winner,
            "rounds_taken": 20,
            "round_by_round": rounds,
            "final_tally": current_tally,
            "total_voters": total_voters,
            "ml_top_pick": ml_top,
            "ml_vote_agreement": "agreement" if ml_top == winner else "disagreement",
        }
