# B0 lexical development v2 threshold calibration

Real HTTP candidate capture; 16 DEV questions only, two repeats scored separately. No test evaluation.
Raw score=1-Chroma distance; original doubles/distances retained, not clipped or assumed probabilistic.
Offline replay: production build_hit + N06 eligibility/validate_hits + N07 finalize on immutable verified snapshot.
Grid 0.00..1.00 by 0.01 is preregistered and min_score-valid, not an assertion that scores lie in [0,1].
Objective: FPR<=1/8 then Recall@5 max; ties: FPR min, MRR max, citation precision max, threshold max.

```json
{
  "status": "locked",
  "split": "dev",
  "selected_threshold": 0.2,
  "selected_threshold_hex": "0x1.999999999999ap-3",
  "objective": "max final Recall@5 subject to dev no-answer false positives <=1/8",
  "tie_break": [
    "Recall@5 max",
    "FPR count min",
    "MRR max",
    "citation precision max (N/A last)",
    "threshold max"
  ],
  "threshold_grid": [
    0.0,
    0.01,
    0.02,
    0.03,
    0.04,
    0.05,
    0.06,
    0.07,
    0.08,
    0.09,
    0.1,
    0.11,
    0.12,
    0.13,
    0.14,
    0.15,
    0.16,
    0.17,
    0.18,
    0.19,
    0.2,
    0.21,
    0.22,
    0.23,
    0.24,
    0.25,
    0.26,
    0.27,
    0.28,
    0.29,
    0.3,
    0.31,
    0.32,
    0.33,
    0.34,
    0.35,
    0.36,
    0.37,
    0.38,
    0.39,
    0.4,
    0.41,
    0.42,
    0.43,
    0.44,
    0.45,
    0.46,
    0.47,
    0.48,
    0.49,
    0.5,
    0.51,
    0.52,
    0.53,
    0.54,
    0.55,
    0.56,
    0.57,
    0.58,
    0.59,
    0.6,
    0.61,
    0.62,
    0.63,
    0.64,
    0.65,
    0.66,
    0.67,
    0.68,
    0.69,
    0.7,
    0.71,
    0.72,
    0.73,
    0.74,
    0.75,
    0.76,
    0.77,
    0.78,
    0.79,
    0.8,
    0.81,
    0.82,
    0.83,
    0.84,
    0.85,
    0.86,
    0.87,
    0.88,
    0.89,
    0.9,
    0.91,
    0.92,
    0.93,
    0.94,
    0.95,
    0.96,
    0.97,
    0.98,
    0.99,
    1.0
  ],
  "score_kind": "one_minus_chroma_distance",
  "score_meaning": "1 - actual Chroma distance; heuristic, not probability or assumed standard cosine",
  "direction": "higher passes; score >= threshold",
  "float_rule": "full stored IEEE754 doubles, no rounding/epsilon/clip; original distance retained",
  "parameter_bounds": "[0,1] per KnowledgeBase.min_score, not score bounds",
  "observed_score_range": [
    -0.011528574334179087,
    0.3374408823545323
  ],
  "baseline_035_dev_metrics": {
    "threshold": 0.35,
    "Recall@1": {
      "value": 0.0,
      "numerator": 0,
      "denominator": 8
    },
    "Recall@3": {
      "value": 0.0,
      "numerator": 0,
      "denominator": 8
    },
    "Recall@5": {
      "value": 0.0,
      "numerator": 0,
      "denominator": 8
    },
    "MRR": {
      "value": 0.0,
      "numerator": 0,
      "denominator": 8
    },
    "no_answer_false_positive_rate": {
      "value": 0.0,
      "numerator": 0,
      "denominator": 8
    },
    "citation_evidence_precision": {
      "value": null,
      "numerator": 0,
      "denominator": 0
    },
    "correct_refusals": 8,
    "no_returned_hits": 16,
    "status_counts": {
      "low_confidence": 16
    }
  },
  "selected_dev_metrics": {
    "threshold": 0.2,
    "Recall@1": {
      "value": 0.25,
      "numerator": 2,
      "denominator": 8
    },
    "Recall@3": {
      "value": 0.25,
      "numerator": 2,
      "denominator": 8
    },
    "Recall@5": {
      "value": 0.25,
      "numerator": 2,
      "denominator": 8
    },
    "MRR": {
      "value": 0.25,
      "numerator": 2.0,
      "denominator": 8
    },
    "no_answer_false_positive_rate": {
      "value": 0.125,
      "numerator": 1,
      "denominator": 8
    },
    "citation_evidence_precision": {
      "value": 0.6667,
      "numerator": 2,
      "denominator": 3
    },
    "correct_refusals": 7,
    "no_returned_hits": 13,
    "status_counts": {
      "low_confidence": 13,
      "usable": 3
    }
  },
  "degenerate_zero_recall": false,
  "reason": "Apply preregistered grid/objective/tie-break solely to 16 development cases; test scores never consumed.",
  "data_binding_sha256": {
    "corpus_v1.json": "f1ca8679113529a54c6cb229f29b669e8e385509e9a08ad6aac8cb8d9d1e6b39",
    "dev_dataset_v2.json": "e49037acd561248f93b5e72ce23ab1d20b3fed1b9d7910b2ba8448f64d9fb002",
    "freeze_v2.json": "7ea0b1c40d430de13fead53ed1f21af082410efc7c0cdf6bb967c22030524f79"
  },
  "as_of": "2026-10-12T00:00:00Z",
  "top_k": 5,
  "embedding_version": "char-bigram-1024-v1",
  "dimensions": 1024,
  "raw_observations_sha256": "31a70535aea795466c09948ba652f550474f778e2efda26c9b7a4ffa2c29859a",
  "curve_csv_sha256": "f39a22e47582240542e42c2e5f2879f978ab64a4d0e27cc0a0d9bf86a68c5bfb",
  "head": "4685741e3fcdde23c3646afc48754d5196aa6f8e",
  "python": "3.12.3",
  "packages": {
    "chromadb-client": "0.5.23",
    "pydantic": "2.10.3",
    "anthropic": "0.40.0",
    "httpx": "0.28.1",
    "pytest": "8.3.4"
  },
  "code_sha256": {
    "mcp/knowledge_embeddings.py": "bca9827430c4d871cf9c7608b2d4a38b086d2c38876d2f4cb0bdd11bf1ec3033",
    "mcp/knowledge_base.py": "4a0b8518ce3749a97a49a287044af3ce8cb9cd54ad3b96872773ae8e8aa7883d",
    "mcp/rag_contract.py": "33c8dbddb9c8a173afbfaa886273c113f59b273b1e32689ce0191c74aa48e527",
    "mcp/tool_manager.py": "af90e5a419503ece6d0b910f0134c3901343596624cb81390e61dc8101ad6844",
    "evaluation/rag_quality/run_baseline.py": "60e933a70291ada708b029ee87e7bb917bbc052c480dee36ceb26bec65035c29",
    "uv.lock": "392b74a8798b2a576cf33aeb13fa6ab73c5ecfe2a27eb669cae6a88e64b5687b",
    "evaluation/rag_quality/dev_calibration.py": "acf191f4e73265bafb3e14ca022c35e3fcce34fc4a3f9a540b7ca432d58707b0"
  },
  "protocol_sha256": "fb97ccaa891c29dfb9a8c7cf5c96c89160c9b57ef8671bf8983b12ae794d3556",
  "snapshot_sha256": "76e3bdffdd34e3d74db4f7ab68debc2aec44966df728a048ba827bf515334676",
  "real_http_candidate_capture": true,
  "repeats_scored_separately": true,
  "test_scores_consumed": false,
  "test_evaluation_executed": false,
  "production_configuration_changed": false,
  "model_calls": 0
}
```

Full 101-point Recall@1/3/5, MRR, FPR/FP count, citation precision, refusal/empty counts in CSV.
Offline sweep latency is not a real HTTP latency measurement; capture latency is in summary.json.
A low FPR with zero Recall is degenerate and must not be called a useful quality improvement.
After acceptance: use this locked JSON/hash for ONE same-v2 30-case B0-calibrated run; no retrospective threshold change.
Small shared corpus and only eight negatives; cannot prove generalization or answer completeness.
