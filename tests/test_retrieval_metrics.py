from ml.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from ml.retrieval.rrf import reciprocal_rank_fusion


def test_rrf_does_not_mix_raw_scores():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert fused[0][0] == "b"


def test_retrieval_metrics():
    ranked = ["x", "b", "c"]
    relevant = {"b"}
    assert recall_at_k(ranked, relevant, 2) == 1
    assert reciprocal_rank(ranked, relevant) == 0.5
    assert ndcg_at_k(ranked, relevant, 3) > 0
