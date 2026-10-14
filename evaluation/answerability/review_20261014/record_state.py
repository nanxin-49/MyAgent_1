"""Record review/preflight only in existing Workbench; preserve acceptance gates."""
import hashlib
import html
import json
import subprocess

from evaluation.answerability.review_20261014.probe import ROOT, OUT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT/'docs/cartcare-workbench-progress.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    task = data['tasks']['A05']
    stages = task['stages']
    assert (task['status'],task['outcome'])==('doing','partial')
    assert stages['A05-ANSWERABILITY']['status']=='verify' and stages['A05-ANSWERABILITY']['outcome']=='partial'
    assert stages['DEFAULT-KB-PUBLICATION']['status']==stages['A05-SKILLS-CONSISTENCY']['status']=='verify'
    assert stages['A05-B1']['status']==stages['A05-B1-PREP']['status']=='blocked'
    assert 'A05-ANSWERABILITY-GOLD-REVIEW' not in stages
    evidence = 'evaluation/reports/hardening/A05/answerability-gold-review-20261014/; evaluation/answerability/review_20261014/'
    note = ('2026-10-14 A05-ANSWERABILITY-GOLD-REVIEW审核材料verify，Gold人工pending；E2E preflight=blocked。'
        'HEAD=1fd93b5a4372dccb03e9bb8ad0f8647358b28fad，起始干净；仅核验和新增报告/Fake探针，不修生产代码。'
        '26题完整、原/candidate/freeze/addendum/历史manifest hash均匹配，候选唯一差异ANS18 allowed_boundary；原数据保留。'
        '22题建议通过，07总额仅补充不是实付/渠道部分命中，13需明确实时位置不可核验，18勘误、24只读问法/路由边界待用户裁决。'
        'ANS24原句确定性门不命中，SDK2次/新记录0；26原题全部调用Support SDK（52请求）并实际含规则，guidance字段存在历史16→26，原复合指标0→26成立但非模型质量。'
        '相近规则问句“是否说明已转人工客服”误命中门，SDK0/模拟records0→1；原句正确否定解释被文字保护删除。'
        '独立登记A05-ANS24-ROUTE/REPLY known_open；最小安全红测2 failed/1 passed，既有相关58 passed/1警告，不修改路由等待另授权。'
        '只读预检API exited/8000拒绝连接；旧镜像2026-09-27构建，与当前关键源码hash不同且缺Single/Handoff/审批资产，禁止启动。'
        'Chroma/Redis healthy，default6ready/6有效/12物理、六正文metadata审批匹配，snapshot未变；Redis只PING，无业务key读取/写入。'
        '本地deepseek-flash/Anthropic0.40配置官方兼容基址，DNS/TCP443通过、仅key存在未验证；Auth默认deny无Demo身份；新版镜像/隔离Auth/SDK限额未准备。'
        '12题E2E候选和分阶段归因/预算只提案未获准，16/17/18、20、24分别隔离；无最终Gold freeze。'
        '零模型请求/服务启动/构建/下载/真实E2E/知识写入/生产配置修改/提交推送。'
        '四份材料含Gold矩阵、重点路由、SDK统计、E2E预检预算及独立练习；lock53/diff通过。'
        'A05 doing/partial、Answerability verify/partial，B1/B1-PREP blocked，DEFAULT-KB-PUBLICATION/SKILLS正式确认前仍verify。')
    stages['A05-ANSWERABILITY-GOLD-REVIEW']={'status':'verify','outcome':'implemented','scope':'review materials and isolated preflight only',
        'gold_approval':'pending','gold_suggested_pass_cases':22,'gold_user_decision_cases':['ANS-07','ANS-13','ANS-18','ANS-24'],
        'evidence':evidence,'routing_expected_safe_tests':'2 failed / 1 passed (confirmed open defects; no repair)',
        'related_regression':'58 passed / 1 existing warning','production_code_modified':False,'real_model_calls':0}
    stages['A05-ANSWERABILITY-E2E']={'status':'blocked','phase':'preflight','outcome':'not_started','evidence':evidence,
        'blockers':['Gold human approval and four decisions pending','A05-ANS24-ROUTE/REPLY confirmed open; repair authorization pending',
            'old stopped API image does not match current source','isolated Demo Auth/Memory/business/new runtime not prepared',
            'model/budget/timeout/retry authorization and limits pending'],'candidate_cases':12,'execution_authorized':False}
    for id,priority in [('A05-ANS24-ROUTE','P1'),('A05-ANS24-REPLY','P2')]:
        task['issues'][id]='deferred/known_open'
        stages[id]={'status':'todo','outcome':'deferred/known_open','priority':priority,
            'observed':'Fake/TestClient with independent process-local business/handoff state',
            'fix_authorized':False,'evidence':evidence}
    task['issues']['A05-ANSWERABILITY-GOLD-REVIEW']='implemented'
    task['issue_id']='A05-ANSWERABILITY-GOLD-REVIEW'
    task['note'] += '\n'+note
    task['evidence'] += '; '+evidence
    data['updatedAt']='2026-10-14'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    path = ROOT/'docs/CartCare-Codex-Workbench.html'
    raw = path.read_text(encoding='utf-8')
    anchor = '<h3>A05 / N06、N07、P1 · 知识契约与冻结检索基线</h3>'
    assert raw.count(anchor)==1
    raw = raw.replace(anchor,anchor+'\n        <p>'+html.escape(note)+'</p>',1)
    start = raw.index('<article class="task-card" data-task="A05">')
    end = raw.index('</article>',start)
    card = raw[start:end]
    pos = card.index('<input data-field="evidence" value="')+len('<input data-field="evidence" value="')
    close = card.index('"',pos)
    card = card[:close]+'; '+html.escape(evidence,quote=True)+card[close:]
    card = card.replace('</textarea>','\n'+html.escape(note)+'</textarea>',1)
    path.write_text(raw[:start]+card+raw[end:],encoding='utf-8')
    before = json.loads((OUT/'protected_before.json').read_text(encoding='utf-8'))
    changes = [f for f,h in before.items() if not (ROOT/f).exists() or sha(ROOT/f)!=h]
    allowed = {'docs/CartCare-Codex-Workbench.html','docs/cartcare-workbench-progress.json'}
    assert set(changes)==allowed,changes
    artifacts = [p for p in OUT.iterdir() if p.is_file() and p.name!='validation.json']
    validated = {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tracked_files_checked':len(before),'changed_existing_files':changes,'unexpected_changes':[],
        'all_production_code_historical_Gold_B0_B1_knowledge_Skills_unchanged':True,
        'new_report_hashes':{p.name:sha(p) for p in artifacts},
        'related_tests':{'command':'uv run python -m pytest -q tests/test_answerability_boundary.py tests/test_handoff.py tests/test_runtime_skills_consistency.py',
            'passed':58,'failed':0,'warnings':1},
        'new_expected_safe_routing_tests':{'passed':1,'failed':2,'outcome':'confirmed_unfixed; intentionally explicit-only regression probes'},
        'full_regression_rerun':False,'reason':'no production changes; only focused isolated probes and additive review docs',
        'uv_lock_check':'passed (53 packages)','git_diff_check':'passed','Gold_approved':False,'services_started':False,
        'real_model_calls':0,'new_default_collection_writes':0,'commit_or_push':False}
    (OUT/'validation.json').write_text(json.dumps(validated,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tracked_files_checked':len(before),'changed':changes,'E2E':'blocked','Gold':'pending'},ensure_ascii=False))


if __name__=='__main__':
    main()
