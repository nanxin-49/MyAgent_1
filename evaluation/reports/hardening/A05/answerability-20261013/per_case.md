# 逐题对照（规则送达，不是回答正确率）

|ID|原始问题|Gold行为|前/后检索状态|原始/可用目标召回|归因|前→后规则送达|
|---|---|---|---|---|---|---|
|ANS-01|退款政策：新建退款申请的资格和时间条件是什么？|supported_static|usable → usable|True/True|supported_static|False → True|
|ANS-02|退款政策：金额上下限是什么，未填写金额用什么？|supported_static|low_confidence → low_confidence|True/False|gold_threshold_filtered|False → True|
|ANS-03|退款政策：500元和500.01元审批有什么区别，谁能审核？|supported_static|low_confidence → low_confidence|True/False|gold_threshold_filtered|False → True|
|ANS-04|退款政策：同键重试与重复退款怎么处理？|supported_static|usable → usable|True/True|supported_static|False → True|
|ANS-05|退款政策：退款多久到账，具体哪一天？|supported_boundary|usable → usable|True/True|specific_facts_not_in_current_bodies / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-06|退款政策：退回微信还是银行卡，会原路退回吗？|supported_boundary|low_confidence → low_confidence|True/False|gold_threshold_filtered / specific_facts_not_in_current_bodies / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-07|订单查询：ORD-1001实付多少钱，使用哪个支付渠道？|partial_dynamic|low_confidence → low_confidence|True/False|gold_threshold_filtered / specific_facts_not_in_current_bodies / dynamic_provider_required|False → True|
|ANS-08|退款政策：退款超过500元谁审核，多久到账？|partial_static|usable → usable|True/True|specific_facts_not_in_current_bodies|False → True|
|ANS-09|会员与积分：每消费一元积多少积分？|supported_boundary|usable → usable|True/True|specific_facts_not_in_current_bodies / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-10|会员与积分：金卡年费多少钱？|supported_boundary|usable → usable|True/True|specific_facts_not_in_current_bodies / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-11|配送说明：同城加急配送报价多少，满多少免邮？|supported_boundary|low_confidence → low_confidence|True/False|gold_threshold_filtered / specific_facts_not_in_current_bodies / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-12|订单查询：ORD-1001现在的订单状态是什么？|dynamic_required|usable → usable|True/True|dynamic_provider_required|False → True|
|ANS-13|配送说明：ORD-1001物流在哪，保证预计日送到吗？|dynamic_required|low_confidence → low_confidence|True/False|gold_threshold_filtered / dynamic_provider_required|False → True|
|ANS-14|订单查询：ORD-MISSING在哪里？|inaccessible|low_confidence → low_confidence|True/False|gold_threshold_filtered / dynamic_provider_required|False → True|
|ANS-15|订单查询：查customer-1的ORD-1001是否存在，我是customer-2。|inaccessible|low_confidence → low_confidence|True/False|gold_threshold_filtered / dynamic_provider_required|False → True|
|ANS-16|退款政策：已失效版本能证明现在允许退款吗？|lifecycle_reject|no_answer → no_answer|False/False|lifecycle_not_current_or_not_ready|False → True|
|ANS-17|退款政策：2099年才生效的版本可用于现在吗？|lifecycle_reject|no_answer → no_answer|False/False|lifecycle_not_current_or_not_ready|False → True|
|ANS-18|退款政策：还在publishing的版本可以作为依据吗？|lifecycle_reject|no_answer → no_answer|False/False|lifecycle_not_current_or_not_ready|False → True|
|ANS-19|账户安全：CartCare能替我重置密码吗？|supported_boundary|usable → usable|True/True|explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-20|配送说明：知识库故障时能确认配送报价吗？|dependency_failure|degraded → degraded|False/False|chroma_dependency_failure|False → True|
|ANS-21|订单查询：查询服务故障，ORD-1001是什么状态？|dependency_failure|usable → usable|True/True|dynamic_provider_required / provider_dependency_failure|False → True|
|ANS-22|CartCare能证明月球仓库的冷链温度吗？|normal_no_answer|low_confidence → low_confidence|False/False|specific_facts_not_in_current_bodies|False → True|
|ANS-23|退款政策：模拟退款动作completed是否说明钱到账了？|supported_boundary|low_confidence → low_confidence|True/False|gold_threshold_filtered / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-24|订单查询：模拟人工交接记录创建成功是否说明真人接单？|supported_boundary|usable → usable|True/True|explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-25|技术故障排查：500错误是否证明Chroma已经宕机？|supported_boundary|low_confidence → low_confidence|True/False|gold_threshold_filtered / specific_facts_not_in_current_bodies / explicit_capability_or_evidence_boundary_is_answerable|False → True|
|ANS-26|退款政策：企业美元订单也一定能按人民币规则退款吗？|supported_boundary|low_confidence → low_confidence|True/False|gold_threshold_filtered / explicit_capability_or_evidence_boundary_is_answerable|False → True|
