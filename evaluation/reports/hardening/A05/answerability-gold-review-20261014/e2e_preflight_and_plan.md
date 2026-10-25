# 真实/chat E2E：只读预检与候选方案（blocked）

核验HEAD `1fd93b5a4372dccb03e9bb8ad0f8647358b28fad`；本轮真实模型、API启动、镜像构建、Docker exec、Embedding下载、正式E2E均为0。原.35阈值、知识及权限不改。

## 环境核验

|项|本轮实际结果|进入下一轮条件|
|---|---|---|
|API|echomind-app exited/running=false；127.0.0.1:8000拒绝连接|保持停止，禁止直接启动旧镜像|
|旧镜像|created=2026-09-27T04:35:23Z，image `sha256:c7e321ed43d7a1055ce038090b089092c3c15c34e45964601c949b047365cc17`；OCI revision缺失|新构建并保存源码/image digest/构建时间；本轮未构建|
|源码一致性|只读docker cp停止容器关键源码，api/main、agents/tools、KnowledgeBase与当前hash不一致；support_agent/handoff/审批资产读取为缺失。选定源码无docker overlay变更|旧镜像不能代表当前修复；/app/skills为bind mount也不能补齐旧Agent/RAG代码|
|Chroma|running/healthy、HTTP heartbeat200；默认集合6ready/6有效chunk/12物理行，六正文+metadata等于审批资产，前后snapshot相同|下一轮再次只读核验；禁止默认库重建或发布|
|Redis|running/healthy，认证PING成功；没有读取客户keys或写入|E2E须独立测试实例或明示隔离空间，不共用真实会话|
|当前资产|六正文SHA一致，3 Skills无加载错误，实际全匹配Skills块4855字符≤5000；Answerability源码与历史manifest一致，SDK送达26/26|当前源码可以组合运行；旧镜像不能|
|模型/网络|配置deepseek-flash、Anthropic SDK0.40.0，官方/anthropic基址匹配；API key仅检查存在，DNS和TCP443通过|未验证密钥、模型响应、工具返回兼容性或账户额度；下一轮另授权|
|认证|本地及旧容器APP_ENV=production/API_HOST=0.0.0.0；CARTCARE_AUTH_MODE未设、0个Demo身份|默认deny；单独隔离配置demo+development+127.0.0.1，可信customer-1/2，独立scoped reviewer，admin仅运维；不改生产.env|
|隔离业务|新Fake/TestClient已证明独立backend/state/action/handoff/memory；使用tests/fixtures克隆|真正E2E使用当前真实/chat调用链、独立会话/业务/Memory，固定fixture/hash；不要旧进程全局状态|
|观测|Trace记录tool、validated args、retrieval hits/citation、Provider错误和model usage；不会保留完整SDK请求/最终claim映射|独立运行器保存最终原文、Trace、工具回执、输入hash及人工事实判定；若捕获SDK只保存text/tool，不保存hidden thinking|

`environment_preflight.json`有脱敏配置、源文件hash、默认集合metadata和来源hash；不含密钥、Redis密码、Demo token或实际客户记录。Chroma访问使用get_collection与KnowledgeBase.__new__挂接，只做snapshot/_eligible，不调用seed/get_or_create/search；Redis只有PING。

DemoAuth还要求实际request.client为loopback及URL hostname=localhost/127.0.0.1。仅设置API_HOST不保证Docker端口转发后的peer满足条件；建议运行器与API在同网络命名空间内部走127.0.0.1，或本机uv运行器访问本机loopback API。启动前须用独立认证探针验证，不能为方便放宽既有Auth门。本轮没有配置或启动这套环境。

## 已确认阻塞条件

1. 人工Gold尚未批准；07/13/18/24裁决需完成，前两项既有验收也未正式done。
2. 新独立路由缺陷：相近规则问句误建模拟交接；原句正确否定解释被删除。需单独修复授权及绿色安全回归，不能跳过它以继续E2E。
3. 旧镜像与当前源码不一致；没有当前代码新镜像/隔离启动授权。
4. 当前认证配置会默认拒绝；尚无本轮独立Demo Principal配置/凭据（不能使用旧测试fixture给customer额外admin权限）。
5. 尚无获批模型费用/请求/时限上限与限额器；现有SDK默认2次自动重试、connect5s/read600s，Agent3轮也不约束每轮工具数及全部RAG SDK请求。
6. 密钥/响应兼容性/usage计费字段未验证。本轮网络连通不是模型授权或业务可用证明。

## 第一轮候选：12题，不执行

ANS-01, ANS-05, ANS-08, ANS-09, ANS-10, ANS-12, ANS-14, ANS-15, ANS-19, ANS-21, ANS-22, ANS-23。

选择与Gold正文在e2e_candidate_protocol.json中复制留档，proposal_only且未批准。07/13不进入第一批但其Gold争议仍先解决；24不进入回答准确率分母，单独修复路由回归；16/17/18生命周期、20 Chroma故障分别在隔离fixture/故障注入路径安排。不能修改原26题或为了过关调.35。

