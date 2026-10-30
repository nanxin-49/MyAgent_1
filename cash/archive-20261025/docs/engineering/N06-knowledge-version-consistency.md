# N06 — Knowledge 版本一致性与旧知识退役

2026-10-12；起始 HEAD `f229aeb23364b775a1b18ee437ff1e710151bbde`，工作区干净。结果 `fixed`，状态 `verify`，待用户验收。仅 N06；未执行 N07、A05 对照实验或其他任务。N01/N02/N03/N04/N05/N10 保留。

## 原始问题与证据

原审查的 `knowledge_probe` 在隔离 Fake Chroma 中先写同 document_id/v1 的 7 天，再写 30 天；chunk ID 含内容，upsert 不会覆盖旧 ID。两段都成为 usable，citation 都是 `audit-policy@v1#chunk-0`。再发布 v2 后，三个片段都可用。原脚本和观察 JSON 原样保留，没有重跑会覆盖历史 JSON 的主入口。

正式回归复用了该输入与 Fake 的固定距离：初始 `uv run python -m pytest -q tests/test_knowledge_version_consistency.py` 为 **5 failed / 0 passed**。同版本实际返回 `['Refund window is 7 days.', 'Refund window is 30 days.']`；ToolManager 600 秒缓存返回原政策；supersedes/expires_at/publication_status 尚不被输入契约支持。新原始观察另存 `N06-knowledge-version-observations.json`。固定距离说明生命周期缺陷，不是排序质量测量。

## document、version、chunk、citation

- collection 是存储边界；document_id 是其中一个知识主题的稳定身份，必须绑定同一 source/doc_type。不同 document_id 不自动合并。
- policy_version 是业务发布标识，不能按字符串排序。推荐人工明确 document_id；省略时现在按 source + title 生成稳定 ID，不再按内容生成。改标题或来源应显式提供原 ID。
- revision 是完整已校验文档（包括生命周期）的 SHA256；chunk ID 由 document/version 发布键、revision 和片段序号生成。相同输入重复发布得到相同 ID，不新增重复片段。
- content_hash 是实际 chunk 文本的 SHA256。内容 hash 证明内容身份，不能说明哪条政策应当生效；version 说明发布身份，也不能区分同版本修订文本。二者均需保留。
- 新 citation.reference 为 `document_id@policy_version#chunk-index~<完整chunk SHA256>`（非 policy 可省略 @version），并新增可选 content_hash。同版本内容修改不会共享旧 reference。旧无 hash 的引用仍可被模型解析，历史 Trace 不重写；真实 KnowledgeBase 只输出经发布完整性校验的新引用。

## 最小发布协议

没有引入新数据库。每个 document/version 在原 Chroma collection 中有一条 `record_type=publication` 的 JSON 发布记录，内容包括校验后的文档、revision、完整 chunk IDs、`publishing/ready`。发布记录也必须写显式向量，但不进入知识候选，doc_count/接口 total_chunks 不计发布记录（计物理 chunk，可能包含历史版本/待恢复片段）。

实际调用链：管理员 `/knowledge/add` 或 `/knowledge/upload` → `KnowledgeDocument` 校验 → `add_documents_async` → 同进程 RLock → `_publish`：

1. 核验身份、替代关系及不可逆生命周期；批次先做结构校验，拒绝同批重复身份。
2. 持久化 `publishing`，读回确认，再开始修改 chunk。此时同版本旧内容已经不可检索。
3. upsert 本次全部 chunk；按精确 document_id/version 删除不属于新集合的旧 ID，只作用于当前 collection。发现 source/type 身份冲突先拒绝，不删除对方记录。
4. 读回逐条核验文本、metadata、IDs 及旧 ID 删除结果。
5. 将单条发布记录改为 `ready`，再读回确认，才返回片段数量。

同版本更新是完整替换，短文本更新会删除多余旧 chunk。跨版本替代保留旧版本 chunk 与发布记录，靠退役关系过滤，不批量删除历史资料。

## 版本与时间契约

知识输入新增 `supersedes: list[str]`、`expires_at` 和 `publication_status`（active/revoked，默认 active）。日期必须带时区，expires_at 必须晚于 effective_at。

