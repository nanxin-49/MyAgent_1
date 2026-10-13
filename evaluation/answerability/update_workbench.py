"""Update only existing Workbench A05 state; do not accept earlier work."""
import html
import json
from evaluation.answerability.harness import ROOT


def main():
    path = ROOT/'docs/cartcare-workbench-progress.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    task = data['tasks']['A05']
    assert task['stages']['DEFAULT-KB-PUBLICATION']['status']=='verify'
    assert task['stages']['A05-SKILLS-CONSISTENCY']['status']=='verify'
    assert task['stages']['A05-B1']['status']==task['stages']['A05-B1-PREP']['status']=='blocked'
    assert 'A05-ANSWERABILITY' not in task['stages']
    evidence = 'evaluation/answerability/; tests/test_answerability_boundary.py; evaluation/reports/hardening/A05/answerability-20261013/'
    note = ('2026-10-13 A05-ANSWERABILITY=verify/partial，人工验收与Gold审核pending。'
        'HEAD=20ad905875d5ffc539752982faa16f3775fee1ea，起始干净；核对usable仅检索来源/分数/生命周期有效，不代表事实充分或逐句grounding。'
        '独立26题在检索前按批准六正文冻结；Fake cosine存储+实际KnowledgeBase/N06/N07/Tool/Provider/SkillManager/Single/Fake SDK，非live Chroma或真实/chat。'
        '红测初始12/3含publishing测试预期误写，按代码纠正Gold18勘误并只读HEAD复跑仍12 failed/3 passed；保留原日志/数据hash。'
        '仅agents/tools.py answer_guidance与Single基础提示词最小补充逐事实/原始问题/部分回答/有依据的能力拒绝/动态Provider/故障区别，状态契约不变，无关键词判题。'
        '规则送达0/26→26/26，原候选/status/citation/Provider及脚本输出逐题相同；10 usable/12 low/3 no_answer/1 degraded，11Gold低分过滤，.35不改。'
        '刻意忽略规则的Fake25/26仍含预设错误承诺（非模型错误率）；未实现自动充分性/逐句核验，整体问题未解决，真实模型遵循待后续单独审核。'
        '15专项、187关联、全量513 passed/3 skipped/1既有AnyIO警告，lock53/diff通过。'
        'Docker API不可达，Chroma heartbeat/API TCP probe超时；零API启动尝试、零collection访问/写入、零付费模型或真实/chat E2E。'
        '批准正文/默认库/Policy/ActionService/Provider权限/历史Gold/B0/B1不改，不下载模型/提交推送。'
        'README/核心Wiki无调用链漂移，新增逐题材料及独立练习见本轮REPORT.md。'
        'DEFAULT-KB-PUBLICATION数据层与A05-SKILLS-CONSISTENCY运行时审核建议通过，用户正式确认前仍verify，不自行done；A05 doing/partial，B1/B1-PREP blocked。')
    task['status'],task['outcome'],task['issue_id']='doing','partial','A05-ANSWERABILITY'
    task['issues']['A05-ANSWERABILITY']='partial'
    task['stages']['A05-ANSWERABILITY'] = {'status':'verify','outcome':'partial',
        'evidence':evidence,'gold_human_review':'pending','cases':26,
        'scope':'deterministic boundary delivery repaired; semantic sufficiency and final grounding unverified',
        'red':'12 failed / 3 passed (corrected tests against original HEAD modules)',
        'targeted':'15 passed; related 187 passed','full_regression':'513 passed / 3 skipped / 1 warning',
        'min_score':.35,'added_model_calls':0,'real_model_tested':False,'real_chat_e2e_tested':False,
        'api_started_by_task':False,'default_collection_accessed':False,
        'live_environment':'Docker API unreachable; Chroma heartbeat and API TCP probe timeout',
        'next_gate':'human Gold+ANS-18 erratum / deterministic acceptance; separately authorize current-image real-model /chat E2E'}
    task['stages']['A05-SKILLS-CONSISTENCY']['runtime_acceptance_recommendation']='suggested_pass_pending_explicit_user_confirmation_before_done'
    task['evidence'] += '; '+evidence
    task['note'] += '\n'+note
    data['updatedAt']='2026-10-13'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    path = ROOT/'docs/CartCare-Codex-Workbench.html'
    content = path.read_text(encoding='utf-8')
    anchor = '<h3>A05 / N06、N07、P1 · 知识契约与冻结检索基线</h3>'
    assert content.count(anchor)==1
    content = content.replace(anchor,anchor+'\n        <p>'+html.escape(note)+'</p>',1)
    start = content.index('<article class="task-card" data-task="A05">')
    end = content.index('</article>',start)
    card = content[start:end]
    # Add evidence/current note without rewriting historical entries.
    marker = '<input data-field="evidence" value="'
    pos = card.index(marker)+len(marker)
    close = card.index('"',pos)
    card = card[:close]+'; '+html.escape(evidence,quote=True)+card[close:]
    closing = '</textarea>'
    assert card.count(closing)==1
    card = card.replace(closing,'\n'+html.escape(note)+closing,1)
    path.write_text(content[:start]+card+content[end:],encoding='utf-8')


if __name__=='__main__':
    main()
