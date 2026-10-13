# Gold v2 候选审核记录

2026-10-13；起始HEAD `98a590b343e0b244a77a0115168a8968fae940d9`。
**依据本轮用户人工讨论决定形成候选；最终验收与正式冻结待用户批准。不是自动标记人工审核通过。**
目标为事实检索Retrieval Quality；保持单Gold Chunk，可含多个必要事实；不测生成答案完整性。
冻结语料与有效时点沿用corpus_v1，2026-10-12T00:00:00Z；原v1/P1/P2-GATE均保留。

| Case | Query变化 | Gold/标签变化 | 状态 |
| --- | --- | --- | --- |
| A05-01 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-02 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-03 | 修改 | query, annotation_reason | 候选，待最终验收 |
| A05-04 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-05 | 保留 | gold_evidence, annotation_reason | 候选，待最终验收 |
| A05-06 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-07 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-08 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-09 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-10 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-11 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-12 | 保留 | annotation_reason | 候选，待最终验收 |
| A05-13 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-14 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-15 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-16 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-17 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-18 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-19 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-20 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-21 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-22 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-23 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-24 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-25 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-26 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-27 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-28 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-29 | 保留 | 全部保留 | 候选，待最终验收 |
| A05-30 | 保留 | 全部保留 | 候选，待最终验收 |

## A05-01 — 候选待验收

- Query：买完东西想把钱退回来，多久之内可以申请？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_dd816769efe7659f114e` / `7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864`。
- 决定理由：保留原口语问法与退款Gold；真实用户无须使用正式术语，政策Chunk应提供期限及起算点。不能因B0失败而改写。
- Gold原文（与冻结正文一致）：

> 订单创建后 7 天内

- 来源：`demo:cartcare-default/refund-policy`；版本：`refund-cancel-v1`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-02 — 候选待验收

- Query：忘掉登录口令了怎样找回账户？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_1348d91e6f873b93a77a` / `4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d`。
- 决定理由：账户安全指南是唯一充分Gold，明确绑定手机号或邮箱找回；技术指南仅说尝试重置，证据不充分，不新增Gold。
- Gold原文（与冻结正文一致）：

> 通过绑定的手机号或邮箱重置

- 来源：`demo:cartcare-default/account-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-03 — 候选待验收

- Query：我想看看买的东西发货了没有、现在是什么状态，应该怎么查？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_b18d553a21972fe4b3f5` / `4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3`。
- 决定理由：只修复表达不自然，问查询方法；不问具体订单实时状态，Gold仍是原订单指南。
- Gold原文（与冻结正文一致）：

> 通过订单号查询订单状态

- 来源：`demo:cartcare-default/order-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-04 — 候选待验收

- Query：普通送货大概几天能到？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_2efff27478d4aa1b0a90` / `df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 标准配送：3-5 个工作日送达

- 来源：`demo:cartcare-default/shipping-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-05 — 候选待验收

- Query：急着拿到包裹，快送收费多少？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_2efff27478d4aa1b0a90` / `df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2`。
- 决定理由：保留快送口语；Gold连续原文扩展为两个配送事实，两种可能方案不等于每人适用同城；一个Chunk已充分，无需多Gold框架。
- Gold原文（与冻结正文一致）：

> 加急配送：1-2 个工作日送达，运费 15 元。同城配送：当日达或次日达，运费 10 元

- 来源：`demo:cartcare-default/shipping-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 必要事实1：`加急配送：1-2 个工作日送达，运费 15 元`。
- 必要事实2：`同城配送：当日达或次日达，运费 10 元`。
- Retrieval成功条件：当前有效同一Gold Chunk提供两个事实。后续Answer Generation应说明两方案及适用条件，不只回答15元；本轮不增加Agent答案评分。
- 最终人工验收/冻结：**待用户确认**。

## A05-06 — 候选待验收

- Query：购物攒的分怎么折成钱用？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_15eee479ec6749cbefce` / `9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 100 积分 = 1 元

- 来源：`demo:cartcare-default/membership-faq`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-07 — 候选待验收

- Query：软件一打开就闪退该怎么办？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_f4878e309f60ff328b5d` / `830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 清除缓存后重启应用

- 来源：`demo:cartcare-default/technical-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-08 — 候选待验收

- Query：保护账号可以启用什么二次确认？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_1348d91e6f873b93a77a` / `4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 开启两步验证

- 来源：`demo:cartcare-default/account-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-09 — 候选待验收

- Query：生日那个月买东西积分享受什么待遇？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_15eee479ec6749cbefce` / `9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 生日当月消费可获得双倍积分

- 来源：`demo:cartcare-default/membership-faq`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-10 — 候选待验收

