# Gold v1 人工审核辅助表

**30条作者审核建议；独立人工审核未完成，所有用户决定均待填写。**
冻结时点2026-10-12T00:00:00Z；仅当前有效且ready的知识是答案证据。
建议先解决歧义/口径，再决定接受v1或批准创建v2。本文件不修改任何Gold。

| case_id | 建议 | 用户决定 |
| --- | --- | --- |
| A05-01 | 需人工判断 | 待审核 |
| A05-02 | 需人工判断 | 待审核 |
| A05-03 | 需人工判断 | 待审核 |
| A05-04 | 合理 | 待审核 |
| A05-05 | 疑似错误 | 待审核 |
| A05-06 | 合理 | 待审核 |
| A05-07 | 合理 | 待审核 |
| A05-08 | 合理 | 待审核 |
| A05-09 | 合理 | 待审核 |
| A05-10 | 合理 | 待审核 |
| A05-11 | 合理 | 待审核 |
| A05-12 | 需人工判断 | 待审核 |
| A05-13 | 合理 | 待审核 |
| A05-14 | 合理 | 待审核 |
| A05-15 | 合理 | 待审核 |
| A05-16 | 合理 | 待审核 |
| A05-17 | 合理 | 待审核 |
| A05-18 | 合理 | 待审核 |
| A05-19 | 需人工判断 | 待审核 |
| A05-20 | 需人工判断 | 待审核 |
| A05-21 | 合理 | 待审核 |
| A05-22 | 合理 | 待审核 |
| A05-23 | 合理 | 待审核 |
| A05-24 | 合理 | 待审核 |
| A05-25 | 合理 | 待审核 |
| A05-26 | 合理 | 待审核 |
| A05-27 | 需人工判断 | 待审核 |
| A05-28 | 需人工判断 | 待审核 |
| A05-29 | 需人工判断 | 待审核 |
| A05-30 | 需人工判断 | 待审核 |

## A05-01 — 需人工判断

- Query：买完东西想把钱退回来，多久之内可以申请？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_dd816769efe7659f114e`；Chunk：`7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864`；位置：`documents[0].content`。
- 原Gold证据（逐字）：

> 订单创建后 7 天内

- 完整实际Chunk（用于上下文复核）：

> CartCare 模拟客服政策说明，仅用于演示。订单创建后 7 天内、订单状态符合要求时可以请求退款。退款金额不能超过订单总额；超过 500 元需人工审批。退款请求是否可执行由实时订单事实和 PolicyEngine 决定。此文档不代表真实商城承诺或支付渠道处理时效。

- 版本与生命周期：来源 `demo:cartcare-default/refund-policy`；版本 `refund-cancel-v1`；effective_at `2026-09-30T00:00:00+00:00`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：“买完”可能指付款，而正文期限从订单创建起算；若接受口语映射则7天证据足够，不能把起算点改成付款。
- 修订建议：建议v2明确订单创建后申请退款的期限；或用户接受当前口语映射。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-02 — 需人工判断

- Query：忘掉登录口令了怎样找回账户？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_1348d91e6f873b93a77a`；Chunk：`4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d`；位置：`documents[2].content`。
- 原Gold证据（逐字）：

> 通过绑定的手机号或邮箱重置

- 完整实际Chunk（用于上下文复核）：

> 账户安全说明。建议用户定期修改密码，密码长度至少 8 位，包含字母和数字。如果忘记密码，可以通过绑定的手机号或邮箱重置。发现账户异常登录时，系统会自动锁定账户并发送通知。用户可以在安全设置中开启两步验证，提高账户安全性。不要将密码分享给他人，客服人员不会索要用户密码。

- 版本与生命周期：来源 `demo:cartcare-default/account-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 补充对照证据 `doc_f4878e309f60ff328b5d`：

> 或尝试重置密码

- 对照来源生命周期：来源 `demo:cartcare-default/technical-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：可能：doc_f4878e309f60ff328b5d，是否充分需人工确认。
- 能否回答/无答案理由及争议：账户指南提供手机/邮箱重置；技术指南也建议认证失败时尝试重置密码。宽泛“找回账户”可能允许后者作为部分有效来源，现有单Gold可能过窄。
- 修订建议：建议v2明确要问绑定手机/邮箱的找回方式，或改为多Gold并重新定义Recall。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-03 — 需人工判断

