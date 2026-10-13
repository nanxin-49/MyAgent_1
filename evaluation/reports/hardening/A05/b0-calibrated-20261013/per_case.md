# A05 B0-calibrated：逐题检索与归因

此表沿用已批准Gold；分析不产生新的人工批准或修改标签。完整raw/final内容、distance、metadata、hash、citation见observations.json。

| 题号 | Query | raw Gold排名 | Gold分数 | 0.35→0.20最终Gold排名 | 0.35→0.20状态 | 归因 |
| --- | --- | --- | --- | --- | --- | --- |
| A05-01 | 买完东西想把钱退回来，多久之内可以申请？ | None | None | None→None | low_confidence→low_confidence | 原始候选未召回 |
| A05-02 | 忘掉登录口令了怎样找回账户？ | 1 | 0.14907120470975777 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-03 | 我想看看买的东西发货了没有、现在是什么状态，应该怎么查？ | 5 | 0.010936966398805259 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-04 | 普通送货大概几天能到？ | 4 | 0.0 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-05 | 急着拿到包裹，快送收费多少？ | None | None | None→None | low_confidence→low_confidence | 原始候选未召回 |
| A05-06 | 购物攒的分怎么折成钱用？ | None | None | None→None | low_confidence→low_confidence | 原始候选未召回 |
| A05-07 | 软件一打开就闪退该怎么办？ | 3 | 0.015113398518462828 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-08 | 保护账号可以启用什么二次确认？ | 3 | 0.014322297262892025 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-09 | 生日那个月买东西积分享受什么待遇？ | 1 | 0.1440164648759914 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-10 | 退款数额很大时还要谁同意？ | 1 | 0.15666989177144985 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-11 | 账户安全的密码长度至少是多少？ | 1 | 0.5012804124668988 | 1→1 | usable→usable | 通过 |
| A05-12 | 登录失败401和500服务器错误分别是什么原因？ | 1 | 0.16030179701521774 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-13 | 会员等级中银卡和金卡的消费门槛分别是多少？ | 1 | 0.22850355248072407 | None→1 | low_confidence→usable | 通过 |
| A05-14 | 配送说明中免运费的门槛是多少，不是退款审批金额？ | 1 | 0.3294345673889266 | None→1 | low_confidence→usable | 通过 |
| A05-15 | 订单查询中物流信息多久更新，而不是多久送达？ | 1 | 0.34154835536126926 | None→1 | low_confidence→usable | 通过 |
| A05-16 | 退款政策是否意味着不用查实时订单就保证退款成功？ | 1 | 0.4677476696899203 | 1→1 | usable→usable | 通过 |
| A05-17 | 积分有效期是一年还是订单退款的七天？ | 2 | 0.14940357414893368 | None→None | low_confidence→low_confidence | 正确候选被分数过滤 |
| A05-18 | 已经发货超过七天没收到，订单查询指南建议做什么？ | 1 | 0.41626205575938746 | 1→1 | usable→usable | 通过 |
| A05-19 | 退款政策规定退款到账需要几个工作日？ | None | None | None→None | usable→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-20 | 账户安全说明中客服可以替我关闭两步验证吗？ | None | None | None→None | usable→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-21 | 订单查询：订单ORD-999今天到哪了？ | None | None | None→None | usable→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-22 | 苹果手机电池的官方保修期是多少？ | None | None | None→None | low_confidence→low_confidence | 通过 |
| A05-23 | 会员与积分：金卡会费每年多少钱？ | None | None | None→None | usable→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-24 | 隔离演示换货政策目前的换货期限是多少？ | 1 | 0.7077252216167482 | 1→1 | usable→usable | 通过 |
| A05-25 | 现行隔离演示换货政策要求商品包装满足什么条件？ | 1 | 0.5628234135020641 | 1→1 | usable→usable | 通过 |
| A05-26 | 现行隔离演示换货政策每笔订单能换货几次？ | 1 | 0.7390384934799793 | 1→1 | usable→usable | 通过 |
| A05-27 | 请仅根据demo-v1换货政策告诉我寄回地址。 | None | None | None→None | low_confidence→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-28 | 请仅根据demo-v3换货政策告诉我指定承运人。 | None | None | None→None | low_confidence→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-29 | 过期的隔离演示优惠券政策活动口令是什么？ | None | None | None→None | low_confidence→usable | 无答案问题错误判为usable；片段事实不足 |
| A05-30 | 撤销的隔离演示延保政策赠品是什么？ | None | None | None→None | low_confidence→usable | 无答案问题错误判为usable；片段事实不足 |

