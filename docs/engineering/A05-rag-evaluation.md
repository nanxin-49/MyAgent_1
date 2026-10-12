# A05-P1 — 冻结 RAG 评测集与 Lexical Baseline

2026-10-12。起始 HEAD `34f4cce19a77b4b08987af47c0e65cddca3750cd`，工作区干净。本轮仅 A05-P1；结果 `implemented`，建议 `verify`，待用户验收。整个 A05/EXPERIMENT 为 `partial`，A05-P2 未执行。没有提交、推送、下载模型或调用收费 API。

## 交付与边界

- `evaluation/rag_quality/corpus_v1.json`：冻结演示语料及来源。
- `evaluation/rag_quality/dataset_v1.json`：30 条 query、人工可审查的证据标签、有效期/退役说明。
- `evaluation/rag_quality/freeze_v1.json`：在任何检索运行前生成的文件 SHA256。
- `evaluation/rag_quality/run_baseline.py`：独立 retrieval runner，复用 `KnowledgeBase`、Tool 执行器、N07 `_finalize_rag` 和既有 `evaluation.system_eval.rate`；不另建 Agent 评测系统。
- `evaluation/reports/rag_quality/20261012T073909Z-a7bd452b/`：成功运行的 manifest、冻结输入副本、chunks、60 条观察、两轮汇总和逐题 Markdown 表。
- `evaluation/reports/rag_quality/20261012T073829Z-3b3ccf32/`：代理连接失败的尝试，manifest=blocked，观察为空；不能算作质量测量。
- `tests/test_rag_quality_baseline.py`：标签、指标、重复发布和 N06/N07 回归。

生产调用链仍为 `/chat → SingleSupportAgent → search_knowledge_base → MCPToolManager.search_with_rewrite → Rewrite/召回/Rerank → N07 最终证据校验 → N06 版本复核 → Agent/Trace`。B0 评测链为冻结文件 → **随机隔离 Chroma HTTP collection** → 同一个 `KnowledgeBase.search_handler` / `MCPToolManager.call` → 阈值筛选 → 同一个 `_finalize_rag` / `validate_hits_async` → 离线指标。评测代码显式绕开 Rewrite/Rerank，不伪装为完整生产配置。NoModel 哨兵一旦被调用会记录并阻止 B0 成功；它不产生任何人工排序结果。

没有改动生产 Embedding、0.35 阈值、N06 发布生命周期、N07 重排契约、PolicyEngine、Single Agent、Action/Handoff/Memory 或历史 T09–T12。N01/N02/N03/N04/N05/N06/N07/N10 和 A02 原修复均保留。README 和核心 Wiki 的生产架构描述无需因评测工具改变；仅 Workbench/progress 更新本轮状态。旧报告只有单题 FAQ HTTP 验证或 component replay，不能据此声称已有 30 题 RAG 基线；新证据单独保存。

## Gold 来源与冻结过程

先读取已有默认知识、T09/system RAG 评测及 FAQ HTTP 报告。6 篇默认文档来自当前 `mcp/knowledge_base.py::_load_default_docs`，正文、来源、类型和退款版本原样冻结；来源 hash 和 HEAD 记录在 corpus。corpus 的 `source_sha256` 是 Python `read_text` 统一 CRLF 为 LF 后的 UTF-8 文本摘要（`871d92da48cb34258848f030904a1b0b565adc7d209db4c038402fe7e815ccf0`）；manifest 中的 implementation hash 则基于原文件字节（`4a0b8518ce3749a97a49a287044af3ce8cb9cd54ad3b96872773ae8e8aa7883d`），二者口径不同。它们是项目演示材料，并非真实商城权威政策；本轮只测系统对已给定演示资料的检索能力。

默认语料没有足够的显式 supersedes/过期/撤销对照，故补充 **5 篇仅限评测的虚构政策版本**：换货 demo-v1/v2/v3、过期优惠券和撤销延保。所有来源以 `demo:a05-p1-isolated/` 开头，正文注明虚构/隔离；没有写入默认业务集合，也没有修改正常退款规则。换货文档故意与原退款主题相近，支持跨主题混淆观察。

