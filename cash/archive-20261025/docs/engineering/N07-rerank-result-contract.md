# N07 — Rerank 结果与检索状态契约

2026-10-12；起始 HEAD `1cc82bb182093b5fb5744b693af17bc034e382b9`，工作区干净。仅 N07，outcome=`fixed`，status=`verify`，待用户验收；N01/N02/N03/N04/N05/N06/N10 保留。

## 根因与红测

原审查 `rerank_probe` 使用 Fake SDK 返回合法 JSON `[]`，有两条有效知识候选、top_k=1，却得到 success=true / usable / reranked=true / hits=[] / citations=[]。本轮复用相同输入结构，通过真实 `_rerank` 解析器建立正式测试，没有运行会覆盖审查 JSON 的主入口。

修复前 **4 failed / 0 passed**：空排序伪 usable；候选数≤Top-K 未调用模型却 reranked=true；SDK 异常原始顺序 fallback 仍 reranked=true；正常空召回被判 success=false。新观察单独保存在 `N07-rerank-observations.json`，历史报告与审查证据不改。

## `[]` 的含义与异常策略

原提示词要求“按相关性降序排列的索引列表，从最相关到最不相关”，没有无相关证据的判定或拒绝阈值。Rerank 是排序器，不能把 `[]` 推断为模型已确认无答案。本轮明确完整排序契约：返回完整候选编号排列，每个编号恰好一次。

合法 JSON 只说明语法成立；类型、范围、完整性和唯一性也必须正确。非空候选的 `[]`、缺号、未知/负数编号、重复、null、bool、浮点、字符串、对象、非法 JSON 或附带额外文字均**整体拒绝**，不截取部分合法编号。解析严格要求完整 JSON；Markdown 围栏也属于不符合“只返回 JSON 数组”的输出。

| 情形 | 输出策略 | reranked / rerank_status |
| --- | --- | --- |
| 有效完整排序 | 按索引排序并取 Top-K，随后校验证据 | true / ranked |
| 候选数≤Top-K | 不调用模型，保留原顺序并校验 | false / not_needed |
| 未请求可选重排 | 普通 Tool 调用保留原路径 | false / not_requested |
| 非空候选却空排序或其他无效输出 | 原始顺序 Top-K fallback，然后校验 | false / invalid_output_fallback |
| SDK 服务失败 | 原始顺序 Top-K fallback，然后校验 | false / service_error_fallback |
| SDK 超时 | 取消 await，原始顺序 Top-K fallback，然后校验 | false / timeout_fallback |
| 没有可用召回候选 | 不调用重排，无 hits/citations | false / no_candidates |

重排 await 采用现有 knowledge_search 的 timeout_s（默认30秒）；没有新增服务、缓存系统或模型评测。取消本地 await 不代表远端服务必定取消或不收费，本轮只有 Fake SDK 超时验证。

## 三个字段不能互相替代

- `success`：本次检索是否按契约完成。正常无答案和低置信检索为 true，不等于知识命中成功。
- `retrieval_status`：最终可用证据情况。usable 必须有非空有效 hits/citations；正常无候选或复核后全部失效为 no_answer；只有低分/不可引用候选为 low_confidence；召回或最终证据校验不可用为 degraded、success=false。
- `reranked`：模型排序是否真实调用且返回有效完整排列。跳过和 fallback 为 false。模型排序成功后，如果 N06 复核将全部结果剔除，reranked 仍可 true，但 retrieval_status=no_answer。这记录已发生的重排，与最终是否有证据无关。

正常 no_answer/low_confidence 的 error/error_code 为 null，最终 hits/citations 都为空；不会把低置信候选当作可靠依据暴露。degraded 有固定错误码，不回传外部 SDK 异常文本。非法 Tool 参数仍沿用原验证失败语义，不是正常无答案。

`rerank_status` 是新增的可观察执行状态，传递到 ToolResult、Agent Tool payload、BaseAgent Trace 和管理员 `/search` 响应；不保存模型隐藏推理。普通缓存保存来源结果的重排状态，cached=true 表示本次使用缓存，不能据 reranked=true 推断本次又调用了模型。N06 的 KnowledgeBase 命中仍不缓存。

## 统一最终校验与 N06

实际路径仍为 `/chat → SingleSupportAgent → search_knowledge_base → search_with_rewrite → query rewrite / 并行召回 → 去重 → _rerank → _finalize_rag → Agent payload / Trace`。管理员 `/search` 使用同一检索结果。