## A05-01：买完东西想把钱退回来，多久之内可以申请？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864；Gold evidence=订单创建后 7 天内
- 归因：原始候选未召回。冻结有效Gold未进入Top5；不能归因为阈值过滤。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/refund-policy 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.025048972350708465 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 2 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.013076645040036694 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 3 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.012265554732729611 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 4 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.011862805581288938 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.009662851116900573 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[]

最终片段正文：无

## A05-02：忘掉登录口令了怎样找回账户？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d；Gold evidence=通过绑定的手机号或邮箱重置
- 归因：正确候选被分数过滤。Gold在raw rank=1，score=0.14907120470975777<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/account-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.14907120470975777 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 2 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.02893995580863784 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 3 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.016666667360940246 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.01556432075745251 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.014119562822511367 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |

最终引用：[]

最终片段正文：无

## A05-03：我想看看买的东西发货了没有、现在是什么状态，应该怎么查？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3；Gold evidence=通过订单号查询订单状态
- 归因：正确候选被分数过滤。Gold在raw rank=5，score=0.010936966398805259<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：根据2026-10-13人工讨论最小修改不自然问法，保留口语表达。本题问如何查询订单状态；订单查询指南的按订单号查询规则充分支持，不要求RAG提供某个具体订单实时位置。Gold Chunk不变。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.05163978040907857 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.03616821326927078 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 3 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.011547005767186147 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.011308282771333777 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.010936966398805259 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |

最终引用：[]

最终片段正文：无

## A05-04：普通送货大概几天能到？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2；Gold evidence=标准配送：3-5 个工作日送达
- 归因：正确候选被分数过滤。Gold在raw rank=4，score=0.0<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/shipping-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.0167084910783889 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 2 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.013280318429048643 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 3 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.0 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.0 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.0 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |

最终引用：[]

最终片段正文：无

## A05-05：急着拿到包裹，快送收费多少？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2；Gold evidence=加急配送：1-2 个工作日送达，运费 15 元。同城配送：当日达或次日达，运费 10 元
- 归因：原始候选未召回。冻结有效Gold未进入Top5；不能归因为阈值过滤。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：根据2026-10-13人工讨论保留原始快送问法。必要事实同时包括加急配送1-2个工作日/15元，以及同城配送当日或次日/10元；它们是可能适用的两种快速方案，不假设所有用户满足同城条件。两事实均在同一个当前有效配送说明Chunk，保持唯一Gold Chunk。Retrieval层找到该Chunk即具备必要证据；后续生成应说明两方案和费用，生成完整性另行评测，本轮不评分。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.017407765752383342 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.015569978798845252 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 3 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.014747401914096292 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | -0.012012499748101257 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[]

最终片段正文：无

## A05-06：购物攒的分怎么折成钱用？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419；Gold evidence=100 积分 = 1 元
- 归因：原始候选未召回。冻结有效Gold未进入Top5；不能归因为阈值过滤。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/membership-faq 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.0309344107434516 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 2 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.01704985831736361 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 3 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.016329931273180054 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.01599232599314504 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.015851065842747425 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |

最终引用：[]

最终片段正文：无

## A05-07：软件一打开就闪退该怎么办？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3；Gold evidence=清除缓存后重启应用
- 归因：正确候选被分数过滤。Gold在raw rank=3，score=0.015113398518462828<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/technical-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.017407765752383342 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.015569978798845252 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 3 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.015113398518462828 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.0 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |

最终引用：[]

最终片段正文：无

## A05-08：保护账号可以启用什么二次确认？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d；Gold evidence=开启两步验证
- 归因：正确候选被分数过滤。Gold在raw rank=3，score=0.014322297262892025<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/account-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.027131273176132398 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.016012815367925648 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.014322297262892025 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.014026197842919252 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.011049892519794602 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[]