标注按语料正文和固定有效时点编写，**在执行检索前冻结**，不是把当前返回文档当 Gold。每条有 case_id/query/answerable/category、document/chunk ID、policy_version、gold_evidence、位置和理由；无答案的正向 Gold 字段为 null，生命周期无答案另有 excluded_evidence。Gold 是本轮作者制作的可审查标签，**未宣称已有独立人工标注员验收**，等待用户复核。

问题不只包含标题复述：例如“把钱退回来”“登录口令”“攒的分折成钱”故意减少表面字符重合；相似主题题区分退款金额、配送门槛、积分期限、订单实时状态。无答案包含主题相关但正文没有的信息，防止只用离题问题高估拒答能力。生命周期题请求失效版本独有的事实；即使历史物理片段仍存在，在本评测定义的“当前有效已发布知识”范围内也无答案。若未来要测历史政策查询，应另建明确允许历史资料的实验，不能悄悄改本版标签。

| 分层 | 数量 | 有答案 | 无答案 |
| --- | ---: | ---: | ---: |
| 同义改写 paraphrase | 10 | 10 | 0 |
| 歧义/跨主题 ambiguity | 8 | 8 | 0 |
| 无答案/范围外 no_answer | 5 | 0 | 5 |
| 版本/有效期/退役 lifecycle | 7 | 3 | 4 |
| 合计 | 30 | 21 | 9 |

没有调整建议的分层数量；“无答案 5 条”是分层计数，指标实际无答案分母 **9**，包括生命周期的 4 条。每个有答案问题恰有 1 个 Gold chunk；可直接在 frozen chunks.json 和 corpus 中定位。401/500 双问题的完整正文证据跨越两项说明，但仍在同一 chunk 内。测试校验正向 Gold 当前有效、文本存在、ID/version 一致，反向排除证据必须存在但失效。测试不能自动证明语言标注完全正确，仍需人工审查。

冻结 corpus SHA256：`f1ca8679113529a54c6cb229f29b669e8e385509e9a08ad6aac8cb8d9d1e6b39`。

冻结 dataset SHA256：`e9442c1d8dc6b67784296c94f4ba49619991d7aeb6c0216ff51cd1253413c028`。

后续修订须创建新版本与新的 freeze 文件，说明原因；不得用本次排序反向修改 v1 Gold 以提高指标。

## 固定配置与可复现操作

| 项目 | 本次值 |
| --- | --- |
| HEAD | `34f4cce19a77b4b08987af47c0e65cddca3750cd`，未提交评测文件另有 implementation hashes |
| 运行时间 | 2026-10-12 15:39:09–15:39:13 Asia/Shanghai；manifest 同时保存 UTC |
| 系统/环境 | Windows 11；Python 3.12.3；uv 0.12.19；uv.lock 53 packages |
| 依赖 | chromadb-client/server 0.5.23，pydantic 2.10.3，anthropic 0.40.0，httpx 0.28.1，pytest 8.3.4 |
| Corpus / Dataset | a05-corpus-v1 / a05-dataset-v1 |
| 知识数量 | 11 篇 document/version、11 个物理 chunk、11 个 ready 发布记录；固定时点仅 7 个有效 chunk |
| Chunk | 生产 `_chunk_text`，500 字符目标、无 overlap；短文整段；长文按中文句号/换行贪心拼接，单个超长句可能超过 500；本版全部为短文 |
| Embedding | char-bigram-1024-v1；1024 维；小写+保留字母数字；字符 bigram 频次；SHA256 signed hashing；L2 归一化；文档标题额外 6 倍特征 |
| 检索 | Top-K=5，cosine distance，score=1-distance，min_score=0.35，不是概率 |
| 有效时点 | 固定 2026-10-12T00:00:00Z（北京时间08:00）；只在独立评测进程 patch KnowledgeBase 的 datetime，不改生产代码/系统时间 |
| 生命周期 | demo-v1 被 demo-v2 替代；demo-v3 在11月才生效；优惠券9月已过期；延保已 revoked；默认退款版本9月30日起有效 |
| Rewrite / Rerank / Cache | 全部关闭；不调用 SDK；没有真实模型或固定替身排序 |
| Backend | 真实 Chroma HTTP `127.0.0.1:8001`，非 Fake；随机专用集合，create-only，seed_defaults=false；结束删除 |
| 调用 | 每轮每题1次 Tool handler、1次实际 vector query；两轮共60次；另有 N06 HTTP 快照和最终复核 |
| 模型/费用 | 模型调用0、模型Token 0、模型API成本USD 0；不估计本机计算/电力成本 |
| B-prod | 未执行，收费模型未获授权；不读取凭据、不把 Fake SDK 重排当质量结果 |

