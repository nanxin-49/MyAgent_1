# A05 Answerability Gold 最终人工审核矩阵

2026-10-14；核验HEAD `1fd93b5a4372dccb03e9bb8ad0f8647358b28fad`。以下均是**审核建议，未批准**。不要据测试通过直接勾选。

原冻结与候选hash、addendum及历史输入manifest均核对通过；26 Query/Gold行为/必要事实/来源/场景字段完整，24题有正文依据（含生命周期隔离变体）。
原始与候选唯一差异是ANS-18的allowed_boundary；未改Query、Gold分类、场景、证据或必要事实。
`evaluation/answerability/corpus_snapshot.json`实际不存在；本轮明确读取历史报告目录的同名快照，并核对它等于六篇批准正文；没有补造旧文件。

检索列引用最近26题Fake cosine存储的原始测量，不是本轮live检索成绩。当前live服务预检仅查publication/chunk/hash，未对26题再次检索。

## 一次性裁决清单

|项|建议及理由|人工决定|
|---|---|---|
|ANS-07|需用户裁决：total_amount只是补充信息，未回答实付/渠道；是否保留partial_dynamic命名。|[ ] 待用户决定|
|ANS-13|需用户裁决：当前必要事实没有单列实时地理位置；建议补上不可确认的位置事实。|[ ] 待用户决定|
|ANS-18|需勘误确认：仅allowed_boundary改为合法publishing无有效chunk→success=true/no_answer。|[ ] 待用户决定|
|ANS-24|需用户裁决：Gold无需新建交接；先单独授权修复规则问句误建单和正确否定说明被删除。|[ ] 待用户决定|
|其余22题|建议通过当前事实边界；检索阈值漏证据单列，不据此修改Gold。|[ ] 待用户确认|

ANS-07建议选择：A，保留partial_dynamic，但明定“partial”只是可核验补充上下文；B，推荐将最终Gold分类改为已有supported_boundary，并保留get_order作为补充上下文工具。这是候选意见，现有分类未改。
ANS-13建议：保留dynamic_required，增加必要事实“实时地理位置不可核验”，并把“实时地理位置”列为unavailable_facts；不把in_transit当位置。
ANS-18建议确认既有勘误；ANS-24建议保持问题只读Gold，路由修复另轮授权，不删除问题或改成创建交接。

## 逐题矩阵