最终片段正文：无

## A05-09：生日那个月买东西积分享受什么待遇？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419；Gold evidence=生日当月消费可获得双倍积分
- 归因：正确候选被分数过滤。Gold在raw rank=1，score=0.1440164648759914<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/membership-faq 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.1440164648759914 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 2 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.038827025372645485 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 3 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.013333333799493752 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 4 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.01262892101115276 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 5 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |

最终引用：[]

最终片段正文：无

## A05-10：退款数额很大时还要谁同意？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864；Gold evidence=超过 500 元需人工审批
- 归因：正确候选被分数过滤。Gold在raw rank=1，score=0.15666989177144985<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/refund-policy 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.15666989177144985 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.015113398518462828 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 3 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.014747401914096292 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.0 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[]

最终片段正文：无

## A05-11：账户安全的密码长度至少是多少？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d；Gold evidence=密码长度至少 8 位
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/account-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.5012804124668988 | usable | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 2 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.04170691348340749 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.014953715054057404 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.013565636588066199 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 5 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |

最终引用：[{"reference": "doc_1348d91e6f873b93a77a#chunk-0~4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de", "content_hash": "4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de", "document_id": "doc_1348d91e6f873b93a77a", "chunk_index": 0, "source": "demo:cartcare-default/account-guide", "policy_version": null}]

最终片段正文：账户安全说明。建议用户定期修改密码，密码长度至少 8 位，包含字母和数字。如果忘记密码，可以通过绑定的手机号或邮箱重置。发现账户异常登录时，系统会自动锁定账户并发送通知。用户可以在安全设置中开启两步验证，提高账户安全性。不要将密码分享给他人，客服人员不会索要用户密码。

## A05-12：登录失败401和500服务器错误分别是什么原因？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3；Gold evidence=登录失败 401 错误：表示认证失败，请检查用户名密码是否正确，或尝试重置密码。页面加载慢：检查网络连接，尝试切换 WiFi 或移动数据。支付失败：确认银行卡余额充足，检查是否开启了网上支付功能。500 服务器错误：这是服务端问题
- 归因：正确候选被分数过滤。Gold在raw rank=1，score=0.16030179701521774<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：根据2026-10-13人工讨论保留Query、Gold Chunk和连续证据跨度。仅两个必要事实：401表示认证失败；500表示服务端问题。跨度中夹带的网络排查和支付描述不是本题要求的事实。两事实同属唯一Gold Chunk，本轮只评证据检索，不评分生成答案是否完整。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.16030179701521774 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.036927447607098984 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.022990024614754412 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.0 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[]

最终片段正文：无

## A05-13：会员等级中银卡和金卡的消费门槛分别是多少？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419；Gold evidence=银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/membership-faq 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.22850355248072407 | usable | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.026490648231984437 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.02473853573880813 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.011602053247714683 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.011221090690186175 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |

最终引用：[{"reference": "doc_15eee479ec6749cbefce#chunk-0~ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6", "content_hash": "ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6", "document_id": "doc_15eee479ec6749cbefce", "chunk_index": 0, "source": "demo:cartcare-default/membership-faq", "policy_version": null}]

最终片段正文：会员积分规则。每消费 1 元累积 1 积分。积分可以在下次购物时抵扣，100 积分 = 1 元。会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。积分有效期为 1 年，过期自动清零。生日当月消费可获得双倍积分。

## A05-14：配送说明中免运费的门槛是多少，不是退款审批金额？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2；Gold evidence=免运费（订单满 99 元）
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/shipping-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.3294345673889266 | usable | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.16378460812219942 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.017388018231870972 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.01103575366817433 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.0 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |

最终引用：[{"reference": "doc_2efff27478d4aa1b0a90#chunk-0~9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678", "content_hash": "9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678", "document_id": "doc_2efff27478d4aa1b0a90", "chunk_index": 0, "source": "demo:cartcare-default/shipping-guide", "policy_version": null}]