运行：

```powershell
uv run python -m evaluation.rag_quality.run_baseline --host 127.0.0.1 --port 8001 --repeats 2
```

若本地运行环境有代理，可仅在该 PowerShell 进程设置 `$env:NO_PROXY='127.0.0.1,localhost'` 后再运行。本轮普通沙箱首次创建报告目录被 Windows 权限阻止，没有集合或报告；获准的执行环境首次又经代理返回 `502 /api/v2/auth/identity`，产生上述 blocked run。仅对本进程绕过本机地址代理后真实测量成功。日志还出现已知 posthog `capture()` 参数不兼容 telemetry 告警；检索和断言成功，不把该告警当作质量结果。

重复导入完全相同 corpus 后，snapshot 的所有正文、metadata、发布记录、chunk IDs 必须一致；检索前对 N06 eligible IDs 与独立语料生命周期标签做集合比较，检索后检查 snapshot 未变。两轮排序、原始分数、状态、引用一致；不将重复调用当60个独立问题。随机 collection 每次新建，拒绝采用已存在集合；cleanup 只删除自己成功创建的集合。无法连接时明确 blocked，不回退嵌入式 Chroma/Fake。

## 指标定义与结果

主要指标根据最终 `retrieval_status`、hits、citations 计算，而非 success。raw candidates 只作诊断。正确 chunk 必须精确匹配冻结 document/version/source/index/content/hash 与派生 chunk_id，不能把同主题任意片段当正确。

- **Recall@K**：21条有答案题中，最终前K个 usable hits 含Gold的题数/21。每题只有一个Gold，因此与Hit@K相同；不是多证据覆盖率。无答案不进分母；失败有答案题仍按未命中计入。
- **MRR**：对21题累加 `1/最终Gold排名` 后除21；缺失为0；仅测到Top5，是截断MRR。
- **无答案误报率**：9条无答案题中，最终 usable 且非空 hits/citations 的题数/9。degraded单独报状态，不当成正确拒答；本次无degraded。
- **Citation evidence precision**：引用中明确支持该题Gold事实的数量/全部最终引用数，包含无答案题的错误引用。技术上引用真实存在不代表它回答了所问事实；这里只测标注证据相关性。
- **P50/P95**：每题墙钟耗时，含Tool执行、Embedding、Chroma HTTP候选/快照、最终N06/N07复核，不含启动/导入；排序后在 `(n-1)*q` 处线性插值。每轮30条，第一轮含冷读；小本地语料，不是生产并发或模型延迟。
- **每题调用**：raw.attempts记录handler尝试数；包装真实collection.query计数，不以success推测vector query数。模型API未触发，Token和成本为0。

| 指标 | 第一轮 | 第二轮 |
| --- | ---: | ---: |
| Recall@1 | 6/21 = 28.57% | 6/21 = 28.57% |
| Recall@3 | 6/21 = 28.57% | 6/21 = 28.57% |
| Recall@5 | 6/21 = 28.57% | 6/21 = 28.57% |
| MRR | 6/21 = 0.2857 | 0.2857 |
| 无答案误报率 | 4/9 = 44.44% | 4/9 = 44.44% |
| Citation evidence precision | 6/10 = 60% | 6/10 = 60% |
| P50 / P95 | 27.20 / 35.69 ms | 28.45 / 38.83 ms |
| 检索 / vector query | 30 / 30 | 30 / 30 |
| 模型调用 / Token / USD | 0 / 0 / 0 | 0 / 0 / 0 |