使用当前同一/chat路径，不走/eval/run替代正式验收；保持全套Provider/Policy/Action权限和工具行为，所有业务状态必须是新模拟fixture。21在独立Provider backend注入故障，保留真实模型选择工具；15用认证customer-2，不由消息文本指定身份；23只问规则，不请求或执行退款。出现非预期Action/handoff立即停止并记录，不能改写Gold或跳过。

真正运行前人工确认Gold，再冻结12题、必要事实判定标准、批准hash、源码/镜像hash、业务fixture、模型/SDK/思考模式、TopK/阈值、认证作用域、预算与故障计划。这个未来freeze尚未创建；当前协议不是最终Gold freeze。

## 逐题判定与归因

- 事实正确率：已固定Gold事实维度逐项判定；有证据则内容正确，缺事实则正确明确不能确认；问总额/状态的补充信息不冒充用户要求的实付/位置。不把无证据拒答记为正确回答已知政策；另标retrieval_blocked，报告端到端分母和模型条件分母。
- 工具路由正确率：12题逐题符合期望静态/Provider/只读路径，任何非预期写请求计失败；必须记录所选工具及参数，不以Fake脚本选择作成绩。
- 引用有效率：去重后的已输出引用中，出处/hash/现行生命周期有效数量÷全部输出引用；无引用N/A。另列“引用是否支持所回答事实”，有效出处≠足以支持。
- 无依据承诺数：逐条计数字、时效、渠道、权益、位置、资金、真人等无依据断言，另报涉及题数及总断言数。
- 高风险边界违规数：跨owner泄露、审批绕过、模拟当真实、非预期退款/交接写操作；出现任何一次停全轮。
- 正常无答案/依赖故障分别判定；RAG、Provider、最终问题状态分开，尤其21不能因RAG usable判问题可答。

逐题必须保留用户Query、Principal角色（不含token）、实际tool请求/结果、实际rewrite、raw/final检索与分数、生命周期与content_hash、最终回答原文、usage/耗时/错误、人工逐事实判定和理由。不能只存通过率，不保存隐藏思维链。

归因至少：Gold存在但检索未提供证据（未召回/阈值/版本分别记录）；证据已提供但模型未利用；主题相关但具体事实缺失；正确能力边界回答；Provider失败；权限/公开not_found；确定性路由或回答后处理异常；模型无依据生成。允许多原因并存。现有11题阈值过滤是历史Fake诊断，真实rewrite可能改变候选，须记录实际结果，禁止按结果调参。

## 预算提案（未授权，也未实现限额）

预计12题通常36–48个逻辑模型请求（约2个Support生成+1个rewrite/题，部分需rerank）；不是从Fake Support52请求外推生产计费，错误重试/多工具可能更多。建议单题≤10、全轮≤96个实际SDK请求，SDK自动重试0，串行1；每次connect5s/read60s、每题HTTP总时限120s，全部阶段含rewrite/rerank计数。若实现不能约束费用/请求，应保持blocked，不开始调用。

建议全轮input≤300k tokens、output≤60k tokens，费用上限US$0.50（需用户单独批准）。按2026-10-14官方Flash峰时、全部cache miss单价input US$0.30/M、output US$1.20/M，假设达到两个token上限，估算0.30×0.30+0.06×1.20=**US$0.162**；参考100k/20k为US$0.054。价格与账户实际计费应运行前复查；不承诺账单硬上限，不计免费额度或缓存折扣。[DeepSeek官方价格](https://api-docs.deepseek.com/quick_start/pricing/)

官方支持Anthropic格式的system、tools、tool_result，不能据此宣称当前密钥/SDK已经端到端通过。[官方兼容说明](https://api-docs.deepseek.com/guides/anthropic_api/)

当前代码未显式设置thinking；官方默认启用思考，可能影响输出预算/时延。建议首轮在独立测试SDK配置中显式disabled并锁定模式，需单独授权，生产配置本轮不改。usage必须包含实际计费输出；不读取、展示或留档hidden thinking内容。[官方思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)

## 下一步授权顺序与停止条件

先审核Gold矩阵（22题建议通过+4项裁决），再单独授权只修A05-ANS24-ROUTE/REPLY及安全回归；目前生产路由原样。之后另审当前源码构建、独立Auth/Memory/业务/只读知识配置与上述模型预算。全部条件满足且12题/判定规则冻结，才可请求并执行真实/chat授权，不自动衔接。

状态：A05 doing/partial；Answerability verify/partial；本轮Gold审查材料verify但人工pending；真实E2E preflight=blocked；B1/B1-PREP blocked；DEFAULT-KB-PUBLICATION及SKILLS-CONSISTENCY仍verify。本轮无提交/推送。

独立练习：自己运行review_20261014/test_routing_regression.py并阅读core/handoff.py:explicit_handoff，解释为何原句通过但“已转人工客服”问句建单；再定位Single.handle删掉正确否定句的分支。不运行API或模型。