`_rerank` 返回内部 RerankResult（items、reranked、status）。`_finalize_rag` 先用 RetrievalHit 校验每条输出，要求可用、非空内容、citation/content_hash 一致，且内容和来源必须完全对应原有候选；拒绝未知、篡改或伪造证据。去重后调用 N06 已有 `KnowledgeBase.validate_hits_async`，再校验返回结果、限制 Top-K，citations 仅从最终 hits 生成。直接 `call(..., rerank_top_k=...)` 的 KnowledgeBase 可选重排也复用该校验。

模型等待期间，同版本内容更新、废止或明确替代后，旧 chunk 不能通过排序或 fallback 重新进入 usable。全部已失效为正常 no_answer，复核服务异常为 degraded；部分仍有效则仅保留该部分。不重新写 N06 生命周期逻辑、不自动补入已被排序截掉的候选。

fallback 仅在排序器失败时合理：已有可靠候选，排序失败并不否定初检事实。但 fallback 不证明内容对查询充分相关，也不代表回答逐句正确。依赖失败产生的召回 fallback（即使看起来带有效 citation）不作为证据；从未通过 Contract 或已被 N06 退役的候选不回退。不能把所有空数组泛化为“原候选一定正确”：此策略只来自本项目的完整排序契约。

## 验证与兼容

正式命令均使用 `uv run python -m pytest -q -o cache_dir=.pytest-cache-n07`（后接相应测试文件），缓存 override 避免本机 cash 目录旧权限问题，不改 pytest 配置或依赖。

| 测试 | 结果 |
| --- | --- |
| tests/test_rerank_result_contract.py | 50 passed |
| tests/test_rag_contract.py + tests/test_tool_contract.py | 41 passed |
| tests/test_knowledge_version_consistency.py | 39 passed |
| N01/N02/N03/N04/N05/N10 六文件回归 | 134 passed |
| 完整 pytest | 356 passed / 3 skipped，既有 AnyIO 弃用警告 |
| uv lock --check / git diff --check | 53 packages / 通过 |

Fake SDK、Fake Chroma 覆盖空排序、正常排序、错误类型/编号、服务异常、超时、跳过、fallback、最终证据篡改、低置信/旧数据/失败召回、N06 更新/废止/替代、部分复核、Agent payload/Trace 和 API 投影。API 投影两项直接调用 handler，不声称是新的认证 HTTP E2E；原授权回归134项覆盖既有安全边界。

原 Tool 输入 schema、权限/风险/Policy/HITL、citation 和 content_hash 格式、状态枚举不变；新增 rerank_status，修正 reranked 含义。**语义变化**：no_answer/low_confidence 正常完成返回 success=true；调用方必须看 retrieval_status/hits/citations，不能再将 success 当作知识是否可用的判据。Agent 无证据分支仍传递澄清/人工核验 guidance、results=[]、citations=[]，knowledge_used 不会因此变成 true。

既有测试相应更新预期；N06 测试仅适配内部重排结果和正常无答案的 success 语义，知识发布代码不改。`evaluation/run_system_eval.py` 删除了只返回原序却伪装重排的测试 stub；该隔离组件每次至多一个候选，真实 `_rerank` 直接 not_needed，不调用模型。没有运行或覆盖历史评测报告。

## 剩余边界与独立练习

char-bigram embedding、0.35 阈值、Query Rewrite、PolicyEngine、Single-Agent 拓扑未改。对低相关候选的筛选能力、真实模型完整排列遵从率、fallback 的相关性收益/损失仍是 A05 实验假设；本轮不声称召回质量提升或生产指标。未运行真实模型、live Redis/Chroma 或收费评测；完整测试3项 live-service opt-in 跳过。N06 非事务、多进程发布和旧格式迁移限制继续有效。

独立练习：不使用 Codex，运行 `uv run python -m pytest -q -o cache_dir=.pytest-cache-n07 tests/test_rerank_result_contract.py`。把 FakeMessages 输出依次改成 `[1,0]`、`[]`、`[0,0]`，核对排序、fallback、reranked 和 rerank_status；在 SDK 返回之前废止候选，独立证明即使 fallback 保留原顺序也必须 no_answer、无旧引用。说明为什么模型排序成功但版本复核后无证据时可以同时 reranked=true 和 retrieval_status=no_answer。

建议提交：`fix(rag): align rerank outcomes with validated evidence`。未提交、推送；停止等待验收。