- Query：退款数额很大时还要谁同意？
- category：`paraphrase`；answerable：`True`。
- Gold Document / Chunk：`doc_dd816769efe7659f114e` / `7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 超过 500 元需人工审批

- 来源：`demo:cartcare-default/refund-policy`；版本：`refund-cancel-v1`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-11 — 候选待验收

- Query：账户安全的密码长度至少是多少？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_1348d91e6f873b93a77a` / `4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 密码长度至少 8 位

- 来源：`demo:cartcare-default/account-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-12 — 候选待验收

- Query：登录失败401和500服务器错误分别是什么原因？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_f4878e309f60ff328b5d` / `830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3`。
- 决定理由：保留Query/Gold/原跨度，仅明确401认证失败、500服务端问题，其他中间内容不属于必要事实。
- Gold原文（与冻结正文一致）：

> 登录失败 401 错误：表示认证失败，请检查用户名密码是否正确，或尝试重置密码。页面加载慢：检查网络连接，尝试切换 WiFi 或移动数据。支付失败：确认银行卡余额充足，检查是否开启了网上支付功能。500 服务器错误：这是服务端问题

- 来源：`demo:cartcare-default/technical-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 必要事实1原文：`登录失败 401 错误：表示认证失败`。
- 必要事实2原文：`500 服务器错误：这是服务端问题`。
- 原连续跨度保留以兼容现有字符串结构；网络/支付中间描述不是必要事实。
- 最终人工验收/冻结：**待用户确认**。

## A05-13 — 候选待验收

- Query：会员等级中银卡和金卡的消费门槛分别是多少？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_15eee479ec6749cbefce` / `9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）

- 来源：`demo:cartcare-default/membership-faq`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-14 — 候选待验收

- Query：配送说明中免运费的门槛是多少，不是退款审批金额？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_2efff27478d4aa1b0a90` / `df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 免运费（订单满 99 元）

- 来源：`demo:cartcare-default/shipping-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-15 — 候选待验收

- Query：订单查询中物流信息多久更新，而不是多久送达？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_b18d553a21972fe4b3f5` / `4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 物流信息通常在发货后 24 小时内更新

- 来源：`demo:cartcare-default/order-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-16 — 候选待验收

- Query：退款政策是否意味着不用查实时订单就保证退款成功？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_dd816769efe7659f114e` / `7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864`。
- 决定理由：原题问能否保证退款成功，现有规则边界支持否定，保持有答案和原Gold；不验证真实退款已成功。
- Gold原文（与冻结正文一致）：

> 退款请求是否可执行由实时订单事实和 PolicyEngine 决定

- 来源：`demo:cartcare-default/refund-policy`；版本：`refund-cancel-v1`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-17 — 候选待验收

- Query：积分有效期是一年还是订单退款的七天？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_15eee479ec6749cbefce` / `9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 积分有效期为 1 年

- 来源：`demo:cartcare-default/membership-faq`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-18 — 候选待验收

- Query：已经发货超过七天没收到，订单查询指南建议做什么？
- category：`ambiguity`；answerable：`True`。
- Gold Document / Chunk：`doc_b18d553a21972fe4b3f5` / `4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 联系客服申请查件

- 来源：`demo:cartcare-default/order-guide`；版本：`None`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-19 — 候选待验收

- Query：退款政策规定退款到账需要几个工作日？
- category：`no_answer`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：无法取得所问到账工作日数，保持无答案；不把未说明写成明确禁止。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 最终人工验收/冻结：**待用户确认**。

## A05-20 — 候选待验收

- Query：账户安全说明中客服可以替我关闭两步验证吗？
- category：`no_answer`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：无客服关闭两步验证权限规定，保持无答案；未知权限不等于明确禁止。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 最终人工验收/冻结：**待用户确认**。

## A05-21 — 候选待验收

- Query：订单查询：订单ORD-999今天到哪了？
- category：`no_answer`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：具体订单实时位置不在静态知识，保持原无答案；与03问查询方法不同。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 最终人工验收/冻结：**待用户确认**。

## A05-22 — 候选待验收

- Query：苹果手机电池的官方保修期是多少？
- category：`no_answer`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 最终人工验收/冻结：**待用户确认**。

## A05-23 — 候选待验收

- Query：会员与积分：金卡会费每年多少钱？
- category：`no_answer`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 最终人工验收/冻结：**待用户确认**。

## A05-24 — 候选待验收

