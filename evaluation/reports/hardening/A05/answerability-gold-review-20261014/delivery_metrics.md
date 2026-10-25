# 26/26规则送达指标核对

历史文件不覆盖；下表是基于原证据及本轮不可变SDK请求快照的新增派生统计。

|观测位置/定义|修复前历史|修复后历史或本轮|分母|
|---|---|---|---|
|Tool payload具有answer_guidance字段|16|26|26题；原非usable结果已有该字段|
|原boundary_delivered复合公式|0|26|26题；BASE_RULES子串均在首个SDK system且RAG guidance含事实充分|
|本轮实际构造system prompt具备BASE_RULES|未另测|26|26构造；构造不等于调用|
|本轮实际调用Support SDK|未另测|26|26题；52个Support请求|
|本轮所有Support SDK请求system含BASE_RULES|未另测|52|52实际请求|
|最后一个Support SDK请求system有BASE_RULES|未另测|26|26实际调用题|
|RAG guidance存在于最终SDK tool_result消息|未另测|26|26实际调用题|
|原26题确定性门绕过模型|未另测|0|26题|

ANS-24精确冻结Query：explicit_handoff=false，Support SDK调用2次、未建新记录，最终SDK实际含基础规则和RAG guidance。因此无需把历史分母改为25；26/26可以保留为复合规则送达指标。
相近规则问句和显式请求控制：确定性门命中，SDK=0；不加入26题分母，也不得称模型收到规则。它们不是对原Query的替换。未来指标只以实际SDK调用题作分母，另报确定性分支数量。
范围是Support回答SDK；RAG rewrite/rerank SDK是其他阶段，不声称所有SDK步骤都收到回答规则。Fake选择RAG/Provider是脚本指定，不能用于评估真实模型工具选择正确率。
SDK快照在调用边界deepcopy，避免BaseAgent后续append工具结果污染首个请求的观测。sdk_delivery_actual.json保留每个实际Fake请求和Trace。
该统计不是模型遵循率或回答准确率。原句中正确否定说明被代码后处理删掉，说明“模型已收到规则”与“最终API答复正确”还受不同阶段影响。