```json
{
  "document_id": "refund-policy",
  "title": "退款说明",
  "source": "merchant:refund-policy",
  "doc_type": "policy",
  "policy_version": "v2",
  "supersedes": ["v1"],
  "effective_at": "2030-01-01T00:00:00Z",
  "expires_at": "2031-01-01T00:00:00Z",
  "publication_status": "active",
  "content": "用于解释的已审核政策文本"
}
```

前驱必须已经存在于同 document_id/source/type 的发布记录中，不能引用另一主题；拒绝循环或比前驱更早生效的替代。批次按输入顺序发布，前驱在前。没有 supersedes 的不同 version 不推断新旧关系，可保留各自适用知识；调用方负责声明政策替代。

有效区间为 `[effective_at, expires_at)`。未来 v2 尚未生效时，v1 只在自身仍有效的区间内可用；v2 正式生效起，v1 被退役。即使 v2 后续过期、废止或发布失败未完成，也不会复活 v1。已接受的 supersedes/effective_at/source/type 不可通过同版本更新移除或改变；revoked 不可恢复 active；已设置 expires_at 不可延长或移除。内容/标题可同版本修订，需要新生效区间时发布新版本。

单独废止某版本：重新发布同 document_id/version 和原生命周期参数、`publication_status=revoked`。没有另建危险业务执行入口。

## 检索与 Top-K

`search_handler → search_async → search` 先读取发布快照，再由 `_eligible` 检查 ready、状态、时间、退役关系及全部 chunk 完整性。Chroma query 使用实际有效 `chunk_id $in` 作为 where 候选过滤；publication、未来、过期、废止、被替代及不完整组不占 Top-K。查询后再读回快照，若发布在窗口中改变则失败；命中文本/metadata 必须与实际存储一致。build_hit 再验证 content_hash，失效元数据无 citation、不可 usable。

ToolManager 对有 `validate_hits_async` 的 KnowledgeBase 禁用持久结果缓存；其他工具原缓存与 retry 契约保留。rewrite/rerank 后再次对照当前发布状态，以免模型 await 期间更新后旧结果仍进入响应。旧结果全部失效则 no_answer，复核服务失败则 degraded；未修改 N07 的原始 rerank 空数组分支。

## Chroma 非事务限制与恢复边界

**这不是原子更新，也不是分布式事务。** 同进程 RLock 只串行化本进程读写；HTTP 网络调用、多个 chunk 和发布记录均是独立操作。部署需单发布者；多 worker 同时发布没有分布式锁/CAS 保证。快照比较可以检测部分竞争，不是线性一致性承诺。发布完毕以后、响应已经生成之后的后续更新不会追溯撤销历史回答。

- 首条 publishing 写入失败或静默未落库：读回未确认即停止，尚未修改 chunk；原已提交知识仍有效。网络超时可能写入成功，此时实际 publishing 记录会阻止旧内容，不能声称知道服务器最终状态。
- chunk 写入/部分写入/删除失败（包括静默丢写）：发布停在 publishing，新旧内容均不能作为当前依据。新实例从 Chroma 读到相同状态，禁止静默回退旧政策。
- ready 写入异常：服务可能已接受提交或仍是 publishing；API 不报成功。读取完整 ready 仅允许已核验新内容，绝不回退旧内容。完全未确认的 publishing 需重试。
- 对失败请求重发完全相同的文档即可恢复；revision/IDs 稳定。若批次第二项失败，第一项可能已发布，整批返回失败，重试不会增加重复片段。没有整批回滚保证。
- `/knowledge/add`、`/knowledge/upload` 保留管理员授权；无效 metadata 422；存储/提交异常 503、固定 `knowledge_publication_failed` 和 `retry_required=true`，不暴露外部异常文本、不宣称成功。
- 当前实现读取全量 collection 文本/metadata 核验完整性，并发送有效 ID 列表，适合演示规模；大库内存、HTTP payload 和延迟未测量，不宣称生产规模性能。

## 旧数据兼容与安全失败

没有发布记录的旧 chunk 无法证明它是否属于当前完整版本、是否已被其他资料替代。保留原数据，禁止作为当前候选；仅旧格式的集合返回 degraded 并要求审核后重发布，不把它当作成功检索。混合集合仍可检索完整的新发布知识。