- Query：隔离演示换货政策目前的换货期限是多少？
- category：`lifecycle`；answerable：`True`。
- Gold Document / Chunk：`eval-exchange` / `e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 换货期限为21天

- 来源：`demo:a05-p1-isolated/exchange`；版本：`demo-v2`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-25 — 候选待验收

- Query：现行隔离演示换货政策要求商品包装满足什么条件？
- category：`lifecycle`；answerable：`True`。
- Gold Document / Chunk：`eval-exchange` / `e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 换货商品必须保留完整包装

- 来源：`demo:a05-p1-isolated/exchange`；版本：`demo-v2`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-26 — 候选待验收

- Query：现行隔离演示换货政策每笔订单能换货几次？
- category：`lifecycle`；answerable：`True`。
- Gold Document / Chunk：`eval-exchange` / `e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525`。
- 决定理由：本次人工决定：其余已判定合理的题目保留Query、Gold、answerable、category及原说明，无充分理由不改写。
- Gold原文（与冻结正文一致）：

> 每笔订单最多换货一次

- 来源：`demo:a05-p1-isolated/exchange`；版本：`demo-v2`；chunk_index：`0`；固定时点有效且在P1 ready发布。
- 最终人工验收/冻结：**待用户确认**。

## A05-27 — 候选待验收

- Query：请仅根据demo-v1换货政策告诉我寄回地址。
- category：`lifecycle`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：旧demo-v1被demo-v2替代，只允许当前有效证据；历史地址存在也不能作为本轮Gold。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 排除版本：`eval-exchange@demo-v1`；原因：`superseded`；effective_at `2026-01-01T00:00:00Z`；expires_at `None`；publication_status `active`。旧正文保留但不作当前证据。
- 最终人工验收/冻结：**待用户确认**。

## A05-28 — 候选待验收

- Query：请仅根据demo-v3换货政策告诉我指定承运人。
- category：`lifecycle`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：demo-v3尚未在固定时点生效，不作为当前证据；不评历史/未来档案说明。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 排除版本：`eval-exchange@demo-v3`；原因：`not_yet_effective`；effective_at `2026-11-01T00:00:00Z`；expires_at `None`；publication_status `active`。旧正文保留但不作当前证据。
- 最终人工验收/冻结：**待用户确认**。

## A05-29 — 候选待验收

- Query：过期的隔离演示优惠券政策活动口令是什么？
- category：`lifecycle`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：优惠券已过期，不作为当前证据；不评历史档案查询。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 排除版本：`eval-coupon@demo-expired`；原因：`expired`；effective_at `2026-01-01T00:00:00Z`；expires_at `2026-09-01T00:00:00Z`；publication_status `active`。旧正文保留但不作当前证据。
- 最终人工验收/冻结：**待用户确认**。

## A05-30 — 候选待验收

- Query：撤销的隔离演示延保政策赠品是什么？
- category：`lifecycle`；answerable：`False`。
- Gold Document / Chunk：`None` / `None`。
- 决定理由：延保已撤销，不作为当前证据；不评历史档案查询。
- 正向证据：无；当前有效Chunk没有所问事实，未说明不意味着禁止。
- 排除版本：`eval-warranty@demo-revoked`；原因：`revoked`；effective_at `2026-01-01T00:00:00Z`；expires_at `None`；publication_status `revoked`。旧正文保留但不作当前证据。
- 最终人工验收/冻结：**待用户确认**。

## 开发集决定

- DEV-04原题不变，保留基础规则Gold；允许一步算术12×1=12；评分仍是检索规则证据。
- DEV-07改为：如果收货地址比较偏远，包裹可能要多等几天？
- DEV-07只询问额外天数，不要求正文没有的原因；其余开发题全部保留。

## 下一步批准后执行方案

1. 用户最终验收候选及审核记录；随后创建正式dataset_v2/dev_dataset_v2与独立freeze_v2，绑定沿用corpus_v1和审核版本，不覆盖旧freeze。
2. 新增正式v2协议/版本选择入口（当前load_frozen/runner只读v1，不能把候选放进v1路径或假称现有命令已支持v2）；最小修改评测入口而非生产检索。
3. 在新随机Chroma HTTP集合、同语料/Chunk/生命周期/Top5/0.35/时点、Rewrite/Rerank关闭条件下，对正式v2重新执行两轮B0-original；保存新的manifest/observations/summary/validation，保留P1。
4. A05-03的问法改变可能改变向量/排序，05/12的证据说明版本改变需记录；当前候选没有新质量测量，不从P1直接宣称v2指标。
5. 开发集只用于之后已批准的校准；正式语义实验仍blocked，下载/安装/计算授权尚未获得。

独立练习：打开配送Gold Chunk，把加急和同城两段各圈出时间与费用，核对候选gold_evidence连续覆盖两段；解释为什么检索到一个Chunk可支持两个事实，却不证明Agent会完整回答。
