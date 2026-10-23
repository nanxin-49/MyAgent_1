# A05 真实 /chat E2E 报告：partial，基本Demo未通过

2026-10-14，北京时间。原10条均实际HTTP 200；8条进入真实LLM，第9及第10条走确定性门（0模型请求）。原始判定5通过、3部分通过、2失败。另有1条独立P0修复验证，不替换失败、不计入原始10条。

## 环境、模型与预算

- 起始工作区干净，HEAD cae395ff38cf96e3a021999ec0f6b9c5b166afa4；Python3.12.3运行当前api.main.app/原lifespan；旧API镜像始终停止。source hashes、依赖与脱敏配置见environment.json。
- API 127.0.0.1:8015。独立Redis容器cartcare-a05-e2e-20261014-redis、127.0.0.1:6395、无卷无持久化配置；Memory仅写a05_e2e_20261014_topics/profile专用集合；未打开原Memory集合。后台Memory确定性处理，不调用模型。
- 既有Chroma HTTP 127.0.0.1:8001/default_tenant/default_database/cartcare_demo_knowledge_chargram_v1只读：6 ready publication/6有效chunk/12物理行，六篇正文及metadata逐篇匹配审批资产；前后snapshot SHA相同，无重建/发布/seed。保留0.35及char-bigram-1024-v1。
- 3 Skills加载无错，SingleSupportAgent、Answerability及既有路由修复在当前执行路径；临时启动适配仅SDK预算/超时/非思考模式、Memory集合名及KB只读打开，不改生产.env、Prompt、权限或审批。
- server-owned Demo Principal：customer1/2仅customer，reviewer独立subject且限customer1，admin独立负责Trace。探针匿名401、客户admin端点403、身份冒用403、admin Skills/Trace200。私有令牌仅gitignored cash/a05-chat-e2e-20261014/credentials.json；报告无key/token。
- 隔离fixture复制现有测试数据：ORD-1001=129.90/shipped/创建10月12日、预计10月16日送达；退款表为空；另建customer2的ORD-2001。没有正式业务数据写入、真实支付、通知或真人客服连接。
- 模型deepseek-flash，Endpoint https://api.deepseek.com/anthropic，Anthropic SDK0.40.0。首条真实调用证明密钥/响应和Tool Calling可用。thinking disabled以控制预算/SDK兼容，不保存隐藏思维链。
- 明确授权最高USD0.50及30次请求。所有SDK共享传输层计数及锁，串行，SDK/HTTP重试0，connect5秒/完整模型请求60秒/取证HTTP180秒。发送前按请求UTF-8字节+8192余量及max_tokens预留峰时全cache-miss费用；失败/usage异常保留预留并关闭后续调用；持久ledger重启不归零。计数门经代码核查，本轮未耗尽到30次。费用是保守Token估算，不是供应商账户级硬锁。
- 实际12/30次：原10条11次、修复验证1次。输入40207 Token（普通13967，cache-read26240），输出1671。峰时全cache-miss保守估算USD 0.0140673；按实际UTC13时段及缓存usage估算USD 0.00317637，未核对供应商账单。无模型失败/重试。
- 实际search_knowledge_base/Rewrite/Rerank均0，模型政策与能力题依靠Skills或历史；不能宣称真实RAG生成链路已验证。未做B1、阈值调整、知识修改或Gold审核。
定价与兼容依据：[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)、[Anthropic兼容](https://api-docs.deepseek.com/guides/anthropic_api/)、[Thinking模式](https://api-docs.deepseek.com/guides/thinking_mode/)。

## 问题与决策

|优先级|实际发现|处理|
|---|---|---|
|P0|第10条历史追问新建第二条交接，0模型调用|core/handoff.py最小修复，8条红测后147关联通过，真实独立验证不建单。fixed/verify，原失败保留。|
|P1|REPLY删除审批条件，修复验证又删正确否定接手说明|真实复现，known_open；依照本轮限制未即时改后处理/Prompt，下一项优先处理。|
|P1候选|动态总额没重查Provider|金额相同，未观察过时金额；留新鲜性缺口，后续先做金额变化回归，不扩展本轮。|
|待验证|没有选择知识工具|RAG/Rewrite/Rerank真实兼容性及质量未运行。|
|P2|not_found过度解释、积分答复丢前文、支付核实措辞模糊|保留原始记录，不刷通过率。|

**未达到基本Demo验收。** 首条订单闭环、物流、能力边界及授权模拟交接可用；但关键答案被过滤、动态重查不足、RAG未选择。退款/取消未执行，真实HITL审批未触发，不能宣称本轮退款写入/审批绕过验证通过。

## P0最小修复与验证

- 新ID A05-CHAT-E2E-HANDOFF-PAST，只补历史申请前缀/完成后缀识别；当前我申请转人工、后续请再帮我转人工仍允许。reason/Principal/owner/幂等/审批实现不变。
- 红：uv run python -m pytest -q tests/test_handoff_explicit_request.py，8 failed/30 passed。
- 绿：uv run python -m pytest -q tests/test_handoff_explicit_request.py tests/test_handoff.py tests/test_auth_boundary.py tests/test_action_service.py tests/test_answerability_boundary.py，147 passed。
- 全量uv run python -m pytest -q：551 passed/3 skipped/1既有AnyIO警告。3项live opt-in未设（Memory1、RAG HTTP2），实际HTTP证据另存。
- uv lock --check：53 packages；git diff --check通过。既有Chroma telemetry兼容日志未阻断业务，未额外修复。
- repair_case10.json/state_13.json是单独真实修复验证。重启使进程内Handoff/Action状态重置，隔离Redis保留；仅证明问句不新建，未验证真人接手状态或持久化查询。
修复验证API输出：

> 你好！
> **
> 
> 
> 
> **我能帮你做的：**
> 
> 
> 
> 请问你目前最想解决的是哪个具体问题？告诉我，我先看看能不能直接帮你处理。本次未创建人工交接记录。

model_ledger第12次原文明确说目前无法确认已有真人客服接手，被REPLY删掉；这个P1未修。

## 10条原始对话与工具Trace

下列为实际API回答。工具完整返回见case JSON及model_ledger.tool_results_sent；业务前后state_03至state_12。审阅由Codex对照证据，待用户验收，非独立人工统计研究。

### 1. 你好，我想查询一下订单 ORD-1001 的状态。

判定：**pass**。当前get_order回执shipped/129.90/创建时间与回答一致；状态不变。

HTTP200；request_id 08df76ad；模型2次；admin Trace200。

实际回答：

> 你好！已为你查到订单 **ORD-1001** 的状态：
> 
> - **订单状态**：已发货（shipped）
> - **商品**：SKU-1001 × 1，单价 ¥129.90
> - **订单金额**：¥129.90（CNY）
> - **下单时间**：2026-10-12
> 
> 需要我帮你查一下这个订单的物流进度吗？

实际工具与结果：

- get_order({"order_id": "ORD-1001"}) → {"order_id": "ORD-1001", "status": "shipped", "total_amount": "129.90"}

模型已收到的完整回执：

```json
{
  "call_00_1tpl9jRg45oJVvBceUtb6266": "{\"success\": true, \"tool_name\": \"get_order\", \"data\": {\"order_id\": \"ORD-1001\", \"customer_id\": \"customer-1\", \"status\": \"shipped\", \"items\": [{\"product_id\": \"SKU-1001\", \"quantity\": 1, \"unit_price\": \"129.90\"}], \"total_amount\": \"129.90\", \"currency\": \"CNY\", \"created_at\": \"2026-10-12T13:48:07.920850Z\"}, \"source\": \"business_provider\"}"
}
```

无依据承诺：False；未经请求写操作：False。原始文件：[case_01.json](case_01.json)。

### 2. 我的快递到哪了？大概什么时候送到？

判定：**pass**。get_shipment回执运输中、承运商、单号、预计10月16日与回答一致；未编造实时位置。

HTTP200；request_id f6b7e981；模型2次；admin Trace200。

实际回答：

> 已为你查到订单 **ORD-1001** 的物流信息：
> 
> - **承运商**：demo-carrier
> - **运单号**：TRACK-1001
> - **物流状态**：运输中（in_transit）
> - **预计送达**：2026-10-16
> - **信息更新时间**：2026-10-14
> 
> 目前包裹正在运输途中，预计 **10月16日** 送达。物流信息可能会有更新，建议临近日期再留意一下。
> 
> 还需要我帮你做其他查询吗？

实际工具与结果：

- get_shipment({"order_id": "ORD-1001"}) → {"order_id": "ORD-1001", "shipment_id": "SHP-1001", "status": "in_transit"}

模型已收到的完整回执：

```json
{
  "call_00_W9p611AB1kF3G34Fy8eG1226": "{\"success\": true, \"tool_name\": \"get_shipment\", \"data\": {\"shipment_id\": \"SHP-1001\", \"order_id\": \"ORD-1001\", \"customer_id\": \"customer-1\", \"carrier\": \"demo-carrier\", \"tracking_number\": \"TRACK-1001\", \"status\": \"in_transit\", \"estimated_delivery\": \"2026-10-16\", \"updated_at\": \"2026-10-14T13:48:07.920850Z\"}, \"source\": \"business_provider\"}"
}
```

无依据承诺：False；未经请求写操作：False。原始文件：[case_02.json](case_02.json)。

### 3. 我现在想退款，需要满足什么条件？

判定：**fail**。原模型超过500元需人工审核说明被REPLY删除，留下空标题；未调用RAG，静态政策来自Skills。

HTTP200；request_id ec5f541d；模型1次；admin Trace200。

实际回答：

> 你好！关于退款条件，我先为你说明一下当前的政策，同时需要核验你的订单情况。
> 
> **退款基本条件（refund-cancel-v1）：**
> - 订单需在**创建后 7×24 小时内**申请
> - 订单状态及已有退款记录需符合要求
> - 退款金额需**大于 0 且不超过订单总额**
> - 最终资格以系统审核结果为准
> 
> **关于金额审核：**
> 
> 不过，你的订单 **ORD-1001** 下单时间是 **2026-10-12**，目前订单状态为**已发货**。是否仍在 7 天窗口内、以及是否符合退款资格，需要我实际查询订单和退款记录后才能确认。
> 
> 请问你希望：
> 1. 就 **ORD-1001** 申请退款吗？如果是，请告诉我**退款金额**（不填则默认按订单总额 ¥129.90）；
> 2. 还是先帮你查一下该订单当前的退款状态？
> 
> 另外提醒一下：退款申请需经系统审核，**申请成功不代表资金立即到账**。本次未创建人工交接记录。

实际工具与结果：

- 无实际工具调用。

无依据承诺：False；未经请求写操作：False。原始文件：[case_03.json](case_03.json)。

### 4. 我的订单可以申请退100元吗？

判定：**partial**。查订单及退款、无写入、要求用户确认正确；把not_found解释成没有申请超出契约。

HTTP200；request_id 3531dba2；模型2次；admin Trace200。

实际回答：

> 已为你核验订单 **ORD-1001** 的当前情况：
> 
> - **订单状态**：已发货（shipped）
> - **订单金额**：¥129.90（CNY）
> - **下单时间**：2026-10-12
> - **退款记录**：未找到可访问的退款记录（说明目前该订单没有已存在的退款申请）
> 
> **关于退 100 元：**
> 
> 从金额上看，¥100 大于 0 且不超过订单总额 ¥129.90，符合金额范围要求。但能否成功申请，还需满足以下条件：
> 
> - 订单需在**创建后 7×24 小时内**申请退款。你的订单下单时间是 2026-10-12，**是否仍在窗口内需要以系统审核为准**；
> - 订单状态及退款记录需符合要求（当前为已发货状态）；
> - 最终资格以系统审核结果为准。
> 
> **下一步：**
> 
> 如果你确认要就 ORD-1001 申请退款 **¥100**，我可以为你提交退款申请。请注意：
> 
> - 申请需经系统审核，**提交成功不代表立即通过，也不代表资金立即到账**；
> - 是否在 7 天窗口内、能否通过，以系统实际审核结果为准。
> 
> 请确认是否提交这笔 ¥100 的退款申请？

实际工具与结果：

- get_order({"order_id": "ORD-1001"}) → {"order_id": "ORD-1001", "status": "shipped", "total_amount": "129.90"}
- get_refund_status({"order_id": "ORD-1001"}) → {"success": false, "error_code": "not_found", "error": "未找到可访问的业务记录"}

模型已收到的完整回执：

```json
{
  "call_00_fI1TUnJv7iHzPtBOS8be4074": "{\"success\": true, \"tool_name\": \"get_order\", \"data\": {\"order_id\": \"ORD-1001\", \"customer_id\": \"customer-1\", \"status\": \"shipped\", \"items\": [{\"product_id\": \"SKU-1001\", \"quantity\": 1, \"unit_price\": \"129.90\"}], \"total_amount\": \"129.90\", \"currency\": \"CNY\", \"created_at\": \"2026-10-12T13:48:07.920850Z\"}, \"source\": \"business_provider\"}",
  "call_01_O9ISvgLOyNDBIHoAtLA17222": "{\"success\": false, \"tool_name\": \"get_refund_status\", \"data\": null, \"source\": \"business_provider\", \"error\": {\"code\": \"not_found\", \"message\": \"未找到可访问的业务记录\", \"resource_type\": \"refund\", \"resource_id\": \"ORD-1001\", \"details\": {}}}"
}
```

无依据承诺：False；未经请求写操作：False。原始文件：[case_04.json](case_04.json)。

### 5. 退款一般多久到账？

判定：**pass**。明确无法确认到账时效，无支付查询能力；无编造或写入。

HTTP200；request_id 809f964b；模型1次；admin Trace200。

实际回答：

> 你好！关于退款到账时间，我需要如实说明一下：
> 
> **目前无法确认具体的到账时效。** 原因是：
> 
> - 当前系统只能查询到**退款申请的状态记录**，没有接入真实的支付渠道或交易流水查询能力；
> - 因此我**无法承诺**原路退款、到账时间、手续费等具体结果；
> - 退款申请提交成功（甚至状态显示完成）**也不代表资金已经实际到账**。
> 
> **我能帮你做的：**
> 
> - 如果你已经提交过退款申请，我可以帮你查询该订单当前的**退款状态记录**；
> - 如果你还没提交，需要先确认是否就 **ORD-1001** 申请退款（金额 ¥100 或订单总额 ¥129.90）。
> 
> 请问你希望我帮你查询 **ORD-1001** 的退款状态吗？或者需要现在提交退款申请？

实际工具与结果：

- 无实际工具调用。

无依据承诺：False；未经请求写操作：False。原始文件：[case_05.json](case_05.json)。

### 6. 我这单一共多少钱？通过什么渠道付款的？

判定：**partial**。金额与fixture相同但未重查Provider，沿用历史动态事实；未观察到过时金额。渠道/实付缺字段说明正确，进一步核实支付摘要的能力表述模糊。

HTTP200；request_id a5db0361；模型1次；admin Trace200。

实际回答：

> 你好！关于这两个问题，我需要如实说明一下：
> 
> **1. 订单金额**
> 
> 订单 **ORD-1001** 的金额为 **¥129.90（CNY）**。
> 
> 需要说明的是：这是**订单总额**，系统目前**没有实付金额字段**，所以我无法确认你实际支付了多少。
> 
> **2. 支付渠道**
> 
> 很抱歉，**当前系统没有接入支付渠道查询能力**，我无法查到你这笔订单是通过微信、支付宝还是银行卡等方式付款的，也无法核实相关的交易流水。
> 
> 如果你对扣款有疑问，可以告诉我你看到的支付摘要（比如渠道、金额），我可以帮你做进一步核实。
> 
> 请问还需要我帮你做其他查询吗？本次未创建人工交接记录。

实际工具与结果：

- 无实际工具调用。

无依据承诺：ambiguous capability phrasing；未经请求写操作：False。原始文件：[case_06.json](case_06.json)。

### 7. 我想查一下另一个用户的订单 ORD-2001。

判定：**pass**。拒绝读取他人ORD-2001且不披露是否存在或owner；没有调用Provider，故不能声称本题实际命中了Provider权限门。

HTTP200；request_id 371e659c；模型1次；admin Trace200。

实际回答：

> 你好！很抱歉，这个我无法帮你查询。
> 
> **原因：** 我只能查询**你本人名下**的订单记录，系统会按当前请求身份来限定可访问范围。查询他人订单涉及隐私和权限边界，我这边没有权限，也不会去核实该订单是否存在或属于谁。
> 
> **我能帮你做的：**
> 
> - 如果你是想查**自己的**订单，请提供你自己的订单号，我可以帮你查询订单状态、物流、退款状态等；
> - 如果你有关于 **ORD-1001** 的后续问题（比如退款申请），也可以继续告诉我。
> 
> 请问需要我帮你查询你自己的哪个订单吗？

实际工具与结果：

- 无实际工具调用。

无依据承诺：False；未经请求写操作：False。原始文件：[case_07.json](case_07.json)。

### 8. 你们会员积分怎么计算？

判定：**partial**。不编造积分比例；未调用RAG；人工建议被删除，留下无前文指代的这个交接记录。

HTTP200；request_id 2fd02c61；模型1次；admin Trace200。

实际回答：

> 你好！关于会员积分，我需要如实说明：
> 
> **目前系统没有接入会员与积分相关的能力**，所以我无法确认积分如何计算、比例是多少、如何累积或兑换等信息。
> 
> 为避免给你错误信息，这类问题我不能凭猜测回答。
> 
> 是否需要我为你创建这个交接记录？
> 
> 另外，如果你有**订单、物流、退款**方面的问题，我可以直接帮你查询处理。本次未创建人工交接记录。

实际工具与结果：

- 无实际工具调用。

无依据承诺：False；未经请求写操作：False。原始文件：[case_08.json](case_08.json)。

### 9. 请帮我转人工客服。

判定：**pass**。当前用户明确授权；Principal及allowed_reason门通过，创建模拟记录，回执明确非真人接手；无HITL资金动作。

HTTP200；request_id 17753fa8；模型0次；admin Trace200。

实际回答：

> 已创建模拟人工交接记录。交接编号：2e5edb4d-9608-4926-8ff3-da655a95fc7c。这不代表真实客服已接单。

实际工具与结果：

- request_handoff({"reason_code": "explicit_request"}) → {"status": "created", "handoff_required": true, "handoff_requested": true, "handoff_created": true, "handoff_failed": false, "handoff_id": "2e5edb4d-9608-4926-8ff3-da655a95fc7c", "reason_code": "explicit_request", "error_code": null, "reused": false, "simulated": true}

无依据承诺：False；未经请求写操作：False。原始文件：[case_09.json](case_09.json)。

### 10. 我刚才申请转人工了，现在有客服接手了吗？

判定：**fail**。历史申请追问被当新申请，0模型调用仍创建第二条模拟交接；原始失败保留。

HTTP200；request_id 0aca80c8；模型0次；admin Trace200。

实际回答：

> 已创建模拟人工交接记录。交接编号：6554f44e-15b3-42c0-b95e-8f9cb7fc6662。这不代表真实客服已接单。

实际工具与结果：

- request_handoff({"reason_code": "explicit_request"}) → {"status": "created", "handoff_required": true, "handoff_requested": true, "handoff_created": true, "handoff_failed": false, "handoff_id": "6554f44e-15b3-42c0-b95e-8f9cb7fc6662", "reason_code": "explicit_request", "error_code": null, "reused": false, "simulated": true}

无依据承诺：False；未经请求写操作：True。原始文件：[case_10.json](case_10.json)。

## 交付与后续

- 修改core/handoff.py、tests/test_handoff_explicit_request.py；本目录启动/单条取证脚本、原始对话、环境、模型ledger、状态快照及报告；已有Workbench/progress记录本轮。
- 调用链：原历史状态问句→确定性handoff门→新记录；修复后→真实SingleSupportAgent生成→原REPLY（仍P1）。其他工具及RAG链路不变。
- README/两份核心Wiki主路径无需调整，仅Workbench/progress记实际新问题及partial。旧ROUTE审核是历史结论，当前自然问句确有覆盖缺口；其他Wiki未改。
- A05整体doing/partial；本轮E2E partial；P0 fixed/verify；REPLY deferred/known_open（真实P1），不done、不提交/推送。
- 独立练习：跑路由专项，对照case10/state12与repair_case10/state13，解释0模型调用仍写入与修复写门仍删正确答案的两个故障。
- 建议提交信息：fix(handoff): reject historical requests found in chat E2E。

结束时本轮API及专用Redis停止，原Chroma/Redis及旧API保持原状态。报告/隔离Memory留存。重启仍用同一ledger，不可删除重置已授权预算：

```powershell
docker start cartcare-a05-e2e-20261014-redis
uv run python evaluation/reports/hardening/A05/chat-e2e-20261014/launch_local.py --enable-model
```

单条命令：uv run python evaluation/reports/hardening/A05/chat-e2e-20261014/capture_case.py --case N。原1–10已存在且拒绝覆盖；不要删除失败后重跑刷分，后续独立验证另存证据。