- Query：收到货的进展能在哪里看？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_b18d553a21972fe4b3f5`；Chunk：`4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3`；位置：`documents[1].content`。
- 原Gold证据（逐字）：

> 通过订单号查询订单状态

- 完整实际Chunk（用于上下文复核）：

> 订单查询指南。用户可以通过订单号查询订单状态。订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。物流信息通常在发货后 24 小时内更新。如果订单显示异常，请提供订单号联系客服处理。

- 版本与生命周期：来源 `demo:cartcare-default/order-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：“收到货的进展”表达不自然，可能指配送进度，也可能是签收后流程。订单状态指南只能支持按订单号查状态。
- 修订建议：建议v2明确“配送/订单状态在哪里查”，不要默认解释签收后流程。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-04 — 合理

- Query：普通送货大概几天能到？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_2efff27478d4aa1b0a90`；Chunk：`df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2`；位置：`documents[5].content`。
- 原Gold证据（逐字）：

> 标准配送：3-5 个工作日送达

- 完整实际Chunk（用于上下文复核）：

> 配送服务说明。标准配送：3-5 个工作日送达，免运费（订单满 99 元）。加急配送：1-2 个工作日送达，运费 15 元。同城配送：当日达或次日达，运费 10 元。偏远地区可能需要额外 2-3 天。配送时间为每天 9:00-18:00，节假日可能延迟。如果需要修改收货地址，请在发货前联系客服。

- 版本与生命周期：来源 `demo:cartcare-default/shipping-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：普通送货可合理对应标准配送，正文明确3-5个工作日；不能把工作日转换为自然日。
- 修订建议：保留；审核时确认普通=标准配送的演示语义。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-05 — 疑似错误

- Query：急着拿到包裹，快送收费多少？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_2efff27478d4aa1b0a90`；Chunk：`df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2`；位置：`documents[5].content`。
- 原Gold证据（逐字）：

> 加急配送：1-2 个工作日送达，运费 15 元

- 完整实际Chunk（用于上下文复核）：

> 配送服务说明。标准配送：3-5 个工作日送达，免运费（订单满 99 元）。加急配送：1-2 个工作日送达，运费 15 元。同城配送：当日达或次日达，运费 10 元。偏远地区可能需要额外 2-3 天。配送时间为每天 9:00-18:00，节假日可能延迟。如果需要修改收货地址，请在发货前联系客服。

- 版本与生命周期：来源 `demo:cartcare-default/shipping-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 补充对照证据 `doc_2efff27478d4aa1b0a90`：

> 同城配送：当日达或次日达，运费 10 元

- 对照来源生命周期：来源 `demo:cartcare-default/shipping-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：“急着拿到”“快送”未明确加急或同城，两者均满足快速需求且价格分别15元/10元。单独指定加急15元的Gold事实可能过窄；同一Gold chunk含两种方案不等于问题没有歧义。
- 修订建议：建议v2明确“加急配送收费”，或把答案定义成需澄清/比较两种方案并补齐证据。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-06 — 合理

- Query：购物攒的分怎么折成钱用？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_15eee479ec6749cbefce`；Chunk：`9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`；位置：`documents[4].content`。
- 原Gold证据（逐字）：

> 100 积分 = 1 元

- 完整实际Chunk（用于上下文复核）：

> 会员积分规则。每消费 1 元累积 1 积分。积分可以在下次购物时抵扣，100 积分 = 1 元。会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。积分有效期为 1 年，过期自动清零。生日当月消费可获得双倍积分。

- 版本与生命周期：来源 `demo:cartcare-default/membership-faq`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：积分折成钱由100积分=1元直接支持，且正文说明下次购物抵扣；不是现金提现。
- 修订建议：保留，并禁止把抵扣说成提现。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-07 — 合理

- Query：软件一打开就闪退该怎么办？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_f4878e309f60ff328b5d`；Chunk：`830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3`；位置：`documents[3].content`。
- 原Gold证据（逐字）：

> 清除缓存后重启应用

- 完整实际Chunk（用于上下文复核）：

> 常见技术问题排查。应用崩溃：请尝试清除缓存后重启应用，如果问题持续请更新到最新版本。登录失败 401 错误：表示认证失败，请检查用户名密码是否正确，或尝试重置密码。页面加载慢：检查网络连接，尝试切换 WiFi 或移动数据。支付失败：确认银行卡余额充足，检查是否开启了网上支付功能。500 服务器错误：这是服务端问题，请稍后重试，如果持续出现请联系技术支持。

- 版本与生命周期：来源 `demo:cartcare-default/technical-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：“闪退”与应用崩溃的处理对应，清缓存重启是第一步；如果持续还需要更新。
- 修订建议：保留，完整chunk还提供持续故障处理。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-08 — 合理

