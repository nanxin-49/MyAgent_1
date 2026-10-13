"""Produce review tables from immutable observations; never tune or grade prose."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from evaluation.answerability.harness import BASE, ROOT, load_dataset
from mcp.default_knowledge_asset import load_approved_defaults

REPORT = ROOT/'evaluation/reports/hardening/A05/answerability-20261013'

REPORT_TEXT = """# A05-ANSWERABILITY — verify / partial

2026-10-13；起始HEAD `20ad905875d5ffc539752982faa16f3775fee1ea`，起始工作区干净。只完成可独立验证的回答边界送达修复，没有实现逐句语义判定器，没有证明模型回答正确。

## 当前调用链与六类概念

`/chat → Memory.get_context → SupportRuntime.run → SingleSupportAgent/BaseAgent → execute_tool → agents.tools.search_knowledge_base → MCPToolManager.search_with_rewrite → KnowledgeBase.search/_eligible/build_hit → N07._finalize_rag/N06.validate_hits_async → tool_result → Agent文本 → Memory写入 → collect_rag_evidence/render_rag_citations → API`。

调用链前后相同；无新Agent、路由、业务Gate或模型步骤。

|概念|实际实现与边界|
|---|---|
|retrieval relevance|char-bigram-1024-v1、Chroma distance、score=1-distance、min_score=.35；改写/重排优化检索；不是概率，也不验证所问事实。|
|lifecycle validity|N06 publishing/ready完整片段、active、effective_at/expires_at、supersedes；Top-K前筛选，N07后再次校验；citation绑定来源、版本、content_hash。|
|evidence sufficiency|原路径没有按问题具体事实的自动判定。现增加基础提示词与工具answer_guidance，要求生成时逐项核对；这仍是指令约束。|
|answer grounding|引用校验验证片段出处和完整性；未实现最终每句话与证据的蕴含/充分性校验。API knowledge_used=bool(citations)，不是逐句grounded。|
|normal no-answer|有效召回为空→success=true/no_answer；候选低分→success=true/low_confidence；Agent results/citations=[]。不证明事实不存在。|
|dependency failure|Chroma异常/元数据损坏/校验故障等→success=false/degraded；Provider依赖失败→typed dependency_failure，与公开not_found不同。|

`usable`的真实含义：分数合格、合法且当前有效的非空片段/引用，N07最终结果属于原候选并经N06复核。它允许提供检索材料，不是“足以回答用户问题”的布尔值。未改变任何status、success、hits或citation语义。

合法publishing记录但没有有效片段，当前代码返回正常no_answer；不能从publishing本身推断依赖故障。冻结Gold ANS-18一句误写已在gold_review_v1.md勘误，原始dataset/hash/红测保留，人工审核仍pending。

## 独立数据与测量范围

`evaluation/answerability/dataset_v1.json`：26题、10类要求均覆盖。逐题包含query、必要事实、直接引文/来源/hash、Gold行为、未知事实、允许边界、禁止承诺、隔离情景、动态工具及参数。`freeze_v1.json`在检索前冻结dataset及批准asset hash；没有从历史Gold v2/B0/B1导入或调题。

`gold_review_v1.md`：逐题人工勾选清单与ANS-18勘误；尚未人工批准。`dataset_v1.review_candidate.json`仅修正该题allowed_boundary，保留全部query/必要事实/引文/Gold行为/场景不变；review_addendum.json绑定原冻结hash和候选hash，明确是测量后的代码契约勘误，不是Gold重标或调题。原dataset/freeze不覆盖。`corpus_snapshot.json`是六篇审批正文的内容副本，不是新增生产知识。未修改批准asset/审批metadata。

真实Python模块与真实Tool Contract、KnowledgeBase、N06/N07、Provider权限、SkillManager、SupportRuntime都执行；存储是隔离Fake cosine collection，SDK为脚本化原查询rewrite及刻意忽略规则的回答。不是live Chroma、ANN/float32质量或真实模型测试；没有真实/chat HTTP E2E。本轮2次支持SDK调用/题与脚本rewrite调用不产生费用。多数题显式包含知识标题，用于隔离“主题相关但所问事实不足”及合同边界；这些题不是自然流量分布，不能外推总体召回质量。

