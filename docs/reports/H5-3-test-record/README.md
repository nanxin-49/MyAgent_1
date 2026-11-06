# H5-3 测试记录

- 捕获时间：2026-11-06T09:23:57.674394+00:00
- 环境：本地 uvicorn + 真实 Redis/Chroma（Redis 16379、Chroma 8001）+ 模拟业务后端
- 页面：`http://127.0.0.1:8000/demo`
- 浏览器截图：`demo-page.png`（静态页面壳；测试结果在用户浏览器会话中，不在服务端 HTML 内）
- 原始 Trace：`traces.json`（`GET /trace/tools?limit=50`）
- 冒烟响应：`smoke-*.json`

## 请求摘要

| request_id | tools | stop_reason | actions | RAG | steps | latency_ms | consistency_warnings |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| `8148fd5a` | get_refund_status, get_order | completed | — | — | 2 | 3485.0 | 0 |
| `2ab8580e` | get_order, get_refund_status, search_knowledge_base, request_refund | budget_exhausted | act_9b862376deb14129:completed | usable/1 | 3 | 9079.0 | 0 |
| `f1939718` | get_order | completed | — | — | 2 | 3797.0 | 0 |
| `06c7e9f4` | get_order, request_cancel_order, search_knowledge_base | budget_exhausted | act_8c9dc63b27e34e2b:rejected | low_confidence/0 | 3 | 6484.0 | 0 |
| `36d3eca1` | get_order | needs_clarification | — | — | 2 | 4781.0 | 0 |
| `abfc6716` | get_order, get_refund_status, request_refund | completed | act_c82a9922ea9846f0:completed | — | 3 | 5844.0 | 0 |
| `082e49e0` | suggest_required_fields | needs_clarification | — | — | 2 | 3984.0 | 0 |
| `0debd535` | search_knowledge_base | completed | — | usable/1 | 2 | 5688.0 | 0 |
| `11ce0601` | search_knowledge_base | completed | — | usable/1 | 2 | 5625.0 | 0 |

## 冒烟快照

- `smoke-policy-before-fix.json`：修复前政策问答，因输出一致性误判被替换为固定回执（问题记录）。
- `smoke-policy-after-fix.json`：修复后政策问答，返回完整政策 + citation，`consistency_warnings=[]`。
- `smoke-composite.json`：复合退款，两个 action 分别为 completed / awaiting_approval。

## 说明

- 页面截图是 `/demo` 的静态壳；浏览器中的 token、对话卡片和 Trace 是客户端会话，不会出现在服务端 HTML 中。
- `traces.json` 只包含请求/工具/动作/Token 用量摘要，不包含 prompt、模型隐藏推理或原始 Memory。
- `2ab8580e` 与 `06c7e9f4` 的 `stop_reason=budget_exhausted` 是 H3-6 已记录的 3 轮上限问题，不是执行器错误；录屏时若只出现一个 action，重启 fixture 重试或缩短消息，不能补造第二个 action。
- 这是演示环境测试记录，不是生产 SLA、真实支付或长期稳定性证据。
