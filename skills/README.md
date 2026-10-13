# CartCare Skills 文档

CartCare 启动时从 `ECHOMIND_SKILLS_DIR`（默认仓库 `skills`）加载 Skills。当前 `/chat` 使用 SingleSupportAgent；`AllRoleSkills` 忽略兼容用 `agents` 标签，按关键词匹配后经 BaseAgent 注入同一个 Agent 的 system prompt，不执行多个独立 Agent 分流。明确转人工走确定性交接门，不调用模型，因此 Skill 匹配不等于该请求一定发生模型注入。

Skills 只提供解释和参数收集指导，不能代替 Provider 动态事实、PolicyEngine/ActionService 的资格、金额、权限或审批控制。当前知识正文及模拟交接/退款能力边界为准；没有证据不补全未接入商城能力或外部业务规则。默认总预算5000、单 Skill 正文上限3200字符；重要边界靠前，修改后应验证真实注入而非只搜索文本。本轮 API保持停止，不调用实际 reload 接口。

当前内置三类 Skills：

```text
skills/general_customer_service/SKILL.md  # 单客服：接待、澄清、事实边界和模拟交接
skills/technical_support/SKILL.md         # 技术支持：故障排查、接口错误、部署配置和安全边界
skills/billing_support/SKILL.md           # 退款解释、受控动作及未接入账单能力边界
```

## Skill 文件格式

推荐每个 Skill 使用独立目录，并将主文件命名为 `SKILL.md`：

```text
skills/<skill_name>/SKILL.md
```

文件顶部使用简单 front matter：

```markdown
---
name: 技术支持处理规范
description: SingleSupportAgent 的故障排查方向和模拟交接边界
keywords: 报错,错误,接口,API,部署,超时,500,401,日志
agents: technical
enabled: true
---
```

字段说明：

- `name`：Skill 展示名称，会出现在注入给模型的 prompt 中。
- `description`：简短说明，方便 `/skills` 接口排查。
- `keywords`：大小写不敏感的子串匹配；多个关键词用英文逗号分隔。
- `agents`：保留 `general`、`technical`、`billing` 兼容标签；当前 SingleSupportAgent 通过 AllRoleSkills 不用此字段分流。
- `enabled`：是否启用，支持 `true/false`。

## 编写要求

- 重要规则放在文档前半部分，因为过长内容会按 prompt 预算截断。
- 一类 Skill 只描述一类职责，不要把技术、账单、通用客服规则混在一个文件里。
- 必须包含“角色定位”“处理流程”“升级条件”“禁止事项”等稳定章节。
- 对用户隐私、支付、密码、验证码、API Key、Token 等敏感信息必须写明禁止收集或禁止公开。
- 无法确认时明确缺少证据；“通常”“预计”也不能用来补充不存在的资金到账、发票、订阅或会员承诺。
- 动作审批与模拟人工交接分开；审批遵循确定性规则，交接须有真实工具成功回执和编号，不等于真人或二线接单。

## 热加载

将来进入已授权的内部运行时验证后可热加载；以下接口要求可信 admin 认证。本轮不要恢复API或执行下列请求：

```bash
curl -H "Authorization: Bearer <trusted-admin-token>" -X POST http://localhost:8000/skills/reload
```

查看加载结果和解析错误：

```bash
curl -H "Authorization: Bearer <trusted-admin-token>" http://localhost:8000/skills
```