- Query：保护账号可以启用什么二次确认？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_1348d91e6f873b93a77a`；Chunk：`4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d`；位置：`documents[2].content`。
- 原Gold证据（逐字）：

> 开启两步验证

- 完整实际Chunk（用于上下文复核）：

> 账户安全说明。建议用户定期修改密码，密码长度至少 8 位，包含字母和数字。如果忘记密码，可以通过绑定的手机号或邮箱重置。发现账户异常登录时，系统会自动锁定账户并发送通知。用户可以在安全设置中开启两步验证，提高账户安全性。不要将密码分享给他人，客服人员不会索要用户密码。

- 版本与生命周期：来源 `demo:cartcare-default/account-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：二次确认可对应两步验证，账户正文明确可开启；未涉及关闭或客服权限。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-09 — 合理

- Query：生日那个月买东西积分享受什么待遇？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_15eee479ec6749cbefce`；Chunk：`9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`；位置：`documents[4].content`。
- 原Gold证据（逐字）：

> 生日当月消费可获得双倍积分

- 完整实际Chunk（用于上下文复核）：

> 会员积分规则。每消费 1 元累积 1 积分。积分可以在下次购物时抵扣，100 积分 = 1 元。会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。积分有效期为 1 年，过期自动清零。生日当月消费可获得双倍积分。

- 版本与生命周期：来源 `demo:cartcare-default/membership-faq`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：生日当月消费双倍积分与问题直接对应，不需要动态订单数据。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-10 — 合理

- Query：退款数额很大时还要谁同意？
- Category：`paraphrase`；answerable：`True`。
- Gold Document：`doc_dd816769efe7659f114e`；Chunk：`7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864`；位置：`documents[0].content`。
- 原Gold证据（逐字）：

> 超过 500 元需人工审批

- 完整实际Chunk（用于上下文复核）：

> CartCare 模拟客服政策说明，仅用于演示。订单创建后 7 天内、订单状态符合要求时可以请求退款。退款金额不能超过订单总额；超过 500 元需人工审批。退款请求是否可执行由实时订单事实和 PolicyEngine 决定。此文档不代表真实商城承诺或支付渠道处理时效。

- 版本与生命周期：来源 `demo:cartcare-default/refund-policy`；版本 `refund-cancel-v1`；effective_at `2026-09-30T00:00:00+00:00`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：退款数额大时谁同意由超过500元需人工审批直接支持；“大”在回答中需明确阈值。
- 修订建议：保留；不能泛化为所有退款都审批。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-11 — 合理

- Query：账户安全的密码长度至少是多少？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_1348d91e6f873b93a77a`；Chunk：`4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d`；位置：`documents[2].content`。
- 原Gold证据（逐字）：

> 密码长度至少 8 位

- 完整实际Chunk（用于上下文复核）：

> 账户安全说明。建议用户定期修改密码，密码长度至少 8 位，包含字母和数字。如果忘记密码，可以通过绑定的手机号或邮箱重置。发现账户异常登录时，系统会自动锁定账户并发送通知。用户可以在安全设置中开启两步验证，提高账户安全性。不要将密码分享给他人，客服人员不会索要用户密码。

- 版本与生命周期：来源 `demo:cartcare-default/account-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：密码最低长度8位直接给出；其他字母数字条件在同chunk，可附带但非本题必要。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-12 — 需人工判断

- Query：登录失败401和500服务器错误分别是什么原因？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_f4878e309f60ff328b5d`；Chunk：`830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3`；位置：`documents[3].content`。
- 原Gold证据（逐字）：

> 登录失败 401 错误：表示认证失败，请检查用户名密码是否正确，或尝试重置密码。页面加载慢：检查网络连接，尝试切换 WiFi 或移动数据。支付失败：确认银行卡余额充足，检查是否开启了网上支付功能。500 服务器错误：这是服务端问题

- 完整实际Chunk（用于上下文复核）：

