# A05 DEFAULT-KB-PUBLICATION 发布实现准备

状态：**verify / implemented**，仅表示本轮隔离实现与机械验证完成。A05 仍 **doing / partial**；B1-PREP、B1 仍 **blocked**，本轮未重试 B1。实际默认集合没有读取、写入、重建或 reset。用户批准的是内容与 Metadata，正式发布仍须另行授权。

起始 HEAD：`d09a2dabdec19a7f30fd96afc2e288c607785980`，起始工作区干净；无提交或推送。Python 3.12 / pydantic 2.10.3 / chromadb-client 0.5.23；真实 HTTP 测试端点 127.0.0.1:8001。没有新增依赖、模型下载、付费模型调用。

## 唯一审批资产

完整六篇原文及所有显式 Metadata 存于 `mcp/knowledge_assets/default_business_v1.json`，未再改写业务措辞。外部校验字段不传入 KnowledgeDocument。
- 资产完整文件 SHA256：`17e3c606365c203589919321b166e942e6aab569d539ce631f447a5439cd018d`
- 独立审批记录：`mcp/knowledge_assets/default_business_v1.approval.json`
- 审批记录完整文件 SHA256：`cac087b27c7030c9d7e85a781f020084a1a1618fa8575c4d58c99a9af5a15f9f`
- 审批入档时间：2026-10-13T07:26:39Z（北京时间15:26:39），记录本轮收到明确批准的时间；不推定此前逐篇人工审核时间。
- source、doc_type、policy_version、effective_at、expires_at、publication_status、supersedes 均原样保留。退款 policy=refund-cancel-v1，effective_at=2026-09-30T00:00:00Z，expires_at=null；其余五篇 policy_version/effective_at/expires_at=null。全文及逐篇 content_hash 以该 JSON 为准。

| 文档 | 显式 document_id | 实际 publication revision，均与审批候选一致 |
|---|---|---|
| 退款政策 | `doc_8450205ee234ce108cbd` | `9c3ac875a00994ef876dcafeafa7369c7e4820586cf587271a7e95a206d9310f` |
| 订单查询 | `doc_ed1fae0ed79e04b2ee03` | `09d6c7f65a9498771ec0c484d2081edb9574f889376d3866c05ef55aa481ea62` |
| 账户安全 | `doc_9958ba736af96fca4e70` | `15f31f6f528980171726219e7aabcc646bf6ab9731269574a7dbebd635048547` |
| 技术故障排查 | `doc_cd81fe468580a43ee0bd` | `5b4e272453b82e4b1ede6fadef627be8916ef88da560c14d8faeeedc9dd06801` |
| 会员与积分 | `doc_4e9e6195c6f9e8cfe749` | `8e945e54cfc0b4b76944e04f6681dd1af622f6d06aeca47dd182161164b6351a` |
| 配送说明 | `doc_73ae51e45fb2abb8ce23` | `8593ba741e04a88774a211f48785227255a26a7511b3062444fe8c02e412908c` |

六篇分别367/284/235/311/220/316字符，当前切分函数每篇仅一个完整 Chunk，适用范围、规则、免责声明没有拆开。按实际 KnowledgeDocument.model_dump_json() 的 UTF-8 字节计算 revision；对应 content_hash、chunk_id 全部一致。文件、正文、Metadata、revision 或 chunk_id 不一致均拒绝，不自动修正。缺失资产或审批记录也直接失败，没有旧正文兜底。`.gitattributes` 对两个审批文件及本轮证据关闭换行转换，避免 Windows core.autocrlf=true 在新检出时改变冻结字节。

## 实现与执行路径

- `mcp/default_knowledge_asset.py`：唯一资产加载器，固定完整文件 SHA、校验人工批准记录、六文档身份、正文 hash、模型 revision 和 chunk ID。
- `mcp/knowledge_base.py`：删除六篇旧字面量；_load_default_docs、空库初始化、reset 均加载同一资产；启动默认种子前先核验资产；reset 在删除前核验资产，重建保留原集合 Metadata。
- `mcp/default_knowledge_publication.py`：限定已批准的文档/版本/来源/类型/生命周期；非空集合必须有完整有效且未变化备份；原位调用既有 add_documents。包含完整向量备份、目标绑定恢复及只读发布核验。
- `mcp/seed_demo_knowledge.py`：普通 seed 不再把非空旧库直接当作完成；增加 --check-assets、--backup、--backup-file、--restore、--verify。读操作/恢复/reset 只打开已存在目标，缺失时拒绝，不隐式创建。--reset 非空也须备份；正式方案不采用 reset。
- 新隔离 runner `evaluation/default_kb_publication.py`、14+1项新单元测试 `tests/test_default_knowledge_publication.py`。
- `tests/test_rag_gold_v2_candidate.py` 仅把已测知识源码的历史哈希断言指向本轮逐字节归档，不更改历史锁或期望 hash。
- README、既有 Workbench/progress 更新当前阶段和种子命令边界；其余 Wiki 无需重写。

