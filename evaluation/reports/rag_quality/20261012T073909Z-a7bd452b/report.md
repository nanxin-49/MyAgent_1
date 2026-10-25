# A05-P1 B0 lexical retrieval baseline

Real Chroma HTTP; no model calls. Labels frozen before retrieval; human acceptance pending.
Production call paths/configuration unchanged. B-prod not executed (no paid-model authorization).
21 answerable / 9 no-answer. One gold chunk per answerable query. Final usable hits determine metrics.

```json
{
  "1": {
    "Recall@1": {
      "value": 0.2857,
      "numerator": 6,
      "denominator": 21
    },
    "Recall@3": {
      "value": 0.2857,
      "numerator": 6,
      "denominator": 21
    },
    "Recall@5": {
      "value": 0.2857,
      "numerator": 6,
      "denominator": 21
    },
    "MRR": {
      "value": 0.2857,
      "numerator": 6.0,
      "denominator": 21
    },
    "no_answer_false_positive_rate": {
      "value": 0.4444,
      "numerator": 4,
      "denominator": 9
    },
    "citation_evidence_precision": {
      "value": 0.6,
      "numerator": 6,
      "denominator": 10
    },
    "diagnostic_candidate_Recall@5": {
      "value": 0.8571,
      "numerator": 18,
      "denominator": 21
    },
    "latency_ms": {
      "p50": 27.197150004212745,
      "p95": 35.68548501061741,
      "count": 30,
      "includes_failed_requests": true
    },
    "status_counts": {
      "low_confidence": 20,
      "usable": 10
    },
    "failure_counts": {
      "gold_not_in_top5_candidates": 3,
      "gold_below_threshold": 12,
      "none": 11,
      "false_positive_no_answer": 4
    },
    "retrieval_calls": 30,
    "model_calls": 0,
    "model_tokens": 0,
    "model_cost_usd": 0
  },
  "2": {
    "Recall@1": {
      "value": 0.2857,
      "numerator": 6,
      "denominator": 21
    },
    "Recall@3": {
      "value": 0.2857,
      "numerator": 6,
      "denominator": 21
    },
    "Recall@5": {
      "value": 0.2857,
      "numerator": 6,
      "denominator": 21
    },
    "MRR": {
      "value": 0.2857,
      "numerator": 6.0,
      "denominator": 21
    },
    "no_answer_false_positive_rate": {
      "value": 0.4444,
      "numerator": 4,
      "denominator": 9
    },
    "citation_evidence_precision": {
      "value": 0.6,
      "numerator": 6,
      "denominator": 10
    },
    "diagnostic_candidate_Recall@5": {
      "value": 0.8571,
      "numerator": 18,
      "denominator": 21
    },
    "latency_ms": {
      "p50": 28.452700018533505,
      "p95": 38.83341999317053,
      "count": 30,
      "includes_failed_requests": true
    },
    "status_counts": {
      "low_confidence": 20,
      "usable": 10
    },
    "failure_counts": {
      "gold_not_in_top5_candidates": 3,
      "gold_below_threshold": 12,
      "none": 11,
      "false_positive_no_answer": 4
    },
    "retrieval_calls": 30,
    "model_calls": 0,
    "model_tokens": 0,
    "model_cost_usd": 0
  }
}
```