> 常见技术问题排查。应用崩溃：请尝试清除缓存后重启应用，如果问题持续请更新到最新版本。登录失败 401 错误：表示认证失败，请检查用户名密码是否正确，或尝试重置密码。页面加载慢：检查网络连接，尝试切换 WiFi 或移动数据。支付失败：确认银行卡余额充足，检查是否开启了网上支付功能。500 服务器错误：这是服务端问题，请稍后重试，如果持续出现请联系技术支持。

- 版本与生命周期：来源 `demo:cartcare-default/technical-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 补充对照证据 `doc_f4878e309f60ff328b5d`：

> 登录失败 401 错误：表示认证失败

- 对照来源生命周期：来源 `demo:cartcare-default/technical-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 补充对照证据 `doc_f4878e309f60ff328b5d`：

> 500 服务器错误：这是服务端问题

- 对照来源生命周期：来源 `demo:cartcare-default/technical-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：同一chunk确实含401认证失败与500服务端问题；原Gold连续长引文混入页面/支付无关事实，但两项目标事实均存在。不是缺失Gold，需确认“原因”仅要求文档解释而非具体根因。
- 修订建议：可接受v1；若v2，改为两个准确短证据跨度，或将问题写为两种错误各表示什么。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-13 — 合理

- Query：会员等级中银卡和金卡的消费门槛分别是多少？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_15eee479ec6749cbefce`；Chunk：`9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`；位置：`documents[4].content`。
- 原Gold证据（逐字）：

> 银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）

- 完整实际Chunk（用于上下文复核）：

> 会员积分规则。每消费 1 元累积 1 积分。积分可以在下次购物时抵扣，100 积分 = 1 元。会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。积分有效期为 1 年，过期自动清零。生日当月消费可获得双倍积分。

- 版本与生命周期：来源 `demo:cartcare-default/membership-faq`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：银卡1000元、金卡5000元累计消费同时在原Gold，引文支持两个门槛。
- 修订建议：保留；这是累计消费而非会费。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-14 — 合理

- Query：配送说明中免运费的门槛是多少，不是退款审批金额？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_2efff27478d4aa1b0a90`；Chunk：`df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2`；位置：`documents[5].content`。
- 原Gold证据（逐字）：

> 免运费（订单满 99 元）

- 完整实际Chunk（用于上下文复核）：

> 配送服务说明。标准配送：3-5 个工作日送达，免运费（订单满 99 元）。加急配送：1-2 个工作日送达，运费 15 元。同城配送：当日达或次日达，运费 10 元。偏远地区可能需要额外 2-3 天。配送时间为每天 9:00-18:00，节假日可能延迟。如果需要修改收货地址，请在发货前联系客服。

- 版本与生命周期：来源 `demo:cartcare-default/shipping-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：明确问免运费且否定退款金额，配送99元足够；退款500元只是干扰事实，不能作为替代答案。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-15 — 合理

- Query：订单查询中物流信息多久更新，而不是多久送达？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_b18d553a21972fe4b3f5`；Chunk：`4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3`；位置：`documents[1].content`。
- 原Gold证据（逐字）：

> 物流信息通常在发货后 24 小时内更新

- 完整实际Chunk（用于上下文复核）：

> 订单查询指南。用户可以通过订单号查询订单状态。订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。物流信息通常在发货后 24 小时内更新。如果订单显示异常，请提供订单号联系客服处理。

- 版本与生命周期：来源 `demo:cartcare-default/order-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：24小时是发货后物流信息更新，不是送达时长；指南精确区分。
- 修订建议：保留，回答保留“通常/发货后”限定。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-16 — 合理

- Query：退款政策是否意味着不用查实时订单就保证退款成功？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_dd816769efe7659f114e`；Chunk：`7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864`；位置：`documents[0].content`。
- 原Gold证据（逐字）：

> 退款请求是否可执行由实时订单事实和 PolicyEngine 决定

- 完整实际Chunk（用于上下文复核）：

> CartCare 模拟客服政策说明，仅用于演示。订单创建后 7 天内、订单状态符合要求时可以请求退款。退款金额不能超过订单总额；超过 500 元需人工审批。退款请求是否可执行由实时订单事实和 PolicyEngine 决定。此文档不代表真实商城承诺或支付渠道处理时效。

- 版本与生命周期：来源 `demo:cartcare-default/refund-policy`；版本 `refund-cancel-v1`；effective_at `2026-09-30T00:00:00+00:00`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：这是要求否定“无事实保证成功”的问题；正文明确是否可执行由实时订单事实与PolicyEngine决定，直接支持否定回答。answerable=true合理，和缺具体到账数字的19题不同。
- 修订建议：保留；证据只能说明规则边界，不证明任何实际订单已退款。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-17 — 合理

- Query：积分有效期是一年还是订单退款的七天？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_15eee479ec6749cbefce`；Chunk：`9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`；位置：`documents[4].content`。
- 原Gold证据（逐字）：