之前：旧字面量初始化；普通 seed 在旧格式非空库直接退出；reset 可能恢复旧正文。
现在：审批校验 → 受控身份核验 → 完整备份/未变化校验 → 原有 publishing → chunk写入/精确旧记录删除 → ready → 独立验证。批次逐文档提交，失败期间保持停写和业务入口维护，不声称六篇事务原子提交。

AST 比对证明除 __init__、rebuild_demo_collection、_load_default_docs 外，KnowledgeBase 全部方法未变，包括 _publish、_eligible、search、validate_hits_async 和切分函数。N06/N07、publication、hash、生命周期、生产阈值0.35、词法1024维均保留。生产 Provider/PolicyEngine/Skills/Agent 查询调用路径未改。框架支持构造参数指定集合，但 api/main.py:136 实际初始化未提供配置切换入口；本轮不引入独立版本集合切换架构，采用停写原位发布。

## 隔离验证证据

最终 `http_evidence.json`：七个场景全部通过，耗时约21.16秒，每个随机 `cartcare_kbprep_<uuid>` 集合均先 create 并记录归属，再打开；finally 删除并确认同名集合不存在。不扫描、打开或修改默认及其他业务集合。
1. 空集合 → 6 ready publication + 6有效 Chunk，全部1024维。
2. 旧格式克隆 → 升级前搜索明确报 legacy knowledge requires reviewed republication；升级后旧6记录精确删除，12行完整，新6片段可检索。
3. chunk写入前失败 → 未完成发布的有效片段为0；记录 partial 新备份后同请求恢复。
4. 精确旧记录删除后回执失败 → 未完成发布的有效片段为0；恢复成功。
5. ready提交成功但回执丢失 → 服务端已有1个有效发布；未把旧记录当新证据，重试后六篇一致。
6. 第二篇 Chunk 写入失败 → 第一篇已提交，证明批次非原子；有效片段为1，重新备份当前 partial 状态后重试恢复。
7. reset 同一路径仅通过默认名绑定为随机测试集合的 subclass 执行，未执行生产 --reset；重建保留原 Metadata。

每场景均验证：hash/revision/chunk ID/正文与审批资产一致；每片段自身向量查询rank1；候选where只包含有效chunk ID，publication不入候选；退款在生效时间前剔除；重复发布整快照不变；备份恢复后 IDs/正文/全部 Metadata/向量/集合 Metadata/目标绑定的规范化 JSON 完全一致；再发布恢复正常。恢复旧格式时搜索仍明确降级。
旧格式克隆来自已保存的 `b0-calibrated-20261013/default_snapshot_formal.json`（SHA256 `500f8ffa736d7a6af42beb94595f9b243648d4b5d654ed016a87e292d5372305`），未重新访问当前默认库。克隆向量按同一词法算法重建；该文件没有原始向量，故本实验不证明克隆向量与真实默认库存储向量逐字节相同。后续正式备份必须读取实际全量向量。

保留首次引用断言错误、第二次 reset Metadata 恢复拒绝的失败证据及清理记录，后者经最小修复通过；之后的扩展记录也独立保留。故障注入包装真实 HTTP 集合，模拟客户端写入/回执失败，不等价于服务断电、跨进程并发或分布式事务测试。Chroma 客户端有既有 telemetry capture 签名告警，实际 HTTP 读写、核验和清理通过；未更改依赖绕过。

## 独立业务检索用例与未解决问题

六个新用例是“请提供CartCare当前[文档标题]能力边界说明”，独立 DEFAULT-KB-01~06；没有读取冻结问题进行本轮检索、没有开发校准或根据结果调参。使用真实工具执行和 N07 finalizer，关闭 Rewrite/Rerank/LLM，不使用冻结 Gold 评判它们。

