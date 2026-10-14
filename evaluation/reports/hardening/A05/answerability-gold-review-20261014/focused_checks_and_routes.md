# 重点事实核验与ANS-24路由证据

ANS-07：Order模型没有paid_amount/payment_channel等字段。当前get_order成功只给total_amount=129.90等订单事实。该金额只是补充上下文，不能算回答了所问“实付/渠道”中的任何一个。分类歧义待用户裁决，不改Gold。
ANS-13：Shipment只有status、carrier、tracking_number、updated_at及可空estimated_delivery等字段，没有实时地理位置或坐标。in_transit是状态，预计2026-09-29也是fixture估计值，不是当前实际位置或保证送达。此日期在本轮已过去，应明确为演示记录日期，不能称未来承诺。
ANS-18：合法publishing文档无ready有效chunk时，_eligible排除，search返回[]，N07返回success=true/no_answer。只有allowed_boundary修正，完整语义diff与hash见gold_integrity.json。
ANS-20：Fake collection.query抛Chroma依赖异常，RAG success=false/degraded，results/citations为空，无Provider调用；期望说查询不可用，不说知识不存在。
ANS-21：RAG success=true/usable且有静态订单查询说明；get_order注入BackendDependencyError，Provider公开success=false/dependency_failure且data=null。整个动态订单事实仍不可回答，只能报告查询失败。RAG usable不能覆盖动态依赖失败。

## 路由专项（真实Python路径 + 隔离Fake/TestClient）

独立进程内每条探针重建BusinessBackend、ActionService、Memory、KnowledgeBase和HandoffService；仅注入customer角色。无lifespan、服务监听、真实业务或真人通知。

|探针|Query|实际分支|SDK调用|新记录|业务/动作变化|
|---|---|---|---|---|---|
|ANS-24-exact|订单查询：模拟人工交接记录创建成功是否说明真人接单？|model_tool_loop|2|0|business=False；action=0|
|same-fact-question-variant|订单查询：模拟人工交接记录创建成功是否说明已转人工客服？|deterministic_handoff_gate|0|1|business=False；action=0|
|explicit-request-control|请帮我转人工客服。|deterministic_handoff_gate|0|1|business=False；action=0|
|negated-request-control|我不需要人工客服，请说明模拟交接记录是什么意思。|model_tool_loop|2|0|business=False；action=0|

所有TestClient请求还会产生2条隔离Memory写入，这是/chat正常模拟副作用；handoff状态差异独立记录。前后完整状态、返回body及Trace见handoff_routes.json。

## 独立缺陷与最小建议（本轮未修复）

**A05-ANS24-ROUTE（建议P1）**：同事实规则问句“……是否说明已转人工客服？”包含转人工客服，explicit_handoff正则匹配而没有排除询问既有记录含义；Single确定性门与HandoffService.allowed_reason重复认可同一判定。跳过SDK，records 0→1/attempts 0→1，escalated=true。没有真实接单，但增加模拟写操作及误leading回执，不能为继续E2E跳过。
最小修复方向：在既有确定性显式请求判定内区分当前主动创建请求与记录/规则/已完成状态询问；服务Policy复用同一判断，保留customer/owner/幂等门及明确请求控制。不按所有问号一刀切，也不引入新Agent。需新增quoted/requested/not-requested、否定、显式请求、Model工具拒绝等安全回归。
**A05-ANS24-REPLY（建议P2，E2E解释题阻塞）**：精确原句不建单、SDK调用2次且RAG usable，但Fake SDK返回正确的“不代表真人接单”句子被Single含人工/真人文字保护整句删掉，API仅返回“本次未创建人工交接记录”及引用；没回答规则含义。最小方向是区分证据支持的否定/能力解释与无回执的虚假成功承诺，继续保留A02拒绝、失败及真实回执保护，避免任意语言绕过。
最小预期安全测试test_routing_regression.py：原句不建单通过；规则问句不得新增记录、正确否定说明应保留两条失败。routing_expected_safe_red.txt为2 failed / 1 passed / 1既有AnyIO警告；仅复现，未修改生产路由。
原有Answerability/Handoff/Skills相关58测试仍通过；它们未覆盖这些问法/正确否定说明，不能据既有绿测否认新红测。
下一步仅建议用户单独授权这两处修复；本轮不执行，不启动E2E。
