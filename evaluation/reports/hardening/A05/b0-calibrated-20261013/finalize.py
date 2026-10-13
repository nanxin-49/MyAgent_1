"""Record existing Workbench state and verify authorized artifact-only changes."""
import html
import json
from pathlib import Path
import re
import subprocess
from evaluation.rag_quality import run_baseline as b

OUT = Path(__file__).resolve().parent
REL = str(OUT.relative_to(b.ROOT)).replace('\\', '/')
NOTE = '''2026-10-13 A05-P2-B0-CAL=measured/verify，待人工验收；A05继续doing/partial，B1不执行。HEAD=8cefc6c3e24230177c1db6dbb54f2e45f1c86f23，起始干净。冻结test30题21/9、Gold/approved candidate、corpus/dev/freeze/开发锁及代码依赖hash全部保持；正式freeze记录全集用户人工批准，非独立双人/盲审，不自行新增人工通过。真实Chroma HTTP0.5.23，独立create-only随机集合；11ready publication/11物理7有效chunk，内容hash/存储float32向量逐一匹配，7个HTTP自检均rank1；snapshot与校准锁、原B0 chunk/有效ID一致，集合已清理。默认业务集合6旧格式记录0publication/0有效，缺content_hash，实际search报legacy knowledge requires reviewed republication；正文等于冻结6篇默认资料，但不代表默认库有效，前后只读snapshot不变，另行可信审核重发布待办，本轮不迁移。仅一次正式test30 query，char-bigram1024/Top5/锁定0.20/as_of固定，Rewrite/Rerank/Cache/LLM关、模型0。Recall1/3/5=9/21、MRR=.4286、FPR=8/9、引用精度9/17；原.35分别6/21、.2857、4/9、6/10；rawRecall5同18/21，两轮原B0与本轮全部候选顺序和完整分数一致，10个检索/指标函数AST及生产sourcehash相同。增正确13/14/15，增误报27–30；失败3未召回、9Gold低分过滤（0有效性剔除）、8主题相关但事实不足的无答案usable；27–30没有旧版本泄漏，现行v2缺所问事实。无新Gold冲突、沿用当前有效ready/单Gold口径；不做test调参或推广生产阈值。P50/P95=32.60/38.71ms，有预检probe、不能作延迟因果结论。193专项、全量466passed/3skipped/既有AnyIO1warning，HTTP另2passed/缓存权限warning；uv lock53/diff通过。独立runner/分析/快照/逐题CSV及报告在''' + REL + '''/；所有原tracked文件测试前后hash保持，仅既有Workbench/progress后续更新。条件式建议人工验收后，在模型资源授权/独立锁/smoke门满足时再做隔离B1，以检验口语语义召回/排序和FPR取舍，事实缺失不能保证被Embedding解决。生产/Policy/Skills/正文/冻结题及历史报告不改，无下载/依赖安装/收费模型/提交推送。独立练习：手算13/14/15增益和27–30误报，核对27引用v2，区分事实不足与失效泄漏。'''


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['outcome'] != 'measured' or not manifest['collection_deleted']:
        raise RuntimeError('measurement incomplete')
    progress_path = b.ROOT / 'docs/cartcare-workbench-progress.json'
    doc = json.loads(progress_path.read_text(encoding='utf-8'))
    task = doc['tasks']['A05']
    task.update(status='doing', outcome='partial', issue_id='A05-P2-B0-CAL')
    task['issues'].update({'A05-P2': 'partial', 'A05-P2-B0-CAL': 'measured'})
    task['stages']['A05-P2'] = dict(status='doing', outcome='partial',
        blockers=['B1 model resource authorization, isolated lock/smoke/resource gate pending'])
    task['stages']['A05-P2-B0-CAL'] = dict(status='verify', outcome='measured', threshold=.20,
        run_id=OUT.name, evidence=REL, calibration_sha256=manifest['calibration_sha256'],
        formal_queries=30, human_acceptance='pending')
    if NOTE not in task['note']:
        task['note'] += '\n' + NOTE
    if REL not in task['evidence']:
        task['evidence'] += '; ' + REL + '/'
    doc['updatedAt'] = '2026-10-13'
    b.write_json(progress_path, doc)
    workbench_path = b.ROOT / 'docs/CartCare-Codex-Workbench.html'
    workbench = workbench_path.read_text(encoding='utf-8')
    pattern = r'(<article class="task-card" data-task="A05">)(.*?)(</article>)'
    match = re.search(pattern, workbench, re.S)
    if match is None:
        raise RuntimeError('A05 card not found')
    card = match.group(2)
    if REL not in card:
        card = re.sub(r'(data-field="evidence" value=")([^"]*)(")',
            lambda m: m[1]+m[2]+'; '+html.escape(REL+'/')+m[3], card, count=1)
    escaped = html.escape(NOTE, quote=False)
    if escaped not in card:
        card = re.sub(r'(<textarea data-field="note">)(.*?)(</textarea>)',
            lambda m: m[1]+m[2]+'\n'+escaped+m[3], card, count=1, flags=re.S)
    workbench = workbench[:match.start(2)] + card + workbench[match.end(2):]
    workbench_path.write_text(workbench, encoding='utf-8')
    protected = json.loads((OUT / 'protected_inputs.json').read_text(encoding='utf-8'))
    changed = [p for p, sha in protected.items() if b.digest(b.ROOT / p) != sha]
    allowed = ['docs/CartCare-Codex-Workbench.html', 'docs/cartcare-workbench-progress.json']
    if set(changed) != set(allowed):
        raise RuntimeError('unexpected tracked changes: ' + repr(changed))
    diff = subprocess.run(['git', 'diff', '--check'], cwd=b.ROOT, text=True, capture_output=True)
    if diff.returncode:
        raise RuntimeError('git diff --check failed: '+diff.stdout+diff.stderr)
    validation = dict(head=manifest['head'], stage='A05-P2-B0-CAL', stage_status='verify',
        A05_status='doing', A05_outcome='partial', measurement='real Chroma HTTP; not Fake or real-model E2E',
        formal_queries=30, model_calls=0, default_snapshot_unchanged=True,
        source_call_path='independent gate → original publisher → retrieve_b0 → N06/N07 → observe/aggregate',
        original_production_call_paths_changed=False, all_other_tracked_hashes_unchanged=True,
        changed_tracked_files=changed, B1_executed=False, commit_push=False,
        commands=[dict(command='uv lock --check', result='passed: 53 packages'),
        dict(command='uv run python -m pytest -q tests/test_rag_dev_calibration.py tests/test_rag_frozen_v2.py tests/test_rag_quality_baseline.py tests/test_rag_quality_gate.py tests/test_rag_gold_v2_candidate.py tests/test_knowledge_version_consistency.py tests/test_rerank_result_contract.py tests/test_rag_contract.py', result='193 passed'),
        dict(command='uv run python -m pytest -q', result='466 passed, 3 skipped, 1 existing AnyIO deprecation warning'),
        dict(command='CARTCARE_RUN_CHROMA_HTTP_TEST=1 CHROMA_HOST=127.0.0.1 CHROMA_PORT=8001 NO_PROXY=127.0.0.1,localhost; uv run python -m pytest -q tests/test_rag_http_integration.py', result='2 passed; pytest cache permission warning'),
        dict(command='NO_PROXY=127.0.0.1,localhost; uv run python -m evaluation.reports.hardening.A05.b0-calibrated-20261013.run_verified', result='preflight_passed; no test queries; collection deleted'),
        dict(command='NO_PROXY=127.0.0.1,localhost; uv run python -m evaluation.reports.hardening.A05.b0-calibrated-20261013.run_verified --formal', result='measured; exactly one 30-case pass; collection deleted'),
        dict(command='uv run python -m evaluation.reports.hardening.A05.b0-calibrated-20261013.analyze', result='offline comparison verified both old repeats; no retrieval'),
        dict(command='git diff --check', result='passed')],
        skipped=['live Memory integration not run', '2 HTTP opt-in skipped by default; separately run above'],
        environment_attempts=[dict(phase='directory creation', error='Windows Access denied under sandbox',
            resolution='auto-reviewed elevated creation approved'),
            dict(phase='preflight before any HTTP or formal test', error='PermissionError [Errno 13] writing protected_inputs.json',
            resolution='auto-reviewed elevated evidence writes approved; subsequent preflight passed'),
            dict(phase='Chroma telemetry only', error='capture() takes 1 positional argument but 3 were given',
            result='Chroma heartbeat/get/query and all measurement gates succeeded')],
        acceptance=dict(isolation_publication_hash_retrievability='passed', frozen_30_gold_snapshot='passed',
            human_Gold_review='prior whole-candidate user approval preserved; no new independent annotation',
            reproducibility='passed; lock/code/AST/packages/input hashes and script archived',
            formal_metrics_and_per_case='completed', comparison='same candidates both repeats; threshold-only quality change',
            stage_human_acceptance='pending'),
        artifact_sha256={str(p.relative_to(OUT)).replace('\\', '/'): b.digest(p) for p in OUT.rglob('*')
            if p.is_file() and p.suffix in ('.json', '.md', '.csv', '.py') and p.name != 'validation.json'})
    b.write_json(OUT / 'validation.json', validation)
    print(json.dumps(dict(changed=changed, stage='verify', A05='doing/partial', diff_check='passed')))


if __name__ == '__main__':
    main()