> 积分有效期为 1 年

- 完整实际Chunk（用于上下文复核）：

> 会员积分规则。每消费 1 元累积 1 积分。积分可以在下次购物时抵扣，100 积分 = 1 元。会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。积分有效期为 1 年，过期自动清零。生日当月消费可获得双倍积分。

- 版本与生命周期：来源 `demo:cartcare-default/membership-faq`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：积分有效期1年直接支持；退款7天是另一主题，不能成为积分有效期的替代Gold。
- 修订建议：保留，正文也写过期清零。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-18 — 合理

- Query：已经发货超过七天没收到，订单查询指南建议做什么？
- Category：`ambiguity`；answerable：`True`。
- Gold Document：`doc_b18d553a21972fe4b3f5`；Chunk：`4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3`；位置：`documents[1].content`。
- 原Gold证据（逐字）：

> 联系客服申请查件

- 完整实际Chunk（用于上下文复核）：

> 订单查询指南。用户可以通过订单号查询订单状态。订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。物流信息通常在发货后 24 小时内更新。如果订单显示异常，请提供订单号联系客服处理。

- 版本与生命周期：来源 `demo:cartcare-default/order-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：已发货超过7天未收到时申请查件在指南直接出现，不代表承诺赔偿或退款。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-19 — 需人工判断

- Query：退款政策规定退款到账需要几个工作日？
- Category：`no_answer`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 当前有效版本/时间范围：见下方有效语料清单；无替代Gold来源，相关主题不补全缺失事实。
- 补充对照证据 `doc_dd816769efe7659f114e`：

> 此文档不代表真实商城承诺或支付渠道处理时效

- 对照来源生命周期：来源 `demo:cartcare-default/refund-policy`；版本 `refund-cancel-v1`；effective_at `2026-09-30T00:00:00+00:00`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：正文明确不代表支付渠道处理时效，无法给出所问工作日数；若answerable要求具体事实，则false合理。若允许“文档未规定”作为答案，应另设可回答拒绝/说明类型，不能悄改二元分母。
- 修订建议：用户确认answerable的操作定义；建议保持“所问事实是否存在”的口径。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-20 — 需人工判断

- Query：账户安全说明中客服可以替我关闭两步验证吗？
- Category：`no_answer`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 当前有效版本/时间范围：见下方有效语料清单；无替代Gold来源，相关主题不补全缺失事实。
- 补充对照证据 `doc_1348d91e6f873b93a77a`：

> 用户可以在安全设置中开启两步验证，提高账户安全性

- 对照来源生命周期：来源 `demo:cartcare-default/account-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：正文只说明开启两步验证，无客服关闭权限。不能推断客服能或不能关闭；以所问权限事实是否存在为标准则无答案。
- 修订建议：用户确认未知权限与明确禁止的区别；不要把未知写成禁止。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-21 — 合理

- Query：订单查询：订单ORD-999今天到哪了？
- Category：`no_answer`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 当前有效版本/时间范围：见下方有效语料清单；无替代Gold来源，相关主题不补全缺失事实。
- 补充对照证据 `doc_b18d553a21972fe4b3f5`：

> 用户可以通过订单号查询订单状态