| 用例 | 目标 | 目标原始分数 | 目标最终可用 |
|---|---|---:|---|
| DEFAULT-KB-01 | 退款政策 | 0.339462 | 否，low_confidence |
| DEFAULT-KB-02 | 订单查询 | 0.401214 | 是 |
| DEFAULT-KB-03 | 账户安全 | 0.445521 | 是 |
| DEFAULT-KB-04 | 技术故障排查 | 0.447345 | 是 |
| DEFAULT-KB-05 | 会员与积分 | 0.513886 | 是 |
| DEFAULT-KB-06 | 配送说明 | 0.352266 | 是 |

目标原始候选6/6，最终目标usable5/6；这是本组业务验收诊断，不是A05 Recall、FPR或全业务成功率。退款属于正确候选被分数过滤，不能通过改阈值、正文或开启B1掩盖。其余候选及最终引用完整记录于 evidence；可用引用与原候选、hash、N06复核一致。--verify 的退出0只代表机械条件通过，business_all_expected_usable=false必须单独处理；若要求六例均可用，业务验收仍未通过，不能自动恢复对外服务。

Answerability、实际业务授权/实付金额/币种校验不由本次检索发布实现。Skills 独立待办：billing_support/SKILL.md:46-53 对部分退款人工审核、实付金额、原路退回的指引仍与当前演示规则/能力边界不一致；订阅、发票、支付渠道等范围也不能因知识发布宣称已实现。未修改 Skills，在最终 /chat 验收前须另行授权处理。未运行真实模型 /chat，不能声称生成答案或人工交接已验收。

## 回归与保护

红测：唯一种子与审批内容相同的预期安全测试，旧实现1 failed；修复后green。
最终命令：进程内设置 NO_PROXY=127.0.0.1,localhost、CARTCARE_RUN_CHROMA_HTTP_TEST=1、CHROMA_HOST=127.0.0.1、CHROMA_PORT=8001；`uv run python -m pytest -q`。
结果：**483 passed / 1 skipped / 2 warnings，8.06s**；含既有两项真实随机HTTP集成。Memory live Redis/Chroma测试未启用而skip；AnyIO弃用及既有pytest缓存写入权限警告，不影响测试断言。完整日志摘要见 regression.txt。
`uv lock --check`：53 packages；`git diff --check`：通过。离线 preservation_validation.json：117个受保护tracked文件git diff为空，64个历史锁文件hash通过；旧知识源码原始SHA `4a0b8518ce3749a97a49a287044af3ce8cb9cd54ad3b96872773ae8e8aa7883d` 归档保留。冻结Gold、B0/B1材料、B1内存阻塞证据、历史报告和模型资源锁不变。新增文件hash清单见 files_sha256.json。

## 正式发布方案（本轮未执行）

前置审核必须先明确是否接受本轮退款检索限制；如不接受，独立跟踪改进并继续维持业务验收未通过，不在本轮改知识或阈值。内容批准、verify状态、下面命令都不构成正式写库授权。

1. 用户单独授权正式发布窗口、目标地址/tenant/database/确切默认集合、停写方法、备份位置及失败处理。记录完整工作区diff、版本和资产hash；确认仍与本证据相同。若默认库已变化、含新文档/版本或生命周期冲突，停止，不自动修正或reset。
2. 停止全部API worker、上传/发布入口、seed脚本、后台知识写入器及自动初始化；不只停一个终端。Chroma保持运行。停止前保存原启动命令、环境来源和只含白名单配置的快照，避免泄露密钥。
3. 备份包括目标host/port/TLS、tenant/database、集合名、完整集合Metadata及全部ID/document/metadata/embedding。JSON及独立SHA文件只创建不覆盖；保存第二份离线副本和独立hash记录，确认备份可读取及磁盘容量。不得以仅正文/metadata的历史snapshot替代。
4. 原位发布：先检查全体记录归属及生命周期；backup与当前完整快照不同立即停止；逐篇以批准的显式原document_id/version发布，精确删除同身份旧记录。任何异常立即保持维护。先备份partial状态再决定同请求恢复或回滚。
5. 停写状态下运行 --verify，把输出留档。必须核对6 ready publication、6有效Chunk、0遗留行、12物理行、1024维、六revision/hash/全文、候选与引用。每个有效片段实际检索；检查业务六例及已知退款低分，新的意外失败按回滚条件处理。
6. 服务恢复前保留旧备份、partial/ready备份、命令输出/hash及审核决定。清空旧进程RAG缓存的方法为重新启动原服务；不得更换阈值或打开B1。机械恢复与业务准入分开：Skills冲突未处理且最终/chat未通过时，保持维护或仅允许授权的内部验收；不称正式业务验收通过。