Docker API不可达，127.0.0.1:8001只读heartbeat超时，8000 TCP probe超时。没有启动服务、没有默认collection访问或写入。不能依据端口超时独立确认容器状态；本轮API启动尝试为0。environment_before/after.json保存原始错误。

## 修复前逐题结果与归因

详见before.json（原始SDK输入、检索候选、Provider回执、Trace与脚本回答），per_case.md与comparison.csv。

- 最终检索状态10 usable / 12 low_confidence / 3 no_answer / 1 degraded。
- 活跃Gold片段均在Fake Top5原始候选内；11题目标片段被.35过滤。另有无Gold的ANS-22低分，不能计入Gold漏召回。
- ANS-05（具体到账）、08（审核+到账）、09（积分比例）、10（金卡会费）均有usable相关正文，但具体数字/时效未给出；正文支持的是能力/证据边界。不能把这种边界回答误记为“事实数值有答案”。
- ANS-12的订单状态必须来自get_order而非static正文；其他动态题即便静态候选低分，Provider仍独立查询。公开not_found不区分缺记录与跨用户；ANS-21 Provider依赖故障不变成知识不足。
- 16/17/18独立Fake lifecycle变体不可引用；不是真实默认库被修改或旧版泄漏。
- Skill中的业务边界在本轮前已修复；当前缺口是基础提示词/成功RAG payload未解释usable与事实充分性的区别。Fake不能证明Skill实际诱导了某个真实模型错误，只能记录发送内容。
- 20 Chroma故障为degraded；22正文无该事实为正常知识不足。23/24分别检验模拟动作与资金、模拟记录与真人的差异，不执行真实资金/接单。

## 最小修改与技术取舍

仅修改运行时`agents/tools.py`与`agents/support_agent.py`：

1. 在既有answer_guidance字段为usable结果补充分数/生命周期不等于事实充分，按原始问题逐项寻找直接依据；混合问题只回答已支持部分；允许引用明确“不支持该功能”的正文。
2. 区分正常无证据与依赖故障的指令。保留原success/status和空results/citations；未初始化RAG也明确依赖不可用。
3. 在Single基础提示词追加通用规则，不依赖Skill命中。动态事实必须使用有权限Provider，Skill只是流程指令；模拟动作/交接不能升级为真实资金/接单事实。

判断放在Agent读到工具材料之后，因为问题的限定条件、多个事实与动态工具回执在这里汇合。没有添加新的模型判断服务，未引入“sufficient=true”之类伪认证字段。检索层继续只负责检索与版本有效性。

避免误拒：不按“包含退款/积分”等词拦截、不按整个query一票拒绝、不删除usable证据；明确能力不存在也是可引用事实，混合问题允许部分回答。多个必要事实须各自有依据，而不是用一个片段/引用覆盖全部结论。

成本：新增模型调用0；追加提示词和payload文字会增加既有调用输入tokens，真实增量未测。生产仍保留原有rewrite与条件式rerank调用，不能声称整个生产RAG零模型调用。

兼容：原有usable/low_confidence/no_answer/degraded、success、Provider公开错误、Policy、ActionService、权限与citations不变；仅扩展已存在的answer_guidance及Single系统提示词。无业务政策或响应字段删除。

更强的语义充分性/grounding判断需另审：可以在既有生成步骤输出逐事实support映射，但那需要结构化生成契约、合法引用/摘录验证、缺失/矛盾/多事实聚合与失败模式设计；摘录存在只能确定性证明字面出处，仍不能保证蕴含。单独判定模型会增加一次调用、时延与成本，且不是确定性安全门。按本轮限制不实施这部分。

## 修复后逐题对照与验收边界

after_final.json与comparison.csv保存26题完整对照：边界规则送达0/26→26/26；raw hits、RAG原字段、Provider结果、脚本输出逐题完全相同。此指标是规则送达，不是答案准确率、Task Success或FPR改善。

刻意忽略规则的Fake SDK在25/26题仍留下预设错误承诺，前后相同；ANS-24被既有handoff文字门处理，与本轮修复无关。这个压力测试揭示本轮不会强制验证自由文本，不能据此推算真实模型错误率。完整问题仍未解决；本项建议verify，outcome=partial，验收可核对确定性接线与材料，真实回答质量等待独立授权。

