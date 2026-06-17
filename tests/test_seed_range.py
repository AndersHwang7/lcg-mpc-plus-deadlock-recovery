# Inha University & RODIX Inc, Anders Hwang
from mr_deadlock.experiments.seeds import expand_seeds


def test_seed_range_stop_is_inclusive():
    assert expand_seeds({"seed_range": {"start": 0, "stop": 4}}) == [0, 1, 2, 3, 4]


def test_seed_range_count():
    assert expand_seeds({"seed_range": {"start": 10, "count": 3}}) == [10, 11, 12]