未来单独授权后的本机命令示例（先核实实际部署目标；以下示例端点来自本轮测试，正式地址须重新确认）：

```powershell
# 在 E:\AAA_NEED\Echomind_new\EchoMind 执行；先完成全部停写。
# 容器部署可 docker compose stop echomind；本机则在原API终端正常停止所有worker。
# 不停止Chroma、不结束无关程序。
$env:CHROMA_HOST = '127.0.0.1'
$env:CHROMA_PORT = '8001'
$env:NO_PROXY = '127.0.0.1,localhost'
$env:PYTHONIOENCODING = 'utf-8'
uv run python -m mcp.seed_demo_knowledge --check-assets
if ($LASTEXITCODE -ne 0) { throw 'Approval asset verification failed' }
$releaseDir = Join-Path (Get-Location) ('data/default-kb-release-' + (Get-Date -Format 'yyyyMMddTHHmmss'))
New-Item -ItemType Directory -Path $releaseDir -ErrorAction Stop | Out-Null
$backupFile = Join-Path $releaseDir 'before.json'
uv run python -m mcp.seed_demo_knowledge --backup $backupFile
if ($LASTEXITCODE -ne 0) { throw 'Full backup failed; keep service stopped' }
Get-FileHash -Algorithm SHA256 -LiteralPath $backupFile
# 人工检查完整备份与独立.sha256，保留第二份副本；确认目标和停写状态。
uv run python -m mcp.seed_demo_knowledge --backup-file $backupFile
if ($LASTEXITCODE -ne 0) { throw 'Publication failed; keep service stopped' }
uv run python -m mcp.seed_demo_knowledge --verify > (Join-Path $releaseDir 'verify.json')
if ($LASTEXITCODE -ne 0) { throw 'Mechanical verification failed; keep service stopped' }
# 必须检查 verify.json 的业务诊断，不能凭exit0恢复服务。
uv run python -m mcp.seed_demo_knowledge --backup (Join-Path $releaseDir 'ready.json')
# 仅在另行审核准入条件通过后，恢复原启动方式和原环境：
# 容器 docker compose start echomind；本机用此前记录的原启动命令。
```

失败处理：keep stopped；先留存失败快照，再在授权的维护窗口执行：
```powershell
uv run python -m mcp.seed_demo_knowledge --backup (Join-Path $releaseDir 'partial.json')
# 经核验及明确恢复决定后，同请求恢复（partial与当前库必须一致）：
uv run python -m mcp.seed_demo_knowledge --backup-file (Join-Path $releaseDir 'partial.json')
# 或回滚原始完整备份：
uv run python -m mcp.seed_demo_knowledge --restore $backupFile
if ($LASTEXITCODE -ne 0) { throw 'Restore failed; keep service stopped' }
# 重新导出 recovered.json，与原 before.json 的完整快照校验一致。
uv run python -m mcp.seed_demo_knowledge --backup (Join-Path $releaseDir 'recovered.json')
```

partial/ready等文件名已存在时禁止覆盖，换新的窗口记录名。若存在未知记录，工具会停止；先独立核查，不直接删除它们。若集合缺失或Metadata改变，restore也拒绝，须独立人工灾难恢复方案，不能随意重建同名集合。恢复旧格式数据后RAG依然降级，须保持服务关闭或知识功能不可用；不能用旧正文绕过publication校验。

风险及回滚触发：未确认停写/并发写入、快照变化、文件/hash不一致、目标不匹配、未知版本、发布未ready、有效片段/hash/引用异常、遗留行未清、实际业务验收发生未获接受的失败。Chroma无批次事务/跨进程CAS，单进程RLock不能替代维护窗口；服务断电、多worker竞争、服务器灾难恢复未在本轮验证。不得使用生产 --reset 代替安全升级。

独立练习：不启动Codex，运行离线 --check-assets 和 validate_preparation.py；在临时文件副本改一个正文字符，证明加载器拒绝而不改审批文件，再运行新增单元测试。若要运行HTTP练习，仅使用本轮随机集合runner，不运行默认seed。

建议提交消息（仅建议，未提交）：`Prepare approved default knowledge seeds and isolated publication recovery`。
