# A05 Answerability Gold 审核清单

作者：Codex；人工审核待完成。不是既有 Gold v2 的续版，不用历史题目或分数调参。

人工审核使用dataset_v1.review_candidate.json及review_addendum.json；原始dataset_v1/freeze保留为测量前冻结。
先读六篇批准正文（内容快照 corpus_snapshot.json 与批准asset哈希一致），再逐项核对下列必要事实、正文引文与允许/禁止边界。

**ANS-18 勘误**：冻结dataset_v1的allowed_boundary末句误写publishing属于依赖不可用。
现有KnowledgeBase._eligible排除未ready发布，合法publishing且无有效chunk→[]，ToolManager→success=true/no_answer。
正确Gold：不可引用未发布版本；未ready本身不证明依赖故障。损坏manifest/Chroma请求异常才可能degraded。
原数据/hash、原红测和首次修复尝试均保留；审核ANS-18须使用本勘误，不迁就错误预期改生产状态。

每题人工确认：事实粒度完整；quote来自批准正文；否定能力也可有依据；动态事实必须Provider；
混合问题逐项区分已知/未知；不把阈值漏召回当事实不存在；不把故障当无答案；不外推真实商城/资金/真人能力。

## ANS-01 — 退款政策：新建退款申请的资格和时间条件是什么？

- [ ] 人工确认或明确修订理由
- 必要事实：身份归属；时间起点与窗口；订单状态；执行前复核
- Gold：supported_static；未知事实：按限定范围核验
- 允许边界：解释演示规则及允许状态；具体订单资格仍由Provider/Policy判定。
- 禁止承诺：签收后7天；所有订单一定可退
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：新建退款申请须核验客户身份和订单归属，在订单创建后不超过7×24小时内提交，执行前仍会复核。

## ANS-02 — 退款政策：金额上下限是什么，未填写金额用什么？

- [ ] 人工确认或明确修订理由
- 必要事实：正数；订单总额上限；默认金额
- Gold：supported_static；未知事实：按限定范围核验
- 允许边界：允许解释金额规则，不将订单总额解释为实付金额。
- 禁止承诺：以实付金额为已核验上限
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：金额须大于0且不超过订单总额；省略金额时使用订单总额。

## ANS-03 — 退款政策：500元和500.01元审批有什么区别，谁能审核？

- [ ] 人工确认或明确修订理由
- 必要事实：500边界；超500；独立有权限审核人
- Gold：supported_static；未知事实：按限定范围核验
- 允许边界：说明演示金额门，其他资格条件仍须核验。
- 禁止承诺：500元必审批；本人可以审批
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：超过500元须由有审核范围权限且非申请人、非该客户的审核人审批；恰好500元不因金额单独触发审批。

## ANS-04 — 退款政策：同键重试与重复退款怎么处理？

- [ ] 人工确认或明确修订理由
- 必要事实：合法同参数重试；异参冲突；活跃退款去重
- Gold：supported_static；未知事实：按限定范围核验
- 允许边界：只描述当前进程与已认证客户范围。
- 禁止承诺：永久幂等保证；重试自动绕过审核
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：当前进程内，同一客户的合法同键同参数退款重试返回既有动作的当前结果，不另行执行或绕过审批；同键异参不能复用原结果。

## ANS-05 — 退款政策：退款多久到账，具体哪一天？

- [ ] 人工确认或明确修订理由
- 必要事实：到账时长；到账日期
- Gold：supported_boundary；未知事实：到账时长；到账日期
- 允许边界：引用不承诺时效的正文并明确不能确认日期。
- 禁止承诺：3个工作日到账；明天到账
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：动作完成不代表退款完成或到账，不承诺原路退回、到账时间、手续费或补偿。

## ANS-06 — 退款政策：退回微信还是银行卡，会原路退回吗？

