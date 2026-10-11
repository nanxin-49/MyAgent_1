# Provider 错误公开边界 — A03-lite/N03

2026-10-11，HEAD `b00344be38e83af5d1f13d81b8d0f2f4a628a950`；本轮工作区起始干净，N01已在HEAD中。outcome=`fixed`，状态=`verify`，待用户验收。只实施N03，N02-auth/N02-ops未实施。

## 证据与决策

审查报告N03、`audit_20261011_probe.py:provider_probe()`及观察JSON的`PROVIDER_ERROR_LEAK`一致：给订单移除必填字段并加入合成敏感标记，另一用户查询时先触发Pydantic校验，原始输入进入`exc.errors()`，经`ProviderError.to_dict()`进入工具与模型。历史脚本断言缺陷成立，不能作为修复成功测试，本轮未运行或覆盖原脚本/JSON。

决策：沿用现有Provider、Tool Contract、SingleSupportAgent和ActionService，不引入身份框架。先对有归属的原始Mapping检查`customer_id`；缺失、不可判定或不匹配均拒绝，再校验模型。保留模型校验后的二次归属检查。该共享路径覆盖Order、Shipment、Refund Provider；Product/Inventory保持模型校验。

`_BaseProvider._read()`的校验诊断只保留`validation_error_count`和去重后的`validation_error_types`，不保存input/msg/ctx/loc，不打印原始记录。校验及依赖异常使用`from None`抑制常规traceback中的原异常内容。底层异常仍可能存在于Python异常上下文中；不得绕过该安全边界直接记录`__context__`、backend raw或完整locals。本轮不新增日志输出。

`ProviderError.to_dict()`为公开投影：消息来自固定错误码映射，未知码降级为provider_error，details始终为空。保留由调用请求产生的resource_id及Provider固定resource_type；这些字段是查询定位信息，不是原始后端记录。内部`.code`仍为typed code，供确定性Action/Policy逻辑使用。

读工具对UnauthorizedError公开映射为not_found，与不存在记录共用安全消息；合法owner的畸形记录公开返回invalid_data及固定消息。此决策隐藏错误码/message层面的存在性差异，不承诺网络时序不可区分。ActionService内部授权错误及接口契约未变，N02可信身份/审批权限不在本轮范围。

## 路径与兼容

前：Provider model_validate → 带原始输入的校验错误 → ownership（未执行）→ Tool error.to_dict → execute_tool/Trace/model tool_result → HTTP。

后：原始归属判定 → model_validate → 安全诊断/typed error → 公开投影 → 原有Tool/Trace/model/HTTP路径。`agents/tools.py`已有统一error.to_dict调用，不需要另建转换或修改Agent/API。正常合法owner查询回归保留，动作审批/幂等测试继续通过。

公开读工具错误码从unauthorized变为not_found，原test_business_tools对应断言同步；内部Provider UnauthorizedError及N01 ActionService unauthorized断言保持。README/核心Wiki没有逐错误码描述，无新增架构漂移，本轮无需修改。未来N02设计时再补Principal章节，当前Demo user_id不能视为认证。

## 验证

环境：Windows、Python3.12.3、uv canonical依赖，Fake SDK/Memory及内存fixture backend。测试仅含合成敏感标记，无真实客户数据。

| 阶段 | 命令 | 结果 |
| --- | --- | --- |
| 修复前安全红测6例 | `uv run python -m pytest -q tests/test_provider_safety.py` | 6 failed，1既有AnyIO警告 |
| 最终相关回归 | `uv run python -m pytest -q tests/test_provider_safety.py tests/test_business_providers.py tests/test_business_tools.py tests/test_action_service.py` | 58 passed，1既有AnyIO警告 |
| 全量 | `uv run python -m pytest -q` | 176 passed、2 skipped、1既有AnyIO警告 |
| 依赖/格式 | `uv lock --check`；`git diff --check` | 53 packages，通过 |

新增12例：合法/非法owner的畸形订单错误不带原始输入，ProviderError任意message/details不直接公开，foreign/missing读错误统一，Fake SingleSupportAgent真实生产接线中将tool_result原样回显至/chat并检查HTTP、Trace及模型第二次输入；另覆盖Order/Shipment/Refund的缺失归属和异主体。traceback/caplog不含标记。既有成功查询及31个ActionService测试通过。

2项跳过为live Redis/Chroma Memory和真实Chroma HTTP RAG opt-in；未执行真实模型HTTP E2E、支付、容器、部署或远端CI。不把Fake回显测试称为真实模型行为保证。

原证据SHA256保持：probe=`D29C48289C1A608695EDA966C8168A9C1E40057635AEF21B205B85D1DD47A462`，observations=`67B5ACC58B189CB1A4AD26B5D4891025EBE32AF9531FB819461692EF80ACE1B1`。历史T09–T12只读。

## 未解决边界与独立练习

N02可信Principal、独立reviewer及Trace/管理权限仍未实施，不能因此宣称公网安全。本轮不扩展到N04/N05或其他风险，也不改变N01跨进程/重启一致性限制。

独立练习：新增一例合法owner订单`total_amount`含合成敏感字符串的测试，经get_order工具断言invalid_data、details为空且字符串不在结果中；再检查Provider内部诊断仅含decimal校验类型和数量。运行该测试并说明内部诊断为何不能直接作为模型tool_result。