|验收要求|证据与结论|
|---|---|
|基线调用链与usable语义|本报告、原始26题SDK输入及Trace；调用链不变。|
|独立Gold与事实边界|dataset/freeze/逐题Gold清单；人工pending，18含明确勘误。|
|先测再改|before.json；修复前12 failed/3 passed；纠正publishing测试后只读加载HEAD模块复测仍12 failed/3 passed。|
|最小可验证修复|15专项通过、187关联通过；规则送达而非语义保证。|
|保护约束|保护文件hash/最终preservation.json；全部历史评测、六正文、.35、业务/权限代码保留。|
|后续模型验收|未执行；无真实模型或真实/chat结论。|

## 回归与复现

Python3.12.3、uv、原HEAD；完整日志保留。

- `uv run python -m evaluation.answerability.harness --output <新的输出路径>`：独立Fake逐题复现，已存在输出拒绝覆盖。
- `uv run python -m evaluation.answerability.run_head_red`：只读HEAD原两个模块复跑当前专项，12 failed/3 passed；没有回滚文件。
- `uv run python -m pytest -q tests/test_answerability_boundary.py`：15 passed。
- Answerability/RAG/N06/N07/Skills/Provider/Single/Handoff关联组：187 passed、1既有AnyIO警告。
- `uv run python -m pytest -q`：513 passed、3 skipped、1既有AnyIO警告。skip分别Memory live与2条Chroma HTTP；未弱化测试范围。
- `uv lock --check`：53 packages；`git diff --check`通过。

red.txt保留初始12/3（其中publishing预期写错）；red_corrected_head.txt保留修正后的12/3；green.txt保留首次3 failed/12 passed（同一预期错误和非usable payload规则覆盖不全）；targeted_final.txt/full_regression.txt是最终绿色结果。

## 未解决风险与后续真实/chat条件

未解决：模型忽略规则、遗漏必要事实、将原文否定/边界读反、错误引用、混合题过度回答、未调用Provider仍猜动态事实、原.35漏证据、rewrite变更问题焦点。无runtime逐句强制grounding门，长会话/注入/真实模型拒答率也未验证；不宣称业务安全或质量已通过。

后续必须另获真实模型及/chat E2E授权和人工Gold确认（含18勘误）；为该轮构建包含本修复、已修Skills与批准六正文的当前镜像/环境，先审镜像源码/HEAD/hash，再按停止服务后的新启动授权运行，不能启动旧API镜像。

需要可用Chroma HTTP与Redis、只读核验默认库6 ready publication/6有效chunk及审批hash、Python3.12/uv锁一致、demo loopback认证与customer/reviewer/admin凭据、安全隔离会话和模拟业务状态、无真实支付或真人通知接入。明确模型/API endpoint、调用/Token/费用上限、运行时内存、最大重试与超时、Trace原始输出及逐事实人工审核；记录已知阈值漏召回，不为了验收改.35。此轮条件不等于新的启动/模型费用授权，也不解锁B1。

## 文档与任务状态

现有Workbench/progress更新本项verify/partial；A05整体doing/partial、B1与B1-PREP blocked。DEFAULT-KB-PUBLICATION和A05-SKILLS-CONSISTENCY仅获得建议通过，正式用户确认前保持verify。

README/核心定位Wiki/重点代码已说明来源引用不等于逐句事实核验，架构与调用链未变，无需本轮扩大维护；其他Wiki不修改。历史Workbench备注按当时快照解读；最新记录补充本轮规则和风险。

独立练习（无需Codex）：运行专项test_usable_never_certifies_fact_sufficiency，手工阅读ANS-08正文引文及before.json结果，分别标出“有依据的审核条件”和“未知的到账时间”，解释为什么usable及引用hash都合法而仍不能给到账日期；再独立核对ANS-18的_eligible分支为什么是no_answer。