| Case | Query | Gold rank | Candidate rank (diagnostic) | Status | Failure reason |
| --- | --- | --- | --- | --- | --- |
| A05-01 | 买完东西想把钱退回来，多久之内可以申请？ | None | None | low_confidence | gold_not_in_top5_candidates |
| A05-02 | 忘掉登录口令了怎样找回账户？ | None | 1 | low_confidence | gold_below_threshold |
| A05-03 | 收到货的进展能在哪里看？ | None | 4 | low_confidence | gold_below_threshold |
| A05-04 | 普通送货大概几天能到？ | None | 4 | low_confidence | gold_below_threshold |
| A05-05 | 急着拿到包裹，快送收费多少？ | None | None | low_confidence | gold_not_in_top5_candidates |
| A05-06 | 购物攒的分怎么折成钱用？ | None | None | low_confidence | gold_not_in_top5_candidates |
| A05-07 | 软件一打开就闪退该怎么办？ | None | 3 | low_confidence | gold_below_threshold |
| A05-08 | 保护账号可以启用什么二次确认？ | None | 3 | low_confidence | gold_below_threshold |
| A05-09 | 生日那个月买东西积分享受什么待遇？ | None | 1 | low_confidence | gold_below_threshold |
| A05-10 | 退款数额很大时还要谁同意？ | None | 1 | low_confidence | gold_below_threshold |
| A05-11 | 账户安全的密码长度至少是多少？ | 1 | 1 | usable | none |
| A05-12 | 登录失败401和500服务器错误分别是什么原因？ | None | 1 | low_confidence | gold_below_threshold |
| A05-13 | 会员等级中银卡和金卡的消费门槛分别是多少？ | None | 1 | low_confidence | gold_below_threshold |
| A05-14 | 配送说明中免运费的门槛是多少，不是退款审批金额？ | None | 1 | low_confidence | gold_below_threshold |
| A05-15 | 订单查询中物流信息多久更新，而不是多久送达？ | None | 1 | low_confidence | gold_below_threshold |
| A05-16 | 退款政策是否意味着不用查实时订单就保证退款成功？ | 1 | 1 | usable | none |
| A05-17 | 积分有效期是一年还是订单退款的七天？ | None | 2 | low_confidence | gold_below_threshold |
| A05-18 | 已经发货超过七天没收到，订单查询指南建议做什么？ | 1 | 1 | usable | none |
| A05-19 | 退款政策规定退款到账需要几个工作日？ | None | None | usable | false_positive_no_answer |
| A05-20 | 账户安全说明中客服可以替我关闭两步验证吗？ | None | None | usable | false_positive_no_answer |
| A05-21 | 订单查询：订单ORD-999今天到哪了？ | None | None | usable | false_positive_no_answer |
| A05-22 | 苹果手机电池的官方保修期是多少？ | None | None | low_confidence | none |
| A05-23 | 会员与积分：金卡会费每年多少钱？ | None | None | usable | false_positive_no_answer |
| A05-24 | 隔离演示换货政策目前的换货期限是多少？ | 1 | 1 | usable | none |
| A05-25 | 现行隔离演示换货政策要求商品包装满足什么条件？ | 1 | 1 | usable | none |
| A05-26 | 现行隔离演示换货政策每笔订单能换货几次？ | 1 | 1 | usable | none |
| A05-27 | 请仅根据demo-v1换货政策告诉我寄回地址。 | None | None | low_confidence | none |
| A05-28 | 请仅根据demo-v3换货政策告诉我指定承运人。 | None | None | low_confidence | none |
| A05-29 | 过期的隔离演示优惠券政策活动口令是什么？ | None | None | low_confidence | none |
| A05-30 | 撤销的隔离演示延保政策赠品是什么？ | None | None | low_confidence | none |

Recall@K: correct frozen gold chunk in final top K / all answerable cases (including failures).
MRR: sum of 1/final gold rank, missing=0, / all answerable cases; ranks truncated at 5.
No-answer FPR: usable with nonempty hits/citations on no-answer cases / all no-answer cases.
Citation precision: emitted citations whose chunk contains the labelled evidence / all emitted citations, including no-answer cases.
Latency: wall time for tool execution plus final N06/N07 validation, excludes ingest/startup; first repeat includes cold reads; linear interpolated percentiles.
Repeat groups are scored separately; repeats are not independent questions or populations.
Candidate Recall is diagnostic, may include low-score chunks, and is never usable-evidence Recall.
No Agent answers generated; Task Success and answer factual accuracy remain unmeasured.
