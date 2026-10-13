# A05 DEFAULT-KB-PUBLICATION：本地内部维护发布记录

实际内部发布已执行，机械核验通过；阶段 **verify，等待用户验收**。A05 保持 **doing / partial**，B1 与 B1-PREP 保持 **blocked**。用户接受退款低置信结果作为本次内部发布限制，未接受业务服务或真实 /chat。API继续停止，没有启动B1、提交或推送。

## 授权与目标

本轮明确授权仅适用于本地 CartCare 演示默认集合，独立授权记录见 authorization.json。禁止 reset、阈值变化、批准正文/Metadata变化和外部生产发布。

实际目标：
- host=127.0.0.1，port=8001，TLS=false；
- tenant=default_tenant，database=default_database；
- collection=cartcare_demo_knowledge_chargram_v1；
- collection Metadata：dataset_kind=demo，description=CartCare demo RAG knowledge，embedding_version=char-bigram-1024-v1，hnsw:space=cosine。

不是按端口名称推定环境：核对 Docker Desktop endpoint `npipe:////./pipe/dockerDesktopLinuxEngine`，Chroma容器 echomind-chromadb / chromadb/chroma:0.5.23，Compose project=echomind、service=chromadb、working_dir及config_files指向当前 E:\AAA_NEED\Echomind_new\EchoMind。8001映射该容器8000，持久卷echomind_chromadb-data。当前六条旧正文/Metadata与既有历史快照完全相同、全部为已批准的demo身份。仓库.env使用APP_ENV=production、CHROMA_HOST=chromadb、CHROMA_PORT=8000；它是容器运行配置，未据此向外部生产环境执行操作，文件未修改。

当前 HEAD `414a101be9b193b4d49d9c8a823e3ba6f35de359`，本轮开始工作区干净。与隔离REPORT的起始HEAD不同，但发布源码、适配器、测试及审批资产逐字节匹配其 files_sha256.json；六个实际revision由已验收加载器重新核验一致。未自行提交该版本。

审批资产完整SHA256：`17e3c606365c203589919321b166e942e6aab569d539ce631f447a5439cd018d`。
审批记录SHA256：`cac087b27c7030c9d7e85a781f020084a1a1618fa8575c4d58c99a9af5a15f9f`。
六篇原文、显式document_id/source/doc_type/policy_version/effective_at/expires_at/publication_status/supersedes均保留。

## 停写检查

API容器原已Exited，本轮执行 `docker stop echomind-app` 确认并保持停止，未停止Chroma、Redis或无关程序。
维护前、备份后发布前、发布后分别保留maintenance_pre_backup.json、maintenance_pre_publish.json、maintenance_after_publish.json：
- echomind-app Running=false；无8000/8080监听；
- Windows无Python/uv API或知识发布者；无未解释的8001 Established连接；
- Ubuntu WSL=Stopped，未启动该发行版；
- 仅本项目Redis和Chroma容器运行；Chroma容器仅其服务进程；
- 本机Docker endpoint、端口映射、Compose目录及服务标签一致。

观测清单与发布前完整快照相等共同证明本窗口未发现并发写入。Chroma没有分布式维护锁，不能将此证据说成阻止未来任意外部客户端写入；API保持停止，任何后续写入仍须授权。

## 全量双份备份

发布前 before.json（38842 bytes）包含target、完整collection Metadata和全部6条ID/document/metadata/1024维embedding；独立before.json.sha256。
SHA256：`2dcb6589e29f01cf80d5e1f92aa2b81fa1c4485eb4f9433a7d11694558980b8d`。
第二副本及SHA位于：
`E:\AAA_NEED\Echomind_new\EchoMind\data\default-kb-backups\default-kb-internal-publication-20261013T081119Z\before.json`。

两份文件及哈希逐字节一致。不同目录、同E盘，满足本次第二份副本要求，但不是独立设备灾备。没有拿历史缺少向量的snapshot代替完整备份。备份后再次读取集合，以及发布前和实际seed CLI内的再次读取，均与完整before快照一致。前置身份/lifecycle检查没有未知记录、版本或正文漂移。

## 实际执行

严格调用已验收的seed CLI，调用日志包含参数、UTC时间、返回码、stdout和stderr：
1. `python -m mcp.seed_demo_knowledge --check-assets` → 0；
2. `python -m mcp.seed_demo_knowledge --backup <本轮before.json>` → 0；
3. 确认双份备份、再核对停写及当前完整快照；
4. `python -m mcp.seed_demo_knowledge --backup-file <同一before.json>` → 0，输出collection及chunks=6；
5. `python -m mcp.seed_demo_knowledge --verify` → 0，完整结果见command_verify.json；
6. 新建KnowledgeBase/Tool runtime再做N07复核及逐片段实际向量查询；
7. `python -m mcp.seed_demo_knowledge --backup <本轮after.json>` → 0，重读完整集合与after备份一致。

发布核验完成时间：**2026-10-13T08:22:32.658182Z / 北京时间16:22:32**。准确命令启动/完成记录见command_publish.json；不是以证据目录时间代替实际执行时间。只调用一次原位发布，未reset、重建集合或重复seed。

发布后after.json SHA256：`e8e6efa31e0b4288050f98b66cf4b0bda127ded2b6496e876d9faecbb53d63c9`，独立after.json.sha256。
before/after都是完整向量快照，不只是摘要。publication_verification.json记录逐题原始及最终候选、引用、阶段和逐片段向量查询。

## 机械验收结果