原始候选中的Gold Recall@5为 **18/21**，它包含低分候选，不能替代最终可用证据的6/21。21条正向题中3条未进入候选Top5，12条进入候选却低于阈值，6条可用且都排第一，因此三个Recall和MRR相等。每轮10条usable、20条low_confidence，无no_answer/degraded；无答案也可能有相似的低分候选，所以不要求其状态字面为no_answer才算未误报。

分层结果：同义改写0/10有答案题命中；歧义3/8命中；当前有效合成换货3/3命中；普通无答案4/5误报；生命周期无答案0/4误报。合成换货贡献3个正向成功，不能泛化为真实退款检索质量。样本小且由作者设计，没有统计显著提升结论，也没有人口分布/生产流量代表性。

## 代表性 Bad Case

共有15条有答案题未得到可用Gold、4条无答案误报，实际失败19条，不编造不足的案例。下表分数来自第一轮真实HTTP返回。

| Case | 实际观察 | 含义与下一阶段假设 |
| --- | --- | --- |
| A05-01 把钱退回来，多久内申请 | 退款Gold未入Top5，错误主题账户安全排第一，score=0.025049，最终low_confidence | 口语与“退款政策”字符重合少；需要对照语义向量对同义改写的召回，不能靠改写标签修补 |
| A05-02 登录口令找回 | 正确账户文档候选第1，score=0.149071，低于0.35，无引用 | 召回方向正确仍未跨阈值；语义模型分数尺度需单独校准 |
| A05-09 生日积分待遇 | 正确会员文档候选第1，score=0.144016，最终low_confidence | 标题特征与长正文可能稀释具体事实；这是待对照假设，不能从一次输出断言唯一原因 |
| A05-14 免运费门槛而非退款审批 | 配送Gold候选第1，score=0.329435，仍低于阈值；退款主题也被召回 | 复合/否定问法与主题词并存；阈值与召回必须分别分析 |
| A05-19 退款到账几天 | 退款文档score=0.421857，usable；正文明确不承诺渠道时效，无到账天数 | 高主题相似度不等于答案存在；语义检索也可能保留该问题，需未来证据充分性评测 |
| A05-20 客服关闭两步验证 | 账户文档score=0.379103，usable；只写开启，没有关闭权限 | 操作词差异和权限事实不可用主题相似度替代 |
| A05-21 ORD-999今天到哪 | 订单指南score=0.459353，usable；指南无该订单的实时位置 | Knowledge检索范围与Provider动态事实须区分；本轮未测Agent是否正确选择Provider |
| A05-23 金卡年费 | 会员文档score=0.508295，usable；正文只有消费门槛/折扣 | 同主题未知属性误报；Rerank仅排序也不自动提供拒答能力 |

char-bigram优点：无模型下载/费用、确定性、来源可解释、导入查询同版本、易重复；标题和原词重合较强时有效。局限：不理解同义/否定/具体属性，1024维哈希有碰撞可能，标题boost影响短查询，cosine不是证据充分性的概率。Top-K增加可能提高候选覆盖但同时引入噪声；本次不改Top-K。阈值可抑制不相关候选，也造成12条Gold低分丢弃；仅下调阈值不能被解释成整体质量改善，因为还要观察无答案误报和引用精度。Knowledge版本决定能进入候选的内容，Embedding不能挽救已经失效的证据。

检索指标不能决定回答质量：Gold出现也可能被模型忽略、数值被改写、无证据承诺被添入；错误主题可引用也可能被Agent识别并拒答。Citation precision不是生成答案事实正确率。本轮没有生成回答、Agent Task Success、Policy/HITL成功率或真实模型效果，不能声称完整Agent任务成功。

## 验证与验收映射