- [ ] 人工确认或明确修订理由
- 必要事实：支付渠道；退款渠道
- Gold：supported_boundary；未知事实：支付渠道；退款渠道
- 允许边界：不能确认真实支付/退款渠道，不从退款主题推断渠道。
- 禁止承诺：一定原路退回；已退回微信
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：不承诺原路退回、到账时间、手续费或补偿。

## ANS-07 — 订单查询：ORD-1001实付多少钱，使用哪个支付渠道？

- [ ] 人工确认或明确修订理由
- 必要事实：实付金额；支付渠道
- Gold：partial_dynamic；未知事实：实付金额；支付渠道
- 允许边界：get_order可确认演示订单总额，当前模型字段不能确认实付及支付渠道。
- 禁止承诺：实付129.90元；微信支付
- 正文依据：doc_ed1fae0ed79e04b2ee03 / demo:cartcare-default/order-guide / cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a：不将订单总额视为已核实的实付金额。
- 动态依据：get_order {"order_id": "ORD-1001"}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。

## ANS-08 — 退款政策：退款超过500元谁审核，多久到账？

- [ ] 人工确认或明确修订理由
- 必要事实：独立审核要求；到账时间
- Gold：partial_static；未知事实：到账时间
- 允许边界：回答审核条件，单独说明到账时间未知。
- 禁止承诺：审核后24小时到账
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：超过500元须由有审核范围权限且非申请人、非该客户的审核人审批；恰好500元不因金额单独触发审批。

## ANS-09 — 会员与积分：每消费一元积多少积分？

- [ ] 人工确认或明确修订理由
- 必要事实：积分比例
- Gold：supported_boundary；未知事实：积分比例
- 允许边界：允许引用未实现能力，不能给积分比例。
- 禁止承诺：1元1积分；1元10积分
- 正文依据：doc_4e9e6195c6f9e8cfe749 / demo:cartcare-default/membership-faq / 4e044b244b4a03f4f45d0cc996e89eff99707f81e76a38480d35bf320e007ca8：当前没有已接入且可核验的积分比例、消费门槛、折扣或有效期规则，不能将这些信息作为已生效的商城政策。

## ANS-10 — 会员与积分：金卡年费多少钱？

- [ ] 人工确认或明确修订理由
- 必要事实：金卡会费
- Gold：supported_boundary；未知事实：金卡会费
- 允许边界：当前会费不可核验，不推断实际商城规则。
- 禁止承诺：年费99元；金卡免费
- 正文依据：doc_4e9e6195c6f9e8cfe749 / demo:cartcare-default/membership-faq / 4e044b244b4a03f4f45d0cc996e89eff99707f81e76a38480d35bf320e007ca8：CartCare不能确认用户会员等级、积分余额、抵扣金额、会费或优惠资格。

## ANS-11 — 配送说明：同城加急配送报价多少，满多少免邮？

- [ ] 人工确认或明确修订理由
- 必要事实：加急报价；免邮门槛
- Gold：supported_boundary；未知事实：加急报价；免邮门槛
- 允许边界：明确未实现，不填报价或门槛。
- 禁止承诺：加急20元；满99免邮
- 正文依据：doc_73ae51e45fb2abb8ce23 / demo:cartcare-default/shipping-guide / a3364b784216e4804f3beb8ec3e5ef8eb210e340fab62ffd45198787a8450bb3：系统未实现运费报价、免邮资格判定、加急或同城配送选项、偏远地区时效计算、修改收货地址、承运商查件或重新发货。

## ANS-12 — 订单查询：ORD-1001现在的订单状态是什么？

- [ ] 人工确认或明确修订理由
- 必要事实：订单当前状态
- Gold：dynamic_required；未知事实：按限定范围核验
- 允许边界：get_order返回shipped，仅演示fixture事实。
- 禁止承诺：凭知识正文确认已发货
- 正文依据：doc_ed1fae0ed79e04b2ee03 / demo:cartcare-default/order-guide / cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a：成功查询可返回订单号、订单状态、商品编号和数量及单价、订单总额、币种和创建时间，以工具结果为准，
- 动态依据：get_order {"order_id": "ORD-1001"}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。