最终片段正文：配送服务说明。标准配送：3-5 个工作日送达，免运费（订单满 99 元）。加急配送：1-2 个工作日送达，运费 15 元。同城配送：当日达或次日达，运费 10 元。偏远地区可能需要额外 2-3 天。配送时间为每天 9:00-18:00，节假日可能延迟。如果需要修改收货地址，请在发货前联系客服。

## A05-15：订单查询中物流信息多久更新，而不是多久送达？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3；Gold evidence=物流信息通常在发货后 24 小时内更新
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/order-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.34154835536126926 | usable | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.05039526403759986 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.03529656096586897 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.01103575366817433 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.0 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[{"reference": "doc_b18d553a21972fe4b3f5#chunk-0~faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0", "content_hash": "faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0", "document_id": "doc_b18d553a21972fe4b3f5", "chunk_index": 0, "source": "demo:cartcare-default/order-guide", "policy_version": null}]

最终片段正文：订单查询指南。用户可以通过订单号查询订单状态。订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。物流信息通常在发货后 24 小时内更新。如果订单显示异常，请提供订单号联系客服处理。

## A05-16：退款政策是否意味着不用查实时订单就保证退款成功？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864；Gold evidence=退款请求是否可执行由实时订单事实和 PolicyEngine 决定
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/refund-policy 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.4677476696899203 | usable | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.1355638465785608 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 3 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.10782023910726524 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.022990024614754412 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.0 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[{"reference": "doc_dd816769efe7659f114e@refund-cancel-v1#chunk-0~a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90", "content_hash": "a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90", "document_id": "doc_dd816769efe7659f114e", "chunk_index": 0, "source": "demo:cartcare-default/refund-policy", "policy_version": "refund-cancel-v1"}]

最终片段正文：CartCare 模拟客服政策说明，仅用于演示。订单创建后 7 天内、订单状态符合要求时可以请求退款。退款金额不能超过订单总额；超过 500 元需人工审批。退款请求是否可执行由实时订单事实和 PolicyEngine 决定。此文档不代表真实商城承诺或支付渠道处理时效。

## A05-17：积分有效期是一年还是订单退款的七天？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419；Gold evidence=积分有效期为 1 年
- 归因：正确候选被分数过滤。Gold在raw rank=2，score=0.14940357414893368<0.20；有效性校验通过。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/membership-faq 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.17320508075688767 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.14940357414893368 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 3 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.13450690009441413 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.01347909660711244 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.01290994430109349 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[]

最终片段正文：无

## A05-18：已经发货超过七天没收到，订单查询指南建议做什么？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3；Gold evidence=联系客服申请查件
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:cartcare-default/order-guide 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.41626205575938746 | usable | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 2 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.15295176906298202 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 3 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.08819171206579968 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 4 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.017388018231870972 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 5 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.01103575366817433 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |

最终引用：[{"reference": "doc_b18d553a21972fe4b3f5#chunk-0~faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0", "content_hash": "faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0", "document_id": "doc_b18d553a21972fe4b3f5", "chunk_index": 0, "source": "demo:cartcare-default/order-guide", "policy_version": null}]

最终片段正文：订单查询指南。用户可以通过订单号查询订单状态。订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。物流信息通常在发货后 24 小时内更新。如果订单显示异常，请提供订单号联系客服处理。

## A05-19：退款政策规定退款到账需要几个工作日？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。退款正文明确不承诺支付渠道处理时效；无到账天数。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：退款正文明确不承诺支付渠道处理时效；无到账天数。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.42185656848285324 | usable | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 2 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.11437392783471767 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 3 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.08343983034805957 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 4 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.011528574334179087 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 5 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.0 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |

最终引用：[{"reference": "doc_dd816769efe7659f114e@refund-cancel-v1#chunk-0~a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90", "content_hash": "a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90", "document_id": "doc_dd816769efe7659f114e", "chunk_index": 0, "source": "demo:cartcare-default/refund-policy", "policy_version": "refund-cancel-v1"}]

最终片段正文：CartCare 模拟客服政策说明，仅用于演示。订单创建后 7 天内、订单状态符合要求时可以请求退款。退款金额不能超过订单总额；超过 500 元需人工审批。退款请求是否可执行由实时订单事实和 PolicyEngine 决定。此文档不代表真实商城承诺或支付渠道处理时效。