| 命令/范围 | 实际结果 |
| --- | --- |
| `uv run python -m pytest -q -o cache_dir=.pytest-cache-a05 tests/test_rag_quality_baseline.py` | 初次20 passed，使用Fake只测contract/metric，不作为质量测量 |
| 同命令，追加 N06/N07/RAG HTTP/Tool/Business 6份测试文件 | 157 passed / 2 skipped（HTTP opt-in）；后续证据断言加强见最终validation.json |
| `uv run python -m pytest -q` | 402 passed / 3 skipped / 1既有AnyIO DeprecationWarning；最终复跑记录另见validation.json |
| 进程环境设置 `CARTCARE_RUN_CHROMA_HTTP_TEST=1, CHROMA_HOST=127.0.0.1, CHROMA_PORT=8001` 后，专项执行 `tests/test_rag_http_integration.py` | 2 passed；随机集合已清理 |
| `uv lock --check` | 53 packages，通过 |
| `git diff --check` | 通过；最终文档更新后复核 |

完整pytest默认跳过2条Chroma HTTP与1条live Memory。2条HTTP已另行真实执行；live Redis/Chroma Memory、收费模型、真实/chat模型E2E、负载/部署未运行。B0本身使用真实HTTP而非Fake。

DoD映射：30题结构/唯一ID/完整标签、Gold文本与有效chunk定位 → 专项测试；Recall/MRR/无答案分母 → 手算算例；N06/旧格式排除、N07空/低分/版本变化 → 专项与原回归；重复版本不改正文/不增加chunk → snapshot相等及真实两次发布；逐题状态/原始候选/引用/失败理由 → observations.json；环境/数据hash/模型开关 → manifest；Bad Case和下一阶段 → 本文。本轮P1可验收；整个A05必须保持partial，未满足B0+B1对照的experiment_complete。

本轮没有发现需要立即修改的额外代码缺陷；观测到的是冻结条件下lexical质量不足和主题相关无答案误报，留作P2实验，不改生产阈值/配置。N06单发布者与非事务边界、N07排序不能证明证据充分性继续有效。

## A05-P2 实验建议（仅候选，不执行）

候选为支持中文的 [multilingual-e5-small 作者模型卡](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md) 和 [bge-small-zh-v1.5 作者模型卡](https://huggingface.co/BAAI/bge-small-zh-v1.5)。本轮只阅读模型卡，未下载权重、安装或调用模型；当前大小、固定revision和最低硬件要求未核定。P2先核验并锁定revision、权重hash、许可证、query前缀与归一化方法，再决定选型。环境预计需要独立受控Python3.12环境及对应torch/transformers/sentence-transformers，CPU内存/磁盘预算和可能的GPU资源需实测，不能把未经核定的资源猜测作为承诺。收费Embedding和Rerank仅列为有预算后的替代，不提供虚构价格。

保持本版语料、chunk、有效时点和Gold；语义维度通常不同，必须另建隔离collection。先B1 retrieval only，再单独评B-prod或语义+真实rerank，不混合实验组。0.35是lexical基线阈值，不可直接解释为语义模型同等置信度：先保留同阈值的明确诊断组，阈值优化应使用另设开发集，不能用这30题测试集调参后宣称泛化改善。若要研究chunk大小，另开受控实验、提供新chunk标签映射，不能同时改chunk和embedding而归因于语义模型。

重点看同义0/10是否改善，以及4/9无答案误报是否恶化；同时记录候选与最终Recall、MRR、引用精度、真实Token/成本、端到端延迟。生命周期过滤必须保持。数据集应先由用户审核，未来扩充要按新版本保存，不能挑选易命中题。是否值得替换生产Embedding，应由质量、延迟、资源和证据不足处理的综合结果决定。

## 独立练习

不使用Codex，打开本次 `observations.json`，仅取 `repeat=1`：对21条 `answerable=true` 的行计算 `gold_rank<=K` 的数量；缺失排名按0计算，累加 `1/gold_rank` 后除21，独立验证Recall@1/3/5=6/21和MRR=6/21。然后在9条无答案中数 `false_positive=true` 得4/9。

再选A05-02与A05-19，查看候选score与固定0.35：解释为何前者Gold排第1却无可用引用，后者无Gold却usable。最后对10个引用逐条比较Gold事实，验证只有6个支持所问内容。不要把候选18/21或success=true当可用证据Recall，也不要调整标签或阈值。

建议提交信息：`eval(rag): freeze A05-P1 corpus and measure lexical baseline`。完成后停止等待验收，不开始P2。
