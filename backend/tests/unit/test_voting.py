import uuid

from app.services.voting_service import RankedChoiceVoting


def test_clear_majority_wins_round_1():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    votes = [
        [{"rank": 1, "recommendation_id": a}],
        [{"rank": 1, "recommendation_id": a}],
        [{"rank": 1, "recommendation_id": b}],
    ]
    result = RankedChoiceVoting().run_election(votes)
    assert result["winner"] == a


def test_elimination_and_redistribution():
    a, b, c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    votes = [
        [{"rank": 1, "recommendation_id": a}, {"rank": 2, "recommendation_id": b}],
        [{"rank": 1, "recommendation_id": c}, {"rank": 2, "recommendation_id": b}],
        [{"rank": 1, "recommendation_id": b}],
    ]
    result = RankedChoiceVoting().run_election(votes)
    assert result["winner"] == b


def test_ml_tiebreaker_used_on_tie():
    a, b, c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    votes = [[{"rank": 1, "recommendation_id": a}], [{"rank": 1, "recommendation_id": b}], [{"rank": 1, "recommendation_id": c}]]
    result = RankedChoiceVoting(ml_scores={a: 0.8, b: 0.9, c: 0.1}).run_election(votes)
    assert result["winner"] in {a, b}


def test_empty_votes_returns_error():
    result = RankedChoiceVoting().run_election([])
    assert "error" in result


def test_single_voter_first_choice_wins():
    a = str(uuid.uuid4())
    result = RankedChoiceVoting().run_election([[{"rank": 1, "recommendation_id": a}]])
    assert result["winner"] == a


def test_rounds_capped_at_20():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    votes = [[{"rank": 1, "recommendation_id": a}], [{"rank": 1, "recommendation_id": b}]]
    result = RankedChoiceVoting().run_election(votes)
    assert result["rounds_taken"] <= 20