## A05-20：账户安全说明中客服可以替我关闭两步验证吗？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。仅说明开启两步验证，无客服关闭权限或流程。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：仅说明开启两步验证，无客服关闭权限或流程。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.37910329788719543 | usable | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |
| 2 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.09895414124595203 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 3 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.036560568396915905 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 4 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.033663272070558414 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 5 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.023204106495429366 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |

最终引用：[{"reference": "doc_1348d91e6f873b93a77a#chunk-0~4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de", "content_hash": "4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de", "document_id": "doc_1348d91e6f873b93a77a", "chunk_index": 0, "source": "demo:cartcare-default/account-guide", "policy_version": null}]

最终片段正文：账户安全说明。建议用户定期修改密码，密码长度至少 8 位，包含字母和数字。如果忘记密码，可以通过绑定的手机号或邮箱重置。发现账户异常登录时，系统会自动锁定账户并发送通知。用户可以在安全设置中开启两步验证，提高账户安全性。不要将密码分享给他人，客服人员不会索要用户密码。

## A05-21：订单查询：订单ORD-999今天到哪了？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。具体订单实时位置必须走Provider；演示指南只有查询方法。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：具体订单实时位置必须走Provider；演示指南只有查询方法。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.4593525962468248 | usable | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.11618950592042676 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.06028035544878474 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.05604198211223488 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 5 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.011308282771333777 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |

最终引用：[{"reference": "doc_b18d553a21972fe4b3f5#chunk-0~faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0", "content_hash": "faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0", "document_id": "doc_b18d553a21972fe4b3f5", "chunk_index": 0, "source": "demo:cartcare-default/order-guide", "policy_version": null}]

最终片段正文：订单查询指南。用户可以通过订单号查询订单状态。订单状态包括：待支付、已支付、已发货、运输中、已签收、已完成。如果订单显示已发货但超过 7 天未收到，可以联系客服申请查件。物流信息通常在发货后 24 小时内更新。如果订单显示异常，请提供订单号联系客服处理。

## A05-22：苹果手机电池的官方保修期是多少？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：通过。最终无证据；正确拒答。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料没有手机保修政策。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.08109589202262035 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.015430335626885783 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.01064794330689478 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.0 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.0 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |

最终引用：[]

最终片段正文：无

## A05-23：会员与积分：金卡会费每年多少钱？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。语料说明金卡消费门槛和折扣，没有会费。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：语料说明金卡消费门槛和折扣，没有会费。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.5082950476448747 | usable | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 2 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.027131273176132398 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 3 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.0 | low_confidence | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.0 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.0 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[{"reference": "doc_15eee479ec6749cbefce#chunk-0~ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6", "content_hash": "ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6", "document_id": "doc_15eee479ec6749cbefce", "chunk_index": 0, "source": "demo:cartcare-default/membership-faq", "policy_version": null}]

最终片段正文：会员积分规则。每消费 1 元累积 1 积分。积分可以在下次购物时抵扣，100 积分 = 1 元。会员等级分为：普通会员、银卡会员（累计消费 1000 元）、金卡会员（累计消费 5000 元）。银卡会员享受 95 折优惠，金卡会员享受 9 折优惠。积分有效期为 1 年，过期自动清零。生日当月消费可获得双倍积分。

## A05-24：隔离演示换货政策目前的换货期限是多少？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525；Gold evidence=换货期限为21天
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:a05-p1-isolated/exchange 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.7077252216167482 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.10596259292793764 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.0 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.0 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 5 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.0 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

## A05-25：现行隔离演示换货政策要求商品包装满足什么条件？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525；Gold evidence=换货商品必须保留完整包装
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:a05-p1-isolated/exchange 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.5628234135020641 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.11338934408459955 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_b18d553a21972fe4b3f5/None | 4a28204fe9202ea4e9c313412ec533f1da53a42ef4728afe8e7dd49addc52aa3 | 0.010673386003424046 | low_confidence | faae5da225a4662a81554146ba9b335c8d6b80220025f8e320706a2bc39a4ca0 |
| 4 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.00869400911593543 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 5 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.0 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

