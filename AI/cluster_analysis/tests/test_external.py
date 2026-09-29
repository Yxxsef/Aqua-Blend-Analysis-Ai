import pytest

from xxcluster.measures.validation.external import AdjustedRand


def test_adjusted_rand_identical_partition():
    index = AdjustedRand()
    score = index.score(
        labels=[0, 0, 1, 1],
        labels_true=[0, 0, 1, 1],
    )
    assert score == 1.0


def test_adjusted_rand_relabelled_partition():
    index = AdjustedRand()
    score = index.score(
        labels=[5, 5, 8, 8],
        labels_true=[0, 0, 1, 1],
    )
    assert score == 1.0


def test_adjusted_rand_is_symmetric():
    index = AdjustedRand()

    labels_a = [0, 0, 1, 1, 2, 2]
    labels_b = [0, 1, 1, 2, 2, 0]

    score_ab = index.score(labels=labels_a, labels_true=labels_b)
    score_ba = index.score(labels=labels_b, labels_true=labels_a)

    assert score_ab == pytest.approx(score_ba)


def test_adjusted_rand_mismatched_lengths():
    index = AdjustedRand()

    with pytest.raises(ValueError, match="the two must describe the same observations"):
        index.score(
            labels=[0, 1],
            labels_true=[0, 1, 1],
        )


def test_adjusted_rand_random_partitions_near_zero():
    index = AdjustedRand()

    labels_true = [0] * 25 + [1] * 25 + [2] * 25 + [3] * 25
    labels = [0, 1, 2, 3] * 25

    score = index.score(
        labels=labels,
        labels_true=labels_true,
    )

    assert abs(score) < 0.1