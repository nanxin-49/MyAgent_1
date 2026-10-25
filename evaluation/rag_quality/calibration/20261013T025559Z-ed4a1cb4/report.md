# a05-threshold-dev-v2 lexical retrieval baseline (dev)

Real Chroma HTTP; no model calls. Labels frozen before retrieval; user-approved v2 after human discussion/candidate verification.
Production call paths/configuration unchanged. B-prod not executed (no paid-model authorization).
8 answerable / 8 no-answer. One gold chunk per answerable query. Final usable hits determine metrics.

```json
{
  "1": {
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
    "diagnostic_candidate_Recall@5": {
      "value": 1.0,
      "numerator": 8,
      "denominator": 8
    },
    "latency_ms": {
      "p50": 26.171350007643923,
      "p95": 34.57660001004115,
      "count": 16,
      "includes_failed_requests": true
    },
    "status_counts": {
      "low_confidence": 16
    },
    "failure_counts": {
      "gold_below_threshold": 8,
      "none": 8
    },
    "retrieval_calls": 16,
    "model_calls": 0,
    "model_tokens": 0,
    "model_cost_usd": 0
  },
  "2": {
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
    "diagnostic_candidate_Recall@5": {
      "value": 1.0,
      "numerator": 8,
      "denominator": 8
    },
    "latency_ms": {
      "p50": 27.649950032355264,
      "p95": 31.66417498141527,
      "count": 16,
      "includes_failed_requests": true
    },
    "status_counts": {
      "low_confidence": 16
    },
    "failure_counts": {
      "gold_below_threshold": 8,
      "none": 8
    },
    "retrieval_calls": 16,
    "model_calls": 0,
    "model_tokens": 0,
    "model_cost_usd": 0
  }
}
```

| Case | Query | Gold rank | Candidate rank (diagnostic) | Status | Failure reason |
| --- | --- | --- | --- | --- | --- |
| DEV-01 | 账户出现陌生人登录时，演示系统会采取哪些措施？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-02 | 配送人员每天在哪个时段送件？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-03 | 已下单但想改收货地址，应该在发货前还是之后联系？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-04 | 花费十二元按基础积分规则能累积几分？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-05 | 银卡购物折扣和金卡购物折扣各是多少？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-06 | 如果用户界面加载很慢，有哪些网络排查方法？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-07 | 如果收货地址比较偏远，包裹可能要多等几天？ | None | 1 | low_confidence | gold_below_threshold |
| DEV-08 | 申请退的钱能超过购买订单的总额吗？ | None | 3 | low_confidence | gold_below_threshold |
| DEV-09 | 积分清零之前，商家会提前几天发送到期提醒？ | None | None | low_confidence | none |
| DEV-10 | 包裹运输途中损坏，演示政策赔付多少现金？ | None | None | low_confidence | none |
| DEV-11 | 忘记登录密码而且手机邮箱都不能用，需要提交哪种身份证件？ | None | None | low_confidence | none |
| DEV-12 | 银卡折扣可以与购物优惠券一起使用吗？ | None | None | low_confidence | none |
| DEV-13 | 收货地址变更是否需要支付十元手续费？ | None | None | low_confidence | none |
| DEV-14 | 客服夜间处理订单异常的服务时间是什么？ | None | None | low_confidence | none |
| DEV-15 | 银行卡支付失败连续三次后会冻结卡片吗？ | None | None | low_confidence | none |
| DEV-16 | 超过21天后，现行隔离换货政策是否允许付费延长窗口？ | None | None | low_confidence | none |

Recall@K: correct frozen gold chunk in final top K / all answerable cases (including failures).
MRR: sum of 1/final gold rank, missing=0, / all answerable cases; ranks truncated at 5.
No-answer FPR: usable with nonempty hits/citations on no-answer cases / all no-answer cases.
Citation precision: emitted citations whose chunk contains the labelled evidence / all emitted citations, including no-answer cases.
Latency: wall time for tool execution plus final N06/N07 validation, excludes ingest/startup; first repeat includes cold reads; linear interpolated percentiles.
Repeat groups are scored separately; repeats are not independent questions or populations.
Candidate Recall is diagnostic, may include low-score chunks, and is never usable-evidence Recall.
No Agent answers generated; Task Success and answer factual accuracy remain unmeasured.