| 项目 | 实际结果 |
|---|---|
| ready publication | 6 |
| 有效Chunk | 6 |
| 物理记录 | 12（6 publication + 6 chunk） |
| 原6条旧格式ID | 全部精确移除 |
| 集合Metadata/target | 与预期及发布前一致 |
| 正文/Metadata/revision/content_hash/chunk_id | 与审批资产一致 |
| 向量 | publication和chunk均1024维、有限值 |
| 所有有效片段实际检索 | 6/6，自身文档向量检索rank1 |
| publication进入候选 | 0，where限定有效chunk ID |
| 默认seed与库内内容 | 一致，未重复写库证明 |
| 新建检索运行时 | 可用；无legacy knowledge错误 |
| N07 | 真Tool executor/finalizer及N06复核通过，引用与候选/hash一致 |

“重建运行时”指真实新建KnowledgeBase及MCPToolManager检索运行时，--verify另在新Python进程读取；没有启动FastAPI或真实/chat，不能冒充完整Agent E2E。真实HTTP 127.0.0.1:8001，非Fake/embedded存储；NoModel sentinel确保模型调用0，Rewrite/Rerank关闭，Top-K=5，阈值仍0.35。

## 独立业务检索结果

用例保持已验收的DEFAULT-KB-01~06新业务问法“请提供CartCare当前[文档标题]能力边界说明”，未使用A05冻结问题。

| 目标 | 实际目标分数 | N07最终状态 | 最终引用数 |
|---|---:|---|---:|
| 退款政策 | 0.339462175866 | low_confidence | 0 |
| 订单查询 | 0.401214114316 | usable | 1 |
| 账户安全 | 0.445521052464 | usable | 1 |
| 技术故障排查 | 0.447344688665 | usable | 1 |
| 会员与积分 | 0.513885971106 | usable | 1 |
| 配送说明 | 0.352265554949 | usable | 1 |

六个目标均进入raw候选，五个目标进入最终usable；全部实际分数保持原隔离结果。退款是正确候选被0.35过滤，最终无证据和引用；这是用户本次明确接受的内部发布限制，不是业务验收通过，也不是Gold问题或生产阈值优化。没有调参、重写正文或启动B1。该6例诊断不等价于A05 Recall/FPR/MRR或全业务正确率；检索通过也不能证明事实足以回答所有用户问题。

## 回滚与维护状态

rollback_record.json：required=false、executed=false。本次无写入/验证失败，未生成partial，未为了证明回滚而修改已通过的真实集合。独立隔离恢复测试已在上一轮通过，本轮不冒称再次完成真实库恢复演练。
原before及第二副本可供已授权维护恢复；当前after快照已保留。若后续发现异常，先保持API停止、导出partial并核查归属/目标，不跳过失败重启。
仅在需要并核验恢复决定后执行既有命令：
```powershell
$env:CHROMA_HOST='127.0.0.1'
$env:CHROMA_PORT='8001'
$env:NO_PROXY='127.0.0.1,localhost'
uv run python -m mcp.seed_demo_knowledge --backup <新的partial文件>
uv run python -m mcp.seed_demo_knowledge --restore <本轮before.json完整路径>
# 恢复后再次全量导出并与before规范快照/hash核对；任何异常保持维护。
```
不要字面运行带尖括号的占位符。before恢复的是旧格式数据及旧降级状态，不能据此恢复业务可用性。禁止以reset替代恢复；未知记录/目标或Metadata漂移必须先停下独立核查。

API未重启，保持维护；仅数据库内容与后续内部检索可用，未宣布对外服务或业务验收完成。

## 保护、验证与下一阶段

新改动仅本轮执行/证据文件、README当前状态、既有Workbench/progress。既有发布代码、PolicyEngine、Skills、.env、审批文件、阈值、冻结Gold/B0/B1数据和历史报告均未修改；delivery_validation.json对发布前全部tracked文件hash逐一比对，只允许三份文档变更，同时再次复读当前默认集合等于after快照。未提交推送。
本轮执行实际默认HTTP维护前置检查、完整备份及双份校验、机械核验、6个业务查询/N07引用核验、6个自身向量查询和最终状态复读。没有代码修复，未额外重跑完整pytest；已验收隔离阶段483 passed/1 skipped是历史回归证据，不记作本轮重跑。既有Chroma telemetry capture签名告警保留在stderr，不影响已确认的写入/读取结果。初次读进程/Docker被沙箱权限拒绝后采用获批只读权限；第一次新证据目录创建失败在任何备份/写库前，目录创建后正常继续，均未改变目标或跳过前置检查。

建议用户验收本轮实际内部发布证据后，单独推进：
1. Skills口径一致性：核对billing_support中的实付金额/部分退款人工审核/原路退回等，以及订阅、发票等未接入能力，最小修订并独立验证；本轮未修改。
2. Answerability：独立业务用例验证事实充分性、资格/费用边界、无依据拒答、模拟交接不等于真人接单。不得改A05冻结Gold或将相似度提高视作事实充分性改善。
3. 在一致性与Answerability门通过、具备明确模型/网络资源授权后，进行本机受限Principal及可观察的真实/chat E2E内部验证；保持实际API旧镜像停止，先核对实际运行代码版本，不能直接重启10月2日旧镜像并声称覆盖当前实现。
B1仍blocked，本轮不重复内存门或模型准备。A05仍doing/partial；DEFAULT-KB-PUBLICATION保持verify待本轮实际执行验收，不自动标done。