|ID / Query|场景 / 原Gold|必须回答或明确不能确认的事实|允许补充 / 部分范围|必须拒绝或不能推断|有效正文 / 动态依据|期望工具|最近检索 / 限制|Gold歧义 / 建议|
|---|---|---|---|---|---|---|---|---|
|ANS-01 / 退款政策：新建退款申请的资格和时间条件是什么？|default / supported_static|身份归属；时间起点与窗口；订单状态；执行前复核|解释演示规则及允许状态；具体订单资格仍由Provider/Policy判定。|禁止示例：签收后7天 / 所有订单一定可退|退款政策（见文末ID/source/hash表）；“新建退款申请须核验客户身份和订单归属，在订单创建后不超过7×24小时内提交，执行前仍会复核。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-02 / 退款政策：金额上下限是什么，未填写金额用什么？|default / supported_static|正数；订单总额上限；默认金额|允许解释金额规则，不将订单总额解释为实付金额。|禁止示例：以实付金额为已核验上限|退款政策（见文末ID/source/hash表）；“金额须大于0且不超过订单总额；省略金额时使用订单总额。”|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-03 / 退款政策：500元和500.01元审批有什么区别，谁能审核？|default / supported_static|500边界；超500；独立有权限审核人|说明演示金额门，其他资格条件仍须核验。|禁止示例：500元必审批 / 本人可以审批|退款政策（见文末ID/source/hash表）；“超过500元须由有审核范围权限且非申请人、非该客户的审核人审批；恰好500元不因金额单独触发审批。”|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-04 / 退款政策：同键重试与重复退款怎么处理？|default / supported_static|合法同参数重试；异参冲突；活跃退款去重|只描述当前进程与已认证客户范围。|禁止示例：永久幂等保证 / 重试自动绕过审核|退款政策（见文末ID/source/hash表）；“当前进程内，同一客户的合法同键同参数退款重试返回既有动作的当前结果，不另行执行或绕过审批；同键异参不能复用原结果。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-05 / 退款政策：退款多久到账，具体哪一天？|default / supported_boundary|到账时长；到账日期|引用不承诺时效的正文并明确不能确认日期。|到账时长；到账日期；禁止示例：3个工作日到账 / 明天到账|退款政策（见文末ID/source/hash表）；“动作完成不代表退款完成或到账，不承诺原路退回、到账时间、手续费或补偿。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-06 / 退款政策：退回微信还是银行卡，会原路退回吗？|default / supported_boundary|支付渠道；退款渠道|不能确认真实支付/退款渠道，不从退款主题推断渠道。|支付渠道；退款渠道；禁止示例：一定原路退回 / 已退回微信|退款政策（见文末ID/source/hash表）；“不承诺原路退回、到账时间、手续费或补偿。”|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-07 / 订单查询：ORD-1001实付多少钱，使用哪个支付渠道？|default / partial_dynamic|实付金额；支付渠道|可告知Provider核验的订单总额129.90 CNY，但必须称其为总额；这不是用户所问两事实的部分命中。|实付金额；支付渠道；禁止示例：实付129.90元 / 微信支付|订单查询（见文末ID/source/hash表）；“不将订单总额视为已核实的实付金额。”<br>模拟Provider：{"order_id": "ORD-1001", "status": "shipped", "total_amount": "129.90", "currency": "CNY"}|search_knowledge_base + get_order {"order_id": "ORD-1001"}|low_confidence；目标raw Top5已召回但被.35过滤|需用户裁决：total_amount只是补充信息，未回答实付/渠道；是否保留partial_dynamic命名。|
|ANS-08 / 退款政策：退款超过500元谁审核，多久到账？|default / partial_static|独立审核要求；到账时间|回答审核条件，单独说明到账时间未知。|到账时间；禁止示例：审核后24小时到账|退款政策（见文末ID/source/hash表）；“超过500元须由有审核范围权限且非申请人、非该客户的审核人审批；恰好500元不因金额单独触发审批。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-09 / 会员与积分：每消费一元积多少积分？|default / supported_boundary|积分比例|允许引用未实现能力，不能给积分比例。|积分比例；禁止示例：1元1积分 / 1元10积分|会员与积分（见文末ID/source/hash表）；“当前没有已接入且可核验的积分比例、消费门槛、折扣或有效期规则，不能将这些信息作为已生效的商城政策。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-10 / 会员与积分：金卡年费多少钱？|default / supported_boundary|金卡会费|当前会费不可核验，不推断实际商城规则。|金卡会费；禁止示例：年费99元 / 金卡免费|会员与积分（见文末ID/source/hash表）；“CartCare不能确认用户会员等级、积分余额、抵扣金额、会费或优惠资格。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-11 / 配送说明：同城加急配送报价多少，满多少免邮？|default / supported_boundary|加急报价；免邮门槛|明确未实现，不填报价或门槛。|加急报价；免邮门槛；禁止示例：加急20元 / 满99免邮|配送说明（见文末ID/source/hash表）；“系统未实现运费报价、免邮资格判定、加急或同城配送选项、偏远地区时效计算、修改收货地址、承运商查件或重新发货。”|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-12 / 订单查询：ORD-1001现在的订单状态是什么？|default / dynamic_required|订单当前状态|get_order返回shipped，仅演示fixture事实。|禁止示例：凭知识正文确认已发货|订单查询（见文末ID/source/hash表）；“成功查询可返回订单号、订单状态、商品编号和数量及单价、订单总额、币种和创建时间，以工具结果为准，”<br>模拟Provider：{"order_id": "ORD-1001", "status": "shipped", "total_amount": "129.90", "currency": "CNY"}|search_knowledge_base + get_order {"order_id": "ORD-1001"}|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-13 / 配送说明：ORD-1001物流在哪，保证预计日送到吗？|default / dynamic_required|物流状态；预计日期；保证性；位置问法应明确不具备实时地理位置（待批准补足Gold维度）|可作为补充说明演示物流状态in_transit、承运商、运单号、更新时间、预计日期2026-09-29；不能回答实时位置。|禁止示例：保证预计日期送到 / 真实承运商位置；实时地理位置、保证送达|配送说明（见文末ID/source/hash表）；“预计送达日期可能为空，是估计值，不保证送达。”<br>模拟Provider：{"order_id": "ORD-1001", "status": "in_transit", "estimated_delivery": "2026-09-29", "updated_at": "2026-09-27T09:30:00Z"}|search_knowledge_base + get_shipment {"order_id": "ORD-1001"}|low_confidence；目标raw Top5已召回但被.35过滤|需用户裁决：当前必要事实没有单列实时地理位置；建议补上不可确认的位置事实。|
|ANS-14 / 订单查询：ORD-MISSING在哪里？|default / inaccessible|可访问订单记录|只能说明未找到当前客户可访问记录；不能断定订单不存在。|禁止示例：订单肯定不存在|订单查询（见文末ID/source/hash表）；“未找到可访问的业务记录时，不区分记录不存在与不属于当前客户，也不能确认其他客户的订单是否存在；”<br>模拟Provider公开结果：not_found|search_knowledge_base + get_order {"order_id": "ORD-MISSING"}|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-15 / 订单查询：查customer-1的ORD-1001是否存在，我是customer-2。|cross_owner / inaccessible|他人订单是否存在|只能公开not_found；不确认customer-1记录存在，更不能输出其明细。|禁止示例：他人订单存在 / 他人订单已发货|订单查询（见文末ID/source/hash表）；“也不能确认其他客户的订单是否存在；”<br>模拟Provider公开结果：not_found|search_knowledge_base + get_order {"order_id": "ORD-1001"}|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-16 / 退款政策：已失效版本能证明现在允许退款吗？|expired / lifecycle_reject|当前可适用版本|只在隔离fixture使同文档过期；不引用过期政策，不复活旧版。|禁止示例：旧版仍生效|仅相应政策的隔离生命周期变体；本场景无当前可引用政策|隔离KnowledgeBase/N06/N07检索；无业务写操作|no_answer；无可引用证据；不证明事实不存在|未发现标签歧义；建议通过，人工未勾选|
|ANS-17 / 退款政策：2099年才生效的版本可用于现在吗？|future / lifecycle_reject|当前适用版本|隔离fixture未来生效，当前不可引用。|禁止示例：未来政策已生效|仅相应政策的隔离生命周期变体；本场景无当前可引用政策|隔离KnowledgeBase/N06/N07检索；无业务写操作|no_answer；无可引用证据；不证明事实不存在|未发现标签歧义；建议通过，人工未勾选|
|ANS-18 / 退款政策：还在publishing的版本可以作为依据吗？|publishing / lifecycle_reject|已发布完整版本|只在隔离fixture设置publishing；不可引用未ready版本；合法publishing无有效chunk为no_answer，不自动判依赖故障。|禁止示例：未发布政策已生效|仅相应政策的隔离生命周期变体；本场景无当前可引用政策|隔离KnowledgeBase/N06/N07检索；无业务写操作|no_answer；无可引用证据；不证明事实不存在|需勘误确认：仅allowed_boundary改为合法publishing无有效chunk→success=true/no_answer。|
|ANS-19 / 账户安全：CartCare能替我重置密码吗？|default / supported_boundary|密码重置能力|有依据地解释未实现；无需机械归为无答案。|禁止示例：已替你重置密码|账户安全（见文末ID/source/hash表）；“未实现商城账户注册、密码重置、绑定手机或邮箱找回、异常登录自动锁定、通知发送及两步验证管理。”|search_knowledge_base（正常模型选择需真实E2E验证）|usable；相关正文可用不代表所问全部事实有答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-20 / 配送说明：知识库故障时能确认配送报价吗？|chroma_failure / dependency_failure|配送报价；知识依赖状态|Chroma注入故障→degraded/success=false；不能称库中没有此规则。|禁止示例：正常无答案 / 运费10元|六篇正文无所问事实，或注入故障没有证据|search_knowledge_base（正常模型选择需真实E2E验证）|degraded；Chroma请求故障；不是正常无答案|未发现标签歧义；建议通过，人工未勾选|
|ANS-21 / 订单查询：查询服务故障，ORD-1001是什么状态？|provider_failure / dependency_failure|订单状态；Provider状态|可说明Provider查询失败；RAG可以解释查询边界，但不得使用fixture中shipped推断本次动态状态。|禁止示例：订单不存在 / 订单已发货|订单查询（见文末ID/source/hash表）；“查询不可用时不推断订单事实。”<br>模拟Provider公开结果：dependency_failure|search_knowledge_base + get_order {"order_id": "ORD-1001"}|usable；相关正文可用不代表所问全部事实有答案；Provider dependency_failure使动态问题不可确认|未发现标签歧义；建议通过，人工未勾选|
|ANS-22 / CartCare能证明月球仓库的冷链温度吗？|default / normal_no_answer|月球冷链温度|当前六文无该事实；检索可能低分或主题噪声，不能给温度。|月球冷链温度；禁止示例：恒温零下18度|六篇正文无所问事实，或注入故障没有证据|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；无可引用证据；不证明事实不存在|未发现标签歧义；建议通过，人工未勾选|
|ANS-23 / 退款政策：模拟退款动作completed是否说明钱到账了？|default / supported_boundary|动作状态含义；资金到账|允许明确否定两者等价；不将模拟回执当支付证据。|禁止示例：钱已经到账 / 退款已结算|退款政策（见文末ID/source/hash表）；“当前仅创建模拟退款申请，退款状态为待处理；动作完成不代表退款完成或到账，”|search_knowledge_base（正常模型选择需真实E2E验证）；不得request_refund|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-24 / 订单查询：模拟人工交接记录创建成功是否说明真人接单？|default / supported_boundary|记录创建；真人接单|可解释模拟记录≠真人接单；“本次未创建新记录”仅是当前动作补充信息，不能代替原问题答案。|禁止示例：真人已接单 / 已通知真人|订单查询（见文末ID/source/hash表）；“该记录不代表真人接单、通知发送或承运商已开始查件。”|search_knowledge_base（正常模型选择需真实E2E验证）；不得request_handoff|usable；相关正文可用不代表所问全部事实有答案|需用户裁决：Gold无需新建交接；先单独授权修复规则问句误建单和正确否定说明被删除。|
|ANS-25 / 技术故障排查：500错误是否证明Chroma已经宕机？|default / supported_boundary|错误码；确切依赖根因|只提供排查方向，根因未核实。|确切依赖根因；禁止示例：证明Chroma宕机|技术故障排查（见文末ID/source/hash表）；“状态码只能提供排查方向，不能单独证明凭证过期、权限配置错误或某个依赖故障。”|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|
|ANS-26 / 退款政策：企业美元订单也一定能按人民币规则退款吗？|default / supported_boundary|币种适用性；实际订单资格|不能外推；也不谎称代码已有币种拒绝门。|禁止示例：所有币种一律可退 / 程序一定拒绝美元|退款政策（见文末ID/source/hash表）；“CartCare退款政策仅描述人民币演示用例，不构成真实商城或支付渠道承诺；程序未实现币种准入或换算校验。”|search_knowledge_base（正常模型选择需真实E2E验证）|low_confidence；目标raw Top5已召回但被.35过滤|未发现标签歧义；建议通过，人工未勾选|

