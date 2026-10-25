# A05-ANS24-ROUTE — fixed / verify

2026-10-14，HEAD `1fd93b5a4372dccb03e9bb8ad0f8647358b28fad`。本轮仅修显式人工交接误触发，等待人工验收。已有未提交Workbench/progress和前轮Gold审核材料保留。

## 最小修改与实际路径

生产代码只改 `core/handoff.py:explicit_handoff`，22行新增/2行删除；[最小diff](minimal.diff)。先定位原有请求短语，再用该短语前后的句式区分：既有记录/已完成状态询问、术语含义/规则解释、引用记录的文字，不作为新的创建请求。保留原否定过滤、分句规则和请求短语范围；没有硬编码复现整句，也没有问号一刀切。

SingleSupportAgent确定性门与HandoffService explicit_request校验继续复用同一函数，既有调用链不变。AST逐节点比较证明core/handoff.py除了explicit_handoff以外完全不变，HandoffService、allowed_reason、身份/客户归属、scope/fingerprint/幂等、合法审批、其他交接理由及回执代码原样。

修复前：规则问句内的“转人工客服”被当作主动请求→确定性门→Service→新模拟记录，SDK不调用。

修复后：只读问句不通过显式门→恢复既有Single模型答复路径；若模型仍请求request_handoff/explicit_request，Service再判定并拒绝，records和attempts均不新增。明确主动请求仍走原门，疑问式“可以帮我转人工客服吗/是否能帮我转人工客服”仍合法。

测试仅Fake SDK/注入TestClient，无lifespan和网络API启动、真实模型或外部交接。不是现实真人服务验收。

## 修复前后状态

|输入|修复前新记录|修复后新记录|Fake SDK调用前→后|
|---|---|---|---|
|模拟记录成功是否说明已转人工客服？|1|0|0→1|
|请帮我转人工客服。|1|1|0→0|
|我不需要人工客服，请说明模拟交接记录是什么意思。|0|0|1→1|

完整before.json/after.json保存Query、匹配分支、body、Trace、不可变Fake SDK请求、business/action/handoff/memory前后状态；comparison.json保存逐题差异。三个场景business均未改变、action记录未增加；Memory仍为隔离/chat的正常两条写入。SDK 0→1是错误绕过后恢复原有答复步骤，没有新增分类器、判断模型或生产SDK调用代码。本轮真实模型调用为0。

## 红绿测试

新文件tests/test_handoff_explicit_request.py共28项参数化/集成测试：主动请求、疑问式主动请求、规则/意义/状态问句、引用术语与记录、否定、混合先问后请求、中英文基本句式、普通订单/退款问句、模型尝试绕过服务门、合法请求幂等及owner隔离。

- 首次修复前红测：13 failed / 11 passed，red.txt保留原始失败。
- 扩充同类引号解释场景后：2 failed / 24 passed，quoted_red.txt；扩充状态问句和合法疑问式主动请求后：1 failed / 27 passed，status_question_red.txt。均先观察失败再作对应最小修复。
- 交接专项：`uv run python -m pytest -q tests/test_handoff_explicit_request.py tests/test_handoff.py` →54 passed / 1既有AnyIO警告，handoff_green.txt。
- 关联：新增交接、既有交接、Single生产接线、BusinessTools、ActionService、PolicyEngine、RAG契约、Answerability、Skills、ToolContract →192 passed / 1警告，related.txt。
- 完整：`uv run python -m pytest -q` →541 passed / 3 skipped / 1警告，full.txt。skip为Memory live和2条Chroma HTTP，未启动服务来补跑。
- `uv lock --check`：53 packages；`git diff --check`：通过。Git LF/CRLF提示不是空白检查失败。

预期安全断言明确检查record/attempt计数、handoff_created/escalated及Trace，不以回复关键词判建单。原合法请求/并发/审批、幂等、失败重放、客户归属测试均继续通过。没有扩大评测框架或新增模型依赖。

## 接受标准与保护范围

已满足本轮DoD：既有误建单红测成立；共享判定最小修复；正反例及主动疑问请求通过；错误模型显式工具请求被Service拒绝；普通订单、退款、知识问答关联及完整回归通过；本项fixed/verify。

所有RAG/Gold/Embedding/.35/六篇批准正文/Provider/Policy/ActionService/Single Agent/Skills源码保持。保护manifest包括当前tracked文件及前轮尚未跟踪的审核材料，后续validation.json列出核验与允许变更。历史review_20261014的两失败探针原样保留；其中ROUTE断言现已修复，REPLY断言仍对应独立待办，不改历史报告来伪造当时结果。

## 剩余风险与文档

这是有限的确定性句式门，不是完整自然语言意图理解。新语言、复杂转述、同一分句中的多个请求或特殊语序仍可能存在误拒/误触发；不宣称消除所有表达风险。没有真实模型遵循或真实/chat E2E证据。

A05-ANS24-REPLY继续独立todo/known_open：正确否定的真人/人工说明仍可能被Single文字保护删掉。agents/support_agent.py保持字节不变，本轮不修该行为，不推进E2E或下一任务。不删除已存在的误建模拟记录或引入状态迁移。

仅更新已有Workbench/progress的ROUTE状态及当前阻塞说明；README/两份核心Wiki的架构和职责仍准确，无需本轮修改。A05 doing/partial、Answerability verify/partial、E2E与B1/B1-PREP blocked、Gold人工pending及既有前两项verify均保持。

独立练习：不用Codex，运行新交接测试，比较“转人工客服成功了吗”和“可以帮我转人工客服吗”的prefix/suffix，再沿Single→Service说明为何不能由模型工具绕过；不要启动API或模型。

建议commit：`fix: prevent read-only handoff questions from creating records`。未提交或推送。
