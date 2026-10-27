import numpy as np

from app.router.bandit import LinUCB


def test_bandit_learns_best_arm():
    bandit = LinUCB(dim=3, alpha=0.2)
    ctx = np.array([1.0, 0.5, 0.2])
    # arm 'good' rewards 0.8, arm 'bad' rewards 0.1
    for _ in range(60):
        chosen, _ = bandit.select(ctx, ["good", "bad"])
        bandit.update(chosen, ctx, 0.8 if chosen == "good" else 0.1)
    chosen, scores = bandit.select(ctx, ["good", "bad"])
    assert chosen == "good"


def test_bandit_explores_unknown_arms_first():
    bandit = LinUCB(dim=3)
    ctx = np.array([1.0, 0.0, 0.0])
    _, scores = bandit.select(ctx, ["a", "b", "c"])
    # identical unexplored arms -> identical UCB scores
    assert scores["a"] == scores["b"] == scores["c"]


def test_save_and_load_roundtrip(tmp_path):
    bandit = LinUCB(dim=2, alpha=0.3)
    ctx = np.array([1.0, 2.0])
    for _ in range(5):
        bandit.update("x", ctx, 0.5)
    path = tmp_path / "bandit.npz"
    bandit.save(path)
    loaded = LinUCB.load(path)
    assert loaded is not None
    assert loaded.dim == 2
    assert "x" in loaded.arms
    assert np.allclose(loaded.arms["x"]["A"], bandit.arms["x"]["A"])
