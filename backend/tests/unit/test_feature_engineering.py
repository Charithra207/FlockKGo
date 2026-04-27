from datetime import date

from app.ml.feature_engineering import build_feature_matrix, build_feature_vector


class Dummy:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def make_response(**kwargs):
    payload = {
        "budget_min": 1000,
        "budget_max": 3000,
        "vibes": ["beach", "food"],
        "climate_pref": "warm",
        "activity_level": "moderate",
        "available_start": date(2026, 7, 1),
        "available_end": date(2026, 7, 16),
        "excluded_destinations": ["A", "B"],
    }
    payload.update(kwargs)
    return Dummy(**payload)


def test_vector_has_correct_length():
    assert len(build_feature_vector(make_response())) == 16


def test_budget_normalization_correct():
    vector = build_feature_vector(make_response(budget_min=1000, budget_max=3000))
    assert vector[0] == 0.2
    assert vector[1] == 0.2


def test_vibe_one_hot_encoding():
    vector = build_feature_vector(make_response(vibes=["beach", "city"]))
    assert vector[2] == 1.0
    assert vector[9] == 1.0


def test_all_values_between_0_and_1():
    vector = build_feature_vector(make_response())
    assert all(0.0 <= x <= 1.0 for x in vector)


def test_feature_matrix_shape():
    matrix = build_feature_matrix([make_response(), make_response(vibes=["adventure"])])
    assert matrix.shape == (2, 16)