## A05-26：现行隔离演示换货政策每笔订单能换货几次？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=True；Gold Chunk=e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525；Gold evidence=每笔订单最多换货一次
- 归因：通过。冻结Gold在最终rank1。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：冻结语料 demo:a05-p1-isolated/exchange 的 chunk-0 直接支持该问；标签来自正文，不依赖检索输出。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.7390384934799793 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.10886621122138151 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.03756241189925624 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |
| 4 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.0 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.0 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

## A05-27：请仅根据demo-v1换货政策告诉我寄回地址。

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。 返回的是现行demo-v2换货片段，无该题所问事实；不是被排除版本泄漏。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.2713987798480071 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.09036961571588742 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.02411214217951385 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.02241679351129422 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.011547005767186147 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

## A05-28：请仅根据demo-v3换货政策告诉我指定承运人。

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。 返回的是现行demo-v2换货片段，无该题所问事实；不是被排除版本泄漏。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.26485808153278323 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.08819171206579968 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.02353104064391265 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.02187654980189302 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 5 | doc_1348d91e6f873b93a77a/None | 4d339c4fb426761092ee96eb40fad8a5555da0cb099e958de8257111f0e63f3d | 0.01126872345062735 | low_confidence | 4cbdb2edc53ea45c3cbb7c7b9955b8806174dadfb41ea646b390804141b440de |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

## A05-29：过期的隔离演示优惠券政策活动口令是什么？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。 返回的是现行demo-v2换货片段，无该题所问事实；不是被排除版本泄漏。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.3099193638432429 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.08164965841603611 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.012708214203857482 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.011814687039594762 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.009390602974814088 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。

## A05-30：撤销的隔离演示延保政策赠品是什么？

- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。
- answerable=False；Gold Chunk=None；Gold evidence=None
- 归因：无答案问题错误判为usable；片段事实不足。在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。 返回的是现行demo-v2换货片段，无该题所问事实；不是被排除版本泄漏。
- Gold/业务口径：未发现新标签冲突；沿用已批准冻结口径。
- annotation_reason：在固定时点有效且ready的语料中无所请求事实；禁止用相似主题或失效版本作为答案。

| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |
| --- | --- | --- | --- | --- | --- |
| 1 | eval-exchange/demo-v2 | e899e0c553a4a9210d55cc3da52404009fbbb664f0c2540999b936bdcb294525 | 0.339499668592955 | usable | 0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868 |
| 2 | doc_dd816769efe7659f114e/refund-cancel-v1 | 7fe603c19a8302870d453c48180ac963df4e4ad6d0b189d7a3aaff4d71562864 | 0.11925696469009273 | low_confidence | a7c085e8feea32a6903616d128d81ba791f26b4797a903296ae4f4ad11396f90 |
| 3 | doc_2efff27478d4aa1b0a90/None | df529ae0e9a9998cda16d9807afc4fb0a426c5a87135428becaea7e82158b2b2 | 0.013921151802570697 | low_confidence | 9ddc4fc42b97b59d13710c770db288e77378dea2eb767311f6cc440ed2434678 |
| 4 | doc_f4878e309f60ff328b5d/None | 830fe9c9a841076d87353846f412320957a1239645ce308039b9b0fbeba739d3 | 0.012942341790881828 | low_confidence | f60ada92831c5eb16025d315dc9d72a3df0680460d207b34993d521a1b78c938 |
| 5 | doc_15eee479ec6749cbefce/None | 9665d55df881fdb718bb4b909f03af9c8a3db971bfd375e25006e144c8e70419 | 0.0 | low_confidence | ee10d33cc7b96cbec8b35b9c7a4c9f0f86a88c78cec26738c252da4abf0cb1e6 |

最终引用：[{"reference": "eval-exchange@demo-v2#chunk-0~0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "content_hash": "0b1a2b2a84c96e92b515fb9a07229e6434d1be8520945b703bfdde4db586e868", "document_id": "eval-exchange", "chunk_index": 0, "source": "demo:a05-p1-isolated/exchange", "policy_version": "demo-v2"}]

最终片段正文：隔离评测虚构换货政策，不是商城承诺。换货期限为21天。换货商品必须保留完整包装。每笔订单最多换货一次。