本轮没有自动推断/清理旧 collection。迁移需从可信源核对 document_id、version、有效期和替代链，然后通过原管理员写入接口按前驱→后继重发布。精确同 document_id/version 重发布会替换该身份的旧 chunk；没有可靠身份时不要据文本或版本字符串猜测，给审核后的明确身份，保留旧证据。旧 auto ID 原来包含内容，不能自动映射到新 source/title ID；需要人工审核。仍有效、未替代、已符合新发布契约的其他文档不受影响。旧格式资料必须经过此迁移，不能承诺无缝继续可用。

## 验证与验收

Windows / Python 3.12.3 / uv；Fake SDK 和 Fake Chroma 不涉及收费模型。

| 验证 | 实际结果 |
| --- | --- |
| N06 正式回归（同版本、显式替代、未来生效前/边界/后、过期、废止、hash/citation、Top-K、缓存和 await 窗口、重复、故障与恢复、旧数据、身份冲突、批次部分发布） | 39 passed |
| 原 RAG Contract + Tool Contract + opt-in HTTP 文件默认运行 | 41 passed / 2 skipped |
| N01/N02/N03/N04/N05/N10 回归六文件 | 134 passed |
| 完整 `uv run python -m pytest -q -o cache_dir=.pytest-cache-n06` | 306 passed / 3 skipped，既有 AnyIO 弃用警告 |
| 隔离 Chroma HTTP 两项 | 2 passed；127.0.0.1:8001；随机 collection，finally 删除 |
| `uv lock --check` / `git diff --check` | 53 packages / 通过 |

最初 HTTP opt-in 因 `.env` 容器主机 chromadb:8000 在本机不能解析而 2 failed；尚未创建集合。仅测试进程覆盖 CHROMA_HOST=127.0.0.1、CHROMA_PORT=8001 后 2 passed，未改 `.env`。真实 HTTP 覆盖入库/查询/同版本替换/重复写入/显式替代/未来到时生效/过期不复活/无关文档保留；服务故障仍是 Fake 注入，没有对正常服务做断电、并发 worker 或支付测试。默认完整测试跳过两项 HTTP 与一项 live Memory；Memory 真实服务和真实模型 /chat 未重跑。

使用 cache_dir override 避免本机既有 cash/pytest 写权限警告；不修改依赖或全局 pytest 配置。历史 T09–T12 报告和审查 JSON 未覆盖。

原 Tool 输入 schema、风险/权限 gate、检索返回状态集合、add_documents 返回 int、API added_chunks/total_chunks 保留；DocInput 明确拒绝未知字段。citation 增加可选 hash 且新 reference 附 hash；按 reference 去重与 Demo 字符串展示兼容，严格依赖旧 reference 字面格式的调用方需适配。

## PolicyEngine 与范围

`policies/engine.py` 仍定义 7 天窗口、500 元自动审批边界及确定性规则。测试中的 30/90 天是隔离合成资料，与真实业务规则不一致，不能当作可执行退款承诺；从未写入正常知识库。默认演示政策仍为 7 天，与 PolicyEngine 一致，未发现默认文案的窗口漂移。外部旧资料没有全面内容审计，不能据此宣称所有知识与业务政策一致。

本轮没有改 Embedding、0.35 阈值、PolicyEngine、Single-Agent、RAG 框架或新数据库；没有开展 A05 质量实验。N07 空重排问题仍 known_open，不影响本轮确定性生命周期验收。

## 独立练习

不使用 Codex，运行 `uv run python -m pytest -q -o cache_dir=.pytest-cache-n06 tests/test_knowledge_version_consistency.py`。阅读 `test_failure_blocks_old_and_partial_chunks_until_retry`，在 FakeCollection 的第二个片段写入后抛异常，独立确认：API 不成功、发布记录为 publishing、新实例无法取得旧政策、无关文档仍能检索。关闭故障并重试同请求，确认全部新片段可用且 chunk 数不增加。再把 successor effective_at 推迟，解释为什么前驱生效区间决定生效前是否可用，为什么 successor 过期不应复活前驱。

建议提交：`fix(rag): enforce knowledge publication lifecycle and retire stale chunks`。尚未提交、推送；停止等待验收。