- 对照来源生命周期：来源 `demo:cartcare-default/order-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：具体订单位置属于动态事实；指南只有按订单号查询的方法，没有ORD-999记录，不能用静态指南回答今天的位置。
- 修订建议：保留。Agent未来可能调用Provider，但本检索实验无答案。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-22 — 合理

- Query：苹果手机电池的官方保修期是多少？
- Category：`no_answer`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 当前有效版本/时间范围：见下方有效语料清单；无替代Gold来源，相关主题不补全缺失事实。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：所有冻结有效文档均无苹果电池官方保修政策，撤销的虚构延保也不属于该产品。
- 修订建议：保留；不从通用常识补Gold。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-23 — 合理

- Query：会员与积分：金卡会费每年多少钱？
- Category：`no_answer`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 当前有效版本/时间范围：见下方有效语料清单；无替代Gold来源，相关主题不补全缺失事实。
- 补充对照证据 `doc_15eee479ec6749cbefce`：

> 金卡会员（累计消费 5000 元）

- 对照来源生命周期：来源 `demo:cartcare-default/membership-faq`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：会员资料只有累计消费门槛/折扣/积分，没有金卡年费；门槛不等于会费。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-24 — 合理

- Query：隔离演示换货政策目前的换货期限是多少？
- Category：`lifecycle`；answerable：`True`。
- Gold Document：`eval-exchange`；Chunk：`e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525`；位置：`documents[7].content`。
- 原Gold证据（逐字）：

> 换货期限为21天

- 完整实际Chunk（用于上下文复核）：

> 隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

- 版本与生命周期：来源 `demo:a05-p1-isolated/exchange`；版本 `demo-v2`；effective_at `2026-10-01T00:00:00Z`；expires_at `无`；publication_status `active`；supersedes `['demo-v1']`；被替代版本 `['demo-v3']`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：demo-v2当前有效且ready，21天直接支持。v1已被替代，v3尚未生效，不能混入14/45天。
- 修订建议：保留隔离演示标记，不当作真实退款规则。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-25 — 合理

- Query：现行隔离演示换货政策要求商品包装满足什么条件？
- Category：`lifecycle`；answerable：`True`。
- Gold Document：`eval-exchange`；Chunk：`e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525`；位置：`documents[7].content`。
- 原Gold证据（逐字）：

> 换货商品必须保留完整包装

- 完整实际Chunk（用于上下文复核）：

> 隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

- 版本与生命周期：来源 `demo:a05-p1-isolated/exchange`；版本 `demo-v2`；effective_at `2026-10-01T00:00:00Z`；expires_at `无`；publication_status `active`；supersedes `['demo-v1']`；被替代版本 `['demo-v3']`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：有效demo-v2明确必须完整包装，旧/未来文档不提供另一有效答案。
- 修订建议：保留。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-26 — 合理

- Query：现行隔离演示换货政策每笔订单能换货几次？
- Category：`lifecycle`；answerable：`True`。
- Gold Document：`eval-exchange`；Chunk：`e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525`；位置：`documents[7].content`。
- 原Gold证据（逐字）：

> 每笔订单最多换货一次

- 完整实际Chunk（用于上下文复核）：

> 隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

- 版本与生命周期：来源 `demo:a05-p1-isolated/exchange`；版本 `demo-v2`；effective_at `2026-10-01T00:00:00Z`；expires_at `无`；publication_status `active`；supersedes `['demo-v1']`；被替代版本 `['demo-v3']`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：有效demo-v2每笔订单最多一次，直接支持次数问题。
- 修订建议：保留；没有业务执行成功含义。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-27 — 需人工判断

- Query：请仅根据demo-v1换货政策告诉我寄回地址。
- Category：`lifecycle`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 排除的Document/Chunk：`eval-exchange` / `e63f7534951058290146662e7acf358002fe2600fa9d3469573772a9f7c612b0`；不是正向Gold。
- 失效正文原文（仅供审核，不允许作为本实验答案）：

> 隔离评测虚构换货政策，不是商城承诺。换货期限为14天。demo-v1寄回地址为青松路14号。

- 版本与生命周期：来源 `demo:a05-p1-isolated/exchange`；版本 `demo-v1`；effective_at `2026-01-01T00:00:00Z`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `['demo-v2']`；固定时点有效 `False`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：demo-v1的地址确实在冻结物理语料，但v2生效后v1被supersedes退役。当前有效证据范围内无答案；若用户期望查询历史版本，其false标签将不合理。
- 修订建议：用户确认本测试只允许现行证据；v2可在题目显式写“仅用当前有效知识”，或另建历史查询测试。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-28 — 需人工判断

- Query：请仅根据demo-v3换货政策告诉我指定承运人。
- Category：`lifecycle`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 排除的Document/Chunk：`eval-exchange` / `46e793a80d27465f89e2ea092bc00ffb563bb4ad68242da9ae56a3023053d549`；不是正向Gold。
- 失效正文原文（仅供审核，不允许作为本实验答案）：

> 隔离评测虚构未来換货政策，不是商城承诺。换货期限为45天。demo-v3指定承运人为雪鹿快递。

- 版本与生命周期：来源 `demo:a05-p1-isolated/exchange`；版本 `demo-v3`；effective_at `2026-11-01T00:00:00Z`；expires_at `无`；publication_status `active`；supersedes `['demo-v2']`；被替代版本 `[]`；固定时点有效 `False`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：demo-v3承运人事实存在，但11月1日才生效。10月12日当前有效证据范围不允许引用；未来版本说明与现行答复是不同任务。
- 修订建议：确认当前有效范围；v2可显式强调当前时点，而非用未来计划解释为已生效。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-29 — 需人工判断

- Query：过期的隔离演示优惠券政策活动口令是什么？
- Category：`lifecycle`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 排除的Document/Chunk：`eval-coupon` / `0f64495c1c7029731bdf2ab8552c2e5906f1c4616b0ef38d9e2a6c13f2370023`；不是正向Gold。
- 失效正文原文（仅供审核，不允许作为本实验答案）：

> 隔离评测虚构且过期的优惠券政策。活动口令为秋叶2026，优惠券可抵扣20元。

- 版本与生命周期：来源 `demo:a05-p1-isolated/coupon`；版本 `demo-expired`；effective_at `2026-01-01T00:00:00Z`；expires_at `2026-09-01T00:00:00Z`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `False`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：优惠券口令确实在物理语料，9月1日已过期。无答案来自当前有效范围，不是正文没有该事实。
- 修订建议：确认过期资料不可用作本实验答案；如要历史说明需新实验口径。
- 用户审核决定：**待审核**（不自动标记通过）。

## A05-30 — 需人工判断

- Query：撤销的隔离演示延保政策赠品是什么？
- Category：`lifecycle`；answerable：`False`。
- Gold Document：`None`；Chunk：`None`；位置：`All eligible documents at frozen as_of; scoped absence label`。
- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。
- 排除的Document/Chunk：`eval-warranty` / `9db3c0cf7c21a23ee86a4159b32af95651cfa98f42e06b68e4256b0e0389948a`；不是正向Gold。
- 失效正文原文（仅供审核，不允许作为本实验答案）：

> 隔离评测虚构且撤销的延保政策。延保赠品为蓝鲸收纳袋。

- 版本与生命周期：来源 `demo:a05-p1-isolated/warranty`；版本 `demo-revoked`；effective_at `2026-01-01T00:00:00Z`；expires_at `无`；publication_status `revoked`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `False`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- 是否多个有效答案来源：未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义。
- 能否回答/无答案理由及争议：延保赠品确实在物理语料，但publication_status=revoked。无答案标签依赖当前有效证据范围。
- 修订建议：确认撤销内容只用于负向过滤验证，不允许历史证据答复。
- 用户审核决定：**待审核**（不自动标记通过）。

## 当前有效语料及版本清单

- `doc_dd816769efe7659f114e`：来源 `demo:cartcare-default/refund-policy`；版本 `refund-cancel-v1`；effective_at `2026-09-30T00:00:00+00:00`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- `doc_b18d553a21972fe4b3f5`：来源 `demo:cartcare-default/order-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- `doc_1348d91e6f873b93a77a`：来源 `demo:cartcare-default/account-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- `doc_f4878e309f60ff328b5d`：来源 `demo:cartcare-default/technical-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- `doc_15eee479ec6749cbefce`：来源 `demo:cartcare-default/membership-faq`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- `doc_2efff27478d4aa1b0a90`：来源 `demo:cartcare-default/shipping-guide`；版本 `非政策，无版本`；effective_at `无时间限制`；expires_at `无`；publication_status `active`；supersedes `[]`；被替代版本 `[]`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。
- `eval-exchange`：来源 `demo:a05-p1-isolated/exchange`；版本 `demo-v2`；effective_at `2026-10-01T00:00:00Z`；expires_at `无`；publication_status `active`；supersedes `['demo-v1']`；被替代版本 `['demo-v3']`；固定时点有效 `True`。所有冻结版本通过P1 ready发布，失效与未发布须区分。

## v2 决策建议

Propose v2 after user resolves A05-05 ambiguity and A05-02 alternative-source scope; do not modify v1. A05-19/20 and 27-30 require scope decisions.
若批准更改query/Gold/answerable/corpus，应创建dataset_v2及对应freeze与审核版本；本轮不修改v1。
改问法会改变向量与召回，改Gold/可回答性会改变Recall/MRR/FPR分母或成功条件；需对批准版本重新运行B0，原P1仍作为v1历史证据。
即使只精简证据跨度，也应新版本保留来源；重新B0可验证引用充分性与版本口径，不能把旧结果冒充新版本。
