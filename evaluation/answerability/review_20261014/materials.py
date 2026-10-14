"""Additive four-part human review delivery. No Gold rewrites or approvals."""
import hashlib
import json
from datetime import datetime, timezone

from evaluation.answerability.review_20261014.probe import ROOT, OUT


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    base = ROOT/'evaluation/answerability'
    old = ROOT/'evaluation/reports/hardening/A05/answerability-20261013'
    gold = read(base/'dataset_v1.review_candidate.json')
    history = {r['id']:r for r in read(old/'after_final.json')['rows']}
    integrity = read(OUT/'gold_integrity.json')
    env = read(OUT/'environment_preflight.json')
    metrics = read(OUT/'delivery_metrics.json')
    routes = read(OUT/'handoff_routes.json')
    docs = read(old/'corpus_snapshot.json')
    doc_titles = {d['document_id']:d['title'] for d in docs}
    disputed = {'ANS-07':'需用户裁决：total_amount只是补充信息，未回答实付/渠道；是否保留partial_dynamic命名。',
        'ANS-13':'需用户裁决：当前必要事实没有单列实时地理位置；建议补上不可确认的位置事实。',
        'ANS-18':'需勘误确认：仅allowed_boundary改为合法publishing无有效chunk→success=true/no_answer。',
        'ANS-24':'需用户裁决：Gold无需新建交接；先单独授权修复规则问句误建单和正确否定说明被删除。'}
    supplemental = {
        'ANS-07':'可告知Provider核验的订单总额129.90 CNY，但必须称其为总额；这不是用户所问两事实的部分命中。',
        'ANS-13':'可作为补充说明演示物流状态in_transit、承运商、运单号、更新时间、预计日期2026-09-29；不能回答实时位置。',
        'ANS-14':'只能说明未找到当前客户可访问记录；不能断定订单不存在。',
        'ANS-15':'只能公开not_found；不确认customer-1记录存在，更不能输出其明细。',
        'ANS-21':'可说明Provider查询失败；RAG可以解释查询边界，但不得使用fixture中shipped推断本次动态状态。',
        'ANS-24':'可解释模拟记录≠真人接单；“本次未创建新记录”仅是当前动作补充信息，不能代替原问题答案。',
    }
    matrix = ['# A05 Answerability Gold 最终人工审核矩阵', '',
        f"2026-10-14；核验HEAD `{integrity['head']}`。以下均是**审核建议，未批准**。不要据测试通过直接勾选。", '',
        '原冻结与候选hash、addendum及历史输入manifest均核对通过；26 Query/Gold行为/必要事实/来源/场景字段完整，24题有正文依据（含生命周期隔离变体）。',
        '原始与候选唯一差异是ANS-18的allowed_boundary；未改Query、Gold分类、场景、证据或必要事实。',
        '`evaluation/answerability/corpus_snapshot.json`实际不存在；本轮明确读取历史报告目录的同名快照，并核对它等于六篇批准正文；没有补造旧文件。', '',
        '检索列引用最近26题Fake cosine存储的原始测量，不是本轮live检索成绩。当前live服务预检仅查publication/chunk/hash，未对26题再次检索。', '',
        '## 一次性裁决清单', '',
        '|项|建议及理由|人工决定|','|---|---|---|']
    for id,message in disputed.items():
        matrix.append(f'|{id}|{message}|[ ] 待用户决定|')
    matrix.extend(['|其余22题|建议通过当前事实边界；检索阈值漏证据单列，不据此修改Gold。|[ ] 待用户确认|','',
        'ANS-07建议选择：A，保留partial_dynamic，但明定“partial”只是可核验补充上下文；B，推荐将最终Gold分类改为已有supported_boundary，并保留get_order作为补充上下文工具。这是候选意见，现有分类未改。',
        'ANS-13建议：保留dynamic_required，增加必要事实“实时地理位置不可核验”，并把“实时地理位置”列为unavailable_facts；不把in_transit当位置。',
        'ANS-18建议确认既有勘误；ANS-24建议保持问题只读Gold，路由修复另轮授权，不删除问题或改成创建交接。', '',
        '## 逐题矩阵', '',
        '|ID / Query|场景 / 原Gold|必须回答或明确不能确认的事实|允许补充 / 部分范围|必须拒绝或不能推断|有效正文 / 动态依据|期望工具|最近检索 / 限制|Gold歧义 / 建议|',
        '|---|---|---|---|---|---|---|---|---|'])
    for c in gold['cases']:
        row = history[c['id']]
        provider = row['provider_payload']
        evidence = []
        for e in c['available_evidence']:
            evidence.append(f"{doc_titles[e['document_id']]}（见文末ID/source/hash表）；“{e['quote']}”" if e['quote'] else
                '仅相应政策的隔离生命周期变体；本场景无当前可引用政策')
        if provider:
            if provider.get('success'):
                fields = ['order_id','status','total_amount','currency','estimated_delivery','updated_at']
                selected = {k:v for k,v in provider['data'].items() if k in fields}
                evidence.append('模拟Provider：'+json.dumps(selected,ensure_ascii=False))
            else:
                evidence.append('模拟Provider公开结果：'+provider['error']['code'])
        tool = ('search_knowledge_base + '+c['dynamic_tool']+' '+json.dumps(c['dynamic_args'],ensure_ascii=False)
            if c['dynamic_tool'] else 'search_knowledge_base（正常模型选择需真实E2E验证）')
        if c['scenario'] in {'expired','future','publishing'}:
            tool = '隔离KnowledgeBase/N06/N07检索；无业务写操作'
        if c['id']=='ANS-24':
            tool += '；不得request_handoff'
        if c['id']=='ANS-23':
            tool += '；不得request_refund'
        status = row['rag_payload']['retrieval_status']
        limit = '目标raw Top5已召回但被.35过滤' if row['gold_raw_recalled'] and not row['gold_usable_recalled'] else (
            '相关正文可用不代表所问全部事实有答案' if status=='usable' else '无可引用证据；不证明事实不存在')
        if c['scenario']=='chroma_failure':
            limit = 'Chroma请求故障；不是正常无答案'
        if c['scenario']=='provider_failure':
            limit += '；Provider dependency_failure使动态问题不可确认'
        required = '；'.join(c['necessary_facts'])
        if c['id']=='ANS-13':
            required += '；位置问法应明确不具备实时地理位置（待批准补足Gold维度）'
        denied = '；'.join(c['unavailable_facts'])
        denied += ('；' if denied else '')+'禁止示例：'+' / '.join(c['forbidden_promises'])
        if c['id']=='ANS-13':
            denied += '；实时地理位置、保证送达'
        matrix.append('|'+ '|'.join([c['id']+' / '+c['query'],c['scenario']+' / '+c['gold_behavior'],
            required,supplemental.get(c['id'],c['allowed_boundary']),denied,
            '<br>'.join(evidence) or '六篇正文无所问事实，或注入故障没有证据',tool,status+'；'+limit,
            disputed.get(c['id'],'未发现标签歧义；建议通过，人工未勾选')])+'|')
    matrix.extend(['','## 六篇批准正文的出处与hash','',
        '|标题|document_id|source|content SHA256|','|---|---|---|---|'])
    for d in docs:
        matrix.append(f"|{d['title']}|{d['document_id']}|{d['source']}|{hashlib.sha256(d['content'].encode()).hexdigest()}|")
    matrix.extend(['', '完整引文/引用字段核验见gold_integrity.json；业务数据来自tests/fixtures/business_provider_data.json的独立内存复制。',
        '08的审核条件可以回答、到账时间不能补全；23的模拟动作完成不证明资金到账；26不得外推币种适用性，也不得谎称已有币种准入Gate。',
        '冻结Gold是审核边界，检索状态是观测，两者分别维护。本轮没有新增声称已批准的Gold freeze。'])
    (OUT/'gold_review_matrix.md').write_text('\n'.join(matrix)+'\n',encoding='utf-8')
    proposals = {'status':'human_decision_required_not_applied','base_candidate_sha256':hashlib.sha256((base/'dataset_v1.review_candidate.json').read_bytes()).hexdigest(),
        'ANS-07_options':{'A':'keep partial_dynamic, define it as verified supplementary context, not partial match of asked facts',
            'B_recommended':{'field':'gold_behavior','before':'partial_dynamic','proposed':'supported_boundary',
                'note':'keep dynamic_tool/get_order; order total is supplementary context only'}},
        'ANS-13_candidate_fields':{'necessary_facts_add':['实时地理位置不可核验'],
            'unavailable_facts_proposed':['实时地理位置']},
        'ANS-18':'confirm existing addendum only','ANS-24':'keep read-only Gold; route repair separate approval',
        'Gold_file_writes':0,'approved_freeze_created':False}
    (OUT/'gold_proposed_differences.json').write_text(json.dumps(proposals,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    focused = ['# 重点事实核验与ANS-24路由证据','',
        'ANS-07：Order模型没有paid_amount/payment_channel等字段。当前get_order成功只给total_amount=129.90等订单事实。该金额只是补充上下文，不能算回答了所问“实付/渠道”中的任何一个。分类歧义待用户裁决，不改Gold。',
        'ANS-13：Shipment只有status、carrier、tracking_number、updated_at及可空estimated_delivery等字段，没有实时地理位置或坐标。in_transit是状态，预计2026-09-29也是fixture估计值，不是当前实际位置或保证送达。此日期在本轮已过去，应明确为演示记录日期，不能称未来承诺。',
        'ANS-18：合法publishing文档无ready有效chunk时，_eligible排除，search返回[]，N07返回success=true/no_answer。只有allowed_boundary修正，完整语义diff与hash见gold_integrity.json。',
        'ANS-20：Fake collection.query抛Chroma依赖异常，RAG success=false/degraded，results/citations为空，无Provider调用；期望说查询不可用，不说知识不存在。',
        'ANS-21：RAG success=true/usable且有静态订单查询说明；get_order注入BackendDependencyError，Provider公开success=false/dependency_failure且data=null。整个动态订单事实仍不可回答，只能报告查询失败。RAG usable不能覆盖动态依赖失败。', '',
        '## 路由专项（真实Python路径 + 隔离Fake/TestClient）','',
        '独立进程内每条探针重建BusinessBackend、ActionService、Memory、KnowledgeBase和HandoffService；仅注入customer角色。无lifespan、服务监听、真实业务或真人通知。', '',
        '|探针|Query|实际分支|SDK调用|新记录|业务/动作变化|','|---|---|---|---|---|---|']
    for r in routes:
        diff = r['state_diff']
        focused.append(f"|{r['probe_id']}|{r['query']}|{r['matched_branch']}|{r['sdk_calls']}|{diff['handoff_count_after']-diff['handoff_count_before']}|business={diff['business_changed']}；action={diff['action_count_after']}|")
    focused.extend(['', '所有TestClient请求还会产生2条隔离Memory写入，这是/chat正常模拟副作用；handoff状态差异独立记录。前后完整状态、返回body及Trace见handoff_routes.json。', '',
        '## 独立缺陷与最小建议（本轮未修复）','',
        '**A05-ANS24-ROUTE（建议P1）**：同事实规则问句“……是否说明已转人工客服？”包含转人工客服，explicit_handoff正则匹配而没有排除询问既有记录含义；Single确定性门与HandoffService.allowed_reason重复认可同一判定。跳过SDK，records 0→1/attempts 0→1，escalated=true。没有真实接单，但增加模拟写操作及误leading回执，不能为继续E2E跳过。',
        '最小修复方向：在既有确定性显式请求判定内区分当前主动创建请求与记录/规则/已完成状态询问；服务Policy复用同一判断，保留customer/owner/幂等门及明确请求控制。不按所有问号一刀切，也不引入新Agent。需新增quoted/requested/not-requested、否定、显式请求、Model工具拒绝等安全回归。',
        '**A05-ANS24-REPLY（建议P2，E2E解释题阻塞）**：精确原句不建单、SDK调用2次且RAG usable，但Fake SDK返回正确的“不代表真人接单”句子被Single含人工/真人文字保护整句删掉，API仅返回“本次未创建人工交接记录”及引用；没回答规则含义。最小方向是区分证据支持的否定/能力解释与无回执的虚假成功承诺，继续保留A02拒绝、失败及真实回执保护，避免任意语言绕过。',
        '最小预期安全测试test_routing_regression.py：原句不建单通过；规则问句不得新增记录、正确否定说明应保留两条失败。routing_expected_safe_red.txt为2 failed / 1 passed / 1既有AnyIO警告；仅复现，未修改生产路由。',
        '原有Answerability/Handoff/Skills相关58测试仍通过；它们未覆盖这些问法/正确否定说明，不能据既有绿测否认新红测。',
        '下一步仅建议用户单独授权这两处修复；本轮不执行，不启动E2E。'])
    (OUT/'focused_checks_and_routes.md').write_text('\n'.join(focused)+'\n',encoding='utf-8')
    delivery = ['# 26/26规则送达指标核对','',
        '历史文件不覆盖；下表是基于原证据及本轮不可变SDK请求快照的新增派生统计。','',
        '|观测位置/定义|修复前历史|修复后历史或本轮|分母|', '|---|---|---|---|',
        '|Tool payload具有answer_guidance字段|16|26|26题；原非usable结果已有该字段|',
        '|原boundary_delivered复合公式|0|26|26题；BASE_RULES子串均在首个SDK system且RAG guidance含事实充分|',
        '|本轮实际构造system prompt具备BASE_RULES|未另测|26|26构造；构造不等于调用|',
        '|本轮实际调用Support SDK|未另测|26|26题；52个Support请求|',
        '|本轮所有Support SDK请求system含BASE_RULES|未另测|52|52实际请求|',
        '|最后一个Support SDK请求system有BASE_RULES|未另测|26|26实际调用题|',
        '|RAG guidance存在于最终SDK tool_result消息|未另测|26|26实际调用题|',
        '|原26题确定性门绕过模型|未另测|0|26题|', '',
        'ANS-24精确冻结Query：explicit_handoff=false，Support SDK调用2次、未建新记录，最终SDK实际含基础规则和RAG guidance。因此无需把历史分母改为25；26/26可以保留为复合规则送达指标。',
        '相近规则问句和显式请求控制：确定性门命中，SDK=0；不加入26题分母，也不得称模型收到规则。它们不是对原Query的替换。未来指标只以实际SDK调用题作分母，另报确定性分支数量。',
        '范围是Support回答SDK；RAG rewrite/rerank SDK是其他阶段，不声称所有SDK步骤都收到回答规则。Fake选择RAG/Provider是脚本指定，不能用于评估真实模型工具选择正确率。',
        'SDK快照在调用边界deepcopy，避免BaseAgent后续append工具结果污染首个请求的观测。sdk_delivery_actual.json保留每个实际Fake请求和Trace。',
        '该统计不是模型遵循率或回答准确率。原句中正确否定说明被代码后处理删掉，说明“模型已收到规则”与“最终API答复正确”还受不同阶段影响。']
    (OUT/'delivery_metrics.md').write_text('\n'.join(delivery)+'\n',encoding='utf-8')
    selected_ids = ['ANS-01','ANS-05','ANS-08','ANS-09','ANS-10','ANS-12','ANS-14','ANS-15','ANS-19','ANS-21','ANS-22','ANS-23']
    selected = [next(c for c in gold['cases'] if c['id']==id) for id in selected_ids]
    candidate_plan = {'status':'proposal_only_unapproved_not_executable','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'candidate_gold_sha256':hashlib.sha256((base/'dataset_v1.review_candidate.json').read_bytes()).hexdigest(),
        'case_ids':selected_ids,'cases':selected,'separate_cases':['ANS-16','ANS-17','ANS-18','ANS-20','ANS-24'],
        'future_required_freeze':'after human Gold decisions, bind approved inputs/evaluator/source/image/fixture/model/config/budgets BEFORE model calls',
        'no_model_calls_this_turn':True,'no_final_gold_freeze':True,
        'budget_proposal':{'typical_logical_model_requests_range':[36,48],'whole_run_logical_model_request_cap':96,
            'per_case_model_request_cap':10,'input_tokens_total_cap':300000,'output_tokens_total_cap':60000,
            'fee_cap_usd':.50,'estimated_peak_cache_miss_cost_at_caps_usd':.162,'sdk_retries':0,
            'connect_timeout_s':5,'read_timeout_s':60,'chat_case_timeout_s':120,
            'parallel_cases':1,'guard_implementation':'not implemented; separate approval/preparation required'},
        'pricing_source':'https://api-docs.deepseek.com/quick_start/pricing/',
        'pricing_checked_date':'2026-10-14','peak_usd_per_million_tokens':{'input_cache_miss':.30,'output':1.20}}
    (OUT/'e2e_candidate_protocol.json').write_text(json.dumps(candidate_plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    plan = f'''# 真实/chat E2E：只读预检与候选方案（blocked）

核验HEAD `{integrity['head']}`；本轮真实模型、API启动、镜像构建、Docker exec、Embedding下载、正式E2E均为0。原.35阈值、知识及权限不改。

## 环境核验

|项|本轮实际结果|进入下一轮条件|
|---|---|---|
|API|echomind-app exited/running=false；127.0.0.1:8000拒绝连接|保持停止，禁止直接启动旧镜像|
|旧镜像|created=2026-09-27T04:35:23Z，image `{env['image']['id']}`；OCI revision缺失|新构建并保存源码/image digest/构建时间；本轮未构建|
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

{', '.join(selected_ids)}。

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
'''
    (OUT/'e2e_preflight_and_plan.md').write_text(plan,encoding='utf-8')
    print('four review deliverables written; Gold remains pending, E2E blocked')


if __name__=='__main__':
    main()