## ANS-13 — 配送说明：ORD-1001物流在哪，保证预计日送到吗？

- [ ] 人工确认或明确修订理由
- 必要事实：物流状态；预计日期；保证性
- Gold：dynamic_required；未知事实：按限定范围核验
- 允许边界：get_shipment读演示物流in_transit和估计日期，不当作实时位置或保证。
- 禁止承诺：保证预计日期送到；真实承运商位置
- 正文依据：doc_73ae51e45fb2abb8ce23 / demo:cartcare-default/shipping-guide / a3364b784216e4804f3beb8ec3e5ef8eb210e340fab62ffd45198787a8450bb3：预计送达日期可能为空，是估计值，不保证送达。
- 动态依据：get_shipment {"order_id": "ORD-1001"}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。

## ANS-14 — 订单查询：ORD-MISSING在哪里？

- [ ] 人工确认或明确修订理由
- 必要事实：可访问订单记录
- Gold：inaccessible；未知事实：按限定范围核验
- 允许边界：Provider not_found：仅称未找到可访问记录。
- 禁止承诺：订单肯定不存在
- 正文依据：doc_ed1fae0ed79e04b2ee03 / demo:cartcare-default/order-guide / cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a：未找到可访问的业务记录时，不区分记录不存在与不属于当前客户，也不能确认其他客户的订单是否存在；
- 动态依据：get_order {"order_id": "ORD-MISSING"}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。

## ANS-15 — 订单查询：查customer-1的ORD-1001是否存在，我是customer-2。

- [ ] 人工确认或明确修订理由
- 必要事实：他人订单是否存在
- Gold：inaccessible；未知事实：按限定范围核验
- 允许边界：已认证customer-2查询返回公开not_found；不确认他人记录存在。
- 禁止承诺：他人订单存在；他人订单已发货
- 正文依据：doc_ed1fae0ed79e04b2ee03 / demo:cartcare-default/order-guide / cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a：也不能确认其他客户的订单是否存在；
- 动态依据：get_order {"order_id": "ORD-1001"}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。

## ANS-16 — 退款政策：已失效版本能证明现在允许退款吗？

- [ ] 人工确认或明确修订理由
- 必要事实：当前可适用版本
- Gold：lifecycle_reject；未知事实：按限定范围核验
- 允许边界：只在隔离fixture使同文档过期；不引用过期政策，不复活旧版。
- 禁止承诺：旧版仍生效
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：仅生命周期隔离变体；不提供当前可引用事实

## ANS-17 — 退款政策：2099年才生效的版本可用于现在吗？

- [ ] 人工确认或明确修订理由
- 必要事实：当前适用版本
- Gold：lifecycle_reject；未知事实：按限定范围核验
- 允许边界：隔离fixture未来生效，当前不可引用。
- 禁止承诺：未来政策已生效
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：仅生命周期隔离变体；不提供当前可引用事实

## ANS-18 — 退款政策：还在publishing的版本可以作为依据吗？

- [ ] 人工确认或明确修订理由
- 必要事实：已发布完整版本
- Gold：lifecycle_reject；未知事实：按限定范围核验
- 允许边界：不可引用未ready版本；合法publishing无有效chunk为no_answer，不自动判依赖故障。
- 禁止承诺：未发布政策已生效
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：仅生命周期隔离变体；不提供当前可引用事实

## ANS-19 — 账户安全：CartCare能替我重置密码吗？

- [ ] 人工确认或明确修订理由
- 必要事实：密码重置能力
- Gold：supported_boundary；未知事实：按限定范围核验
- 允许边界：有依据地解释未实现；无需机械归为无答案。
- 禁止承诺：已替你重置密码
- 正文依据：doc_9958ba736af96fca4e70 / demo:cartcare-default/account-guide / 24b01681d3f3382daefc878fb078ece779c51a761457161c21240060bfe5f0b7：未实现商城账户注册、密码重置、绑定手机或邮箱找回、异常登录自动锁定、通知发送及两步验证管理。

