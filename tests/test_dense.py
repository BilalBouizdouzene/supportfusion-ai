import numpy as np
import pytest


faiss = pytest.importorskip("faiss")


def test_faiss_cpu_round_trip():
    index = faiss.IndexFlatIP(3)
    index.add(np.asarray([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype="float32"))
    scores, positions = index.search(np.asarray([[0.9, 0.1, 0.0]], dtype="float32"), 1)
    assert positions[0][0] == 0
    assert scores[0][0] > 0.8