建议commit：`fix: clarify RAG answerability and evidence boundaries`。没有提交或推送代码。
"""


def main():
    data = load_dataset()
    candidate = json.loads(json.dumps(data))
    original18 = candidate['cases'][17]['allowed_boundary']
    candidate['cases'][17]['allowed_boundary'] = '只在隔离fixture设置publishing；不可引用未ready版本；合法publishing无有效chunk为no_answer，不自动判依赖故障。'
    assert candidate['cases'][17]['id']=='ANS-18'
    for original,corrected in zip(data['cases'],candidate['cases']):
        assert {k:v for k,v in original.items() if k!='allowed_boundary'}=={k:v for k,v in corrected.items() if k!='allowed_boundary'}
        if original['id']!='ANS-18':
            assert original==corrected
    candidate_path = BASE/'dataset_v1.review_candidate.json'
    candidate_path.write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (BASE/'review_addendum.json').write_text(json.dumps({
        'review_status':'pending','original_frozen_sha256':hashlib.sha256((BASE/'dataset_v1.json').read_bytes()).hexdigest(),
        'review_candidate_sha256':hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        'correction_phase':'after baseline measurement; source-contract correction only, no query/label/score tuning',
        'change':{'id':'ANS-18','field':'allowed_boundary','before':original18,
                  'after':candidate['cases'][17]['allowed_boundary']},
        'source':'mcp/knowledge_base.py:_eligible/search; mcp/tool_manager.py:search_with_rewrite',
        'unchanged':'queries, necessary facts, evidence, gold_behavior, scenarios and all other case fields'},
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    before = json.loads((REPORT/'before.json').read_text(encoding='utf-8'))['rows']
    after = json.loads((REPORT/'after_final.json').read_text(encoding='utf-8'))['rows']
    assert [r['id'] for r in before]==[c['id'] for c in data['cases']]==[r['id'] for r in after]
    for b,a in zip(before,after):
        assert b['raw_hits']==a['raw_hits']
        assert {k:v for k,v in b['rag_payload'].items() if k!='answer_guidance'}=={
            k:v for k,v in a['rag_payload'].items() if k!='answer_guidance'}
        assert b['provider_payload']==a['provider_payload']
        assert b['scripted_adversarial_reply']==a['scripted_adversarial_reply']
    table = ['|ID|原始问题|Gold行为|前/后检索状态|原始/可用目标召回|归因|前→后规则送达|',
             '|---|---|---|---|---|---|---|']
    review = ['# A05 Answerability Gold 审核清单', '',
        '作者：Codex；人工审核待完成。不是既有 Gold v2 的续版，不用历史题目或分数调参。', '',
        '人工审核使用dataset_v1.review_candidate.json及review_addendum.json；原始dataset_v1/freeze保留为测量前冻结。',
        '先读六篇批准正文（内容快照 corpus_snapshot.json 与批准asset哈希一致），再逐项核对下列必要事实、正文引文与允许/禁止边界。', '',
        '**ANS-18 勘误**：冻结dataset_v1的allowed_boundary末句误写publishing属于依赖不可用。',
        '现有KnowledgeBase._eligible排除未ready发布，合法publishing且无有效chunk→[]，ToolManager→success=true/no_answer。',
        '正确Gold：不可引用未发布版本；未ready本身不证明依赖故障。损坏manifest/Chroma请求异常才可能degraded。',
        '原数据/hash、原红测和首次修复尝试均保留；审核ANS-18须使用本勘误，不迁就错误预期改生产状态。', '',
        '每题人工确认：事实粒度完整；quote来自批准正文；否定能力也可有依据；动态事实必须Provider；',
        '混合问题逐项区分已知/未知；不把阈值漏召回当事实不存在；不把故障当无答案；不外推真实商城/资金/真人能力。', '']
    rows = []
    for c,b,a in zip(data['cases'],before,after):
        status = a['rag_payload']['retrieval_status']
        causes = []
        if c['scenario'] in {'expired','future','publishing'}:
            causes.append('lifecycle_not_current_or_not_ready')
        elif c['scenario']=='chroma_failure':
            causes.append('chroma_dependency_failure')
        elif c['available_evidence'] and not a['gold_raw_recalled']:
            causes.append('gold_not_recalled')
        elif a['gold_raw_recalled'] and not a['gold_usable_recalled']:
            causes.append('gold_threshold_filtered')
        if c['unavailable_facts']:
            causes.append('specific_facts_not_in_current_bodies')
        if c['dynamic_tool']:
            causes.append('dynamic_provider_required')
        if c['scenario']=='provider_failure':
            causes.append('provider_dependency_failure')
        if c['gold_behavior']=='supported_boundary':
            causes.append('explicit_capability_or_evidence_boundary_is_answerable')
        if not causes:
            causes.append('supported_static')
        causes.append('original_prompt_or_payload_did_not_explain_usable_sufficiency_boundary')
        row = {'id':c['id'],'query':c['query'],'gold_behavior':c['gold_behavior'],
            'before_status':b['rag_payload']['retrieval_status'],'after_status':status,
            'gold_raw_recalled':a['gold_raw_recalled'],'gold_usable_recalled':a['gold_usable_recalled'],
            'attribution':'; '.join(causes),'before_boundary_delivered':b['boundary_delivered'],
            'after_boundary_delivered':a['boundary_delivered'],
            'prose_semantic_verdict':'not_measured_adversarial_fake',
            'provider_result_code':(a['provider_payload'] or {}).get('error',{}).get('code','')}
        rows.append(row)
        table.append(f"|{c['id']}|{c['query']}|{c['gold_behavior']}|{status} → {status}|{a['gold_raw_recalled']}/{a['gold_usable_recalled']}|{' / '.join(causes[:-1]) or 'supported_static'}|{b['boundary_delivered']} → {a['boundary_delivered']}|")
        review.extend([f"## {c['id']} — {c['query']}", '', '- [ ] 人工确认或明确修订理由',
            f"- 必要事实：{'；'.join(c['necessary_facts'])}",
            f"- Gold：{c['gold_behavior']}；未知事实：{'；'.join(c['unavailable_facts']) or '按限定范围核验'}",
            f"- 允许边界：{c['allowed_boundary'] if c['id']!='ANS-18' else '不可引用未ready版本；合法publishing无有效chunk为no_answer，不自动判依赖故障。'}",
            f"- 禁止承诺：{'；'.join(c['forbidden_promises'])}"])
        for evidence in c['available_evidence']:
            review.append(f"- 正文依据：{evidence['document_id']} / {evidence['source']} / {evidence['content_sha256']}：{evidence['quote'] or '仅生命周期隔离变体；不提供当前可引用事实'}")
        if c['dynamic_tool']:
            review.append(f"- 动态依据：{c['dynamic_tool']} {json.dumps(c['dynamic_args'])}；tests/fixtures/business_provider_data.json（模拟数据）。实际Provider回执见逐题JSON。")
        review.append('')
    with (REPORT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (REPORT/'per_case.md').write_text('# 逐题对照（规则送达，不是回答正确率）\n\n'+ '\n'.join(table)+'\n',encoding='utf-8')
    (BASE/'gold_review_v1.md').write_text('\n'.join(review),encoding='utf-8')
    (REPORT/'corpus_snapshot.json').write_text(json.dumps(load_approved_defaults(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary = {'cases':26,'scope':'deterministic actual Python path, Fake Chroma cosine + Fake SDK only',
        'before_boundary_delivered':sum(r['boundary_delivered'] for r in before),
        'after_boundary_delivered':sum(r['boundary_delivered'] for r in after),
        'retrieval_statuses':dict(Counter(r['rag_payload']['retrieval_status'] for r in after)),
        'raw_results_rag_fields_provider_results_scripted_prose_unchanged':True,
        'expected_evidence_cases':sum(bool(c['available_evidence']) for c in data['cases']),
        'gold_not_recalled_active':sum('gold_not_recalled' in r['attribution'] for r in rows),
        'gold_threshold_filtered':sum('gold_threshold_filtered' in r['attribution'] for r in rows),
        'model_obedience_measured':False,'real_chat_e2e':False,'real_model_calls':0,
        'added_model_calls':0,'incremental_prompt_token_cost':'not_measured; longer existing prompts/payloads increase tokens',
        'adversarial_fake_unsafe_phrase_persisted':sum(c['forbidden_promises'][0] in r['scripted_adversarial_reply'] for c,r in zip(data['cases'],after)),
        'adversarial_fake_denominator':26,'not_a_model_performance_rate':True,
        'ANS-18_gold_erratum':'legal publishing is no_answer not automatically degraded; frozen original kept',
        'gold_human_review':'pending'}
    (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (REPORT/'REPORT.md').write_text(REPORT_TEXT,encoding='utf-8')
    inputs = [BASE/'dataset_v1.json',BASE/'freeze_v1.json',BASE/'dataset_v1.review_candidate.json',BASE/'review_addendum.json',BASE/'gold_review_v1.md',
              BASE/'harness.py',ROOT/'agents/tools.py',ROOT/'agents/support_agent.py']
    (REPORT/'final_inputs_sha256.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