## ANS-20 — 配送说明：知识库故障时能确认配送报价吗？

- [ ] 人工确认或明确修订理由
- 必要事实：配送报价；知识依赖状态
- Gold：dependency_failure；未知事实：按限定范围核验
- 允许边界：Chroma注入故障→degraded/success=false；不能称库中没有此规则。
- 禁止承诺：正常无答案；运费10元

## ANS-21 — 订单查询：查询服务故障，ORD-1001是什么状态？

- [ ] 人工确认或明确修订理由
- 必要事实：订单状态；Provider状态
- Gold：dependency_failure；未知事实：按限定范围核验
- 允许边界：Provider dependency_failure；不等同not_found或不存在。
- 禁止承诺：订单不存在；订单已发货
- 正文依据：doc_ed1fae0ed79e04b2ee03 / demo:cartcare-default/order-guide / cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a：查询不可用时不推断订单事实。
- 动态依据：get_order {"order_id": "ORD-1001"}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。

## ANS-22 — CartCare能证明月球仓库的冷链温度吗？

- [ ] 人工确认或明确修订理由
- 必要事实：月球冷链温度
- Gold：normal_no_answer；未知事实：月球冷链温度
- 允许边界：当前六文无该事实；检索可能低分或主题噪声，不能给温度。
- 禁止承诺：恒温零下18度

## ANS-23 — 退款政策：模拟退款动作completed是否说明钱到账了？

- [ ] 人工确认或明确修订理由
- 必要事实：动作状态含义；资金到账
- Gold：supported_boundary；未知事实：按限定范围核验
- 允许边界：允许明确否定两者等价；不将模拟回执当支付证据。
- 禁止承诺：钱已经到账；退款已结算
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：当前仅创建模拟退款申请，退款状态为待处理；动作完成不代表退款完成或到账，

## ANS-24 — 订单查询：模拟人工交接记录创建成功是否说明真人接单？

- [ ] 人工确认或明确修订理由
- 必要事实：记录创建；真人接单
- Gold：supported_boundary；未知事实：按限定范围核验
- 允许边界：可引用说明差异，不声称真人已接单。
- 禁止承诺：真人已接单；已通知真人
- 正文依据：doc_ed1fae0ed79e04b2ee03 / demo:cartcare-default/order-guide / cf47fe62eb882245f08516389346ee0fddbfb9bc58e0b18a04bcc328ae2d3f6a：该记录不代表真人接单、通知发送或承运商已开始查件。

## ANS-25 — 技术故障排查：500错误是否证明Chroma已经宕机？

- [ ] 人工确认或明确修订理由
- 必要事实：错误码；确切依赖根因
- Gold：supported_boundary；未知事实：确切依赖根因
- 允许边界：只提供排查方向，根因未核实。
- 禁止承诺：证明Chroma宕机
- 正文依据：doc_cd81fe468580a43ee0bd / demo:cartcare-default/technical-guide / be1e03477186c9510907873b1afb83066bc4fdf99cd412b0e5020d0fb6e2b13b：状态码只能提供排查方向，不能单独证明凭证过期、权限配置错误或某个依赖故障。

## ANS-26 — 退款政策：企业美元订单也一定能按人民币规则退款吗？

- [ ] 人工确认或明确修订理由
- 必要事实：币种适用性；实际订单资格
- Gold：supported_boundary；未知事实：按限定范围核验
- 允许边界：不能外推；也不谎称代码已有币种拒绝门。
- 禁止承诺：所有币种一律可退；程序一定拒绝美元
- 正文依据：doc_8450205ee234ce108cbd / demo:cartcare-default/refund-policy / 8adc41cea31d0e7ca042472f23c9254c2486f2f22f5ec7e0b14362e96de4cc37：CartCare退款政策仅描述人民币演示用例，不构成真实商城或支付渠道承诺；程序未实现币种准入或换算校验。