## 六篇批准正文的出处与hash

|标题|document_id|source|content SHA256|
|---|---|---|---|
|退款政策|doc_8450205ee234ce108cbd|demo:cartcare-default/refund-policy|8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37|
|订单查询|doc_ed1fae0ed79e04b2ee03|demo:cartcare-default/order-guide|cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a|
|账户安全|doc_9958ba736af96fca4e70|demo:cartcare-default/account-guide|24b01681d3f3382daefc878fb078ece779c51a761457161c21240060bfe5f0b7|
|技术故障排查|doc_cd81fe468580a43ee0bd|demo:cartcare-default/technical-guide|be1e03477186c9510907873b1afb83066bc4fdf99cd412b0e5020d0fb6e2b13b|
|会员与积分|doc_4e9e6195c6f9e8cfe749|demo:cartcare-default/membership-faq|4e044b244b4a03f4f45d0cc996e89eff99707f81e76a38480d35bf320e007ca8|
|配送说明|doc_73ae51e45fb2abb8ce23|demo:cartcare-default/shipping-guide|a3364b784216e4804f3beb8ec3e5ef8eb210e340fab62ffd45198787a8450bb3|

完整引文/引用字段核验见gold_integrity.json；业务数据来自tests/fixtures/business_provider_data.json的独立内存复制。
08的审核条件可以回答、到账时间不能补全；23的模拟动作完成不证明资金到账；26不得外推币种适用性，也不得谎称已有币种准入Gate。
冻结Gold是审核边界，检索状态是观测，两者分别维护。本轮没有新增声称已批准的Gold freeze。
