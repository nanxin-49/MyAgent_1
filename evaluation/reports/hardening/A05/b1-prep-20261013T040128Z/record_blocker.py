"""Record the observed failed gate; no network, environment or model operations."""
import ast
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
REL = str(OUT.relative_to(ROOT)).replace('\\', '/')
NOTE = ('2026-10-13 A05-B1-PREP=blocked/partial；用户有条件批准独立CPU环境/固定BGE权重/评测适配器/合成smoke，'
        '未批准dev校准或正式B1。HEAD=eb55ae85532100829f7f8dd92d6a8c4813f6572c，起始干净。'
        '北京时间12:01:28资源门实测可用物理内存1.7302GiB<4GiB（总15.2458GiB/占用88%），'
        'E盘165.7613GiB>=6GiB；首个资源门未通过，立即停止安装、独立环境创建及模型加载。'
        '本阶段新增网络下载0bytes；没有解析完整依赖预算/创建锁/下载权重/验证本地SHA/编写语义适配器/运行smoke或冻结Chunk长度检查。'
        'Embedding峰值/模型CPU时间/加载及编码耗时均N/A，不能冒用旧回归。'
        '本轮0次Chroma调用/0新集合，不触及默认库或词法集合；不终止其他进程。'
        '全部原tracked文件hash保留，后续仅既有Workbench/progress授权更新；pyproject/uv.lock/生产代码/冻结Gold/B0报告不改。'
        '完整pytest未运行：资源门阻断且无模型/适配器实现；证据JSON、脚本语法、文档状态、保护hash及diff检查见' + REL + '/validation.json。'
        '最小解决：用户自行释放应用内存或选择运行时段，使可用内存>=4GiB后重新核验；保留有条件PREP授权，'
        '安装前完整锁/wheelhash与累计<=1GiB下载预算、加载前内存复检、进程峰值<=2GiB门仍须满足。'
        'A05仍doing/partial，B1正式实验blocked；B0-calibrated verify/待最终验收保持，未提交推送。'
        '独立练习：运行本目录check_resource_gate.py，exit2表示内存/磁盘资源不足；exit0不自动授权安装。')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    resource = json.loads((OUT / 'resource_gate.json').read_text(encoding='utf-8'))
    if resource['installation_resource_gate_passed']:
        raise RuntimeError('this recorder is only for the observed failed resource gate')
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    protection_path = OUT / 'protected_inputs.json'
    if protection_path.exists():
        protected = json.loads(protection_path.read_text(encoding='utf-8'))
    else:
        protected = {p: digest(ROOT / p) for p in tracked if (ROOT / p).is_file()}
        write_json(protection_path, protected)
    progress_path = ROOT / 'docs/cartcare-workbench-progress.json'
    before = json.loads(progress_path.read_text(encoding='utf-8'))
    baseline_path = OUT / 'progress_before.json'
    if not baseline_path.exists():
        baseline_path.write_bytes(progress_path.read_bytes())
    doc = json.loads(baseline_path.read_text(encoding='utf-8'))
    task = doc['tasks']['A05']
    task.update(status='doing', outcome='partial', issue_id='A05-B1-PREP')
    task['issues']['A05-B1-PREP'] = 'partial'
    task['stages']['A05-B1-PREP'] = dict(status='blocked', outcome='partial', run_id=OUT.name,
        preparation_authorization='conditional user approval on 2026-10-13; install/load require available RAM >=4 GiB',
        blockers=['available physical RAM 1.7302 GiB below 4 GiB requirement',
                  'environment/lock/weight validation/adapter/smoke not attempted after failed resource gate'],
        evidence=REL+'/', model_id=resource['requested_model']['model_id'],
        revision=resource['requested_model']['revision'], new_network_download_bytes=0,
        dev_calibration_executed=False, formal_test_executed=False)
    task['stages']['A05-B1']['blockers'] = [
        'formal B1 development calibration and test authorization not granted',
        'B1-PREP memory gate failed; independent environment, dependency lock and smoke incomplete']
    task['stages']['A05-P2']['blockers'] = [
        'B1-PREP resource gate failed (available RAM <4 GiB)',
        'formal B1 calibration/test authorization and remaining preparation gates pending']
    task['note'] += '\n'+NOTE
    task['evidence'] += '; '+REL+'/'
    doc['updatedAt'] = '2026-10-13'
    write_json(progress_path, doc)
    workbench_path = ROOT / 'docs/CartCare-Codex-Workbench.html'
    workbench = workbench_path.read_text(encoding='utf-8')
    match = re.search(r'(<article class="task-card" data-task="A05">)(.*?)(</article>)', workbench, re.S)
    if match is None:
        raise RuntimeError('A05 workbench card missing')
    card = match[2]
    if REL not in card:
        card = re.sub(r'(data-field="evidence" value=")([^"]*)(")',
            lambda m: m[1]+m[2]+'; '+html.escape(REL+'/')+m[3], card, count=1)
    escaped = html.escape(NOTE, quote=False)
    if escaped not in card:
        card = re.sub(r'(<textarea data-field="note">)(.*?)(</textarea>)',
            lambda m: m[1]+m[2]+'\n'+escaped+m[3], card, count=1, flags=re.S)
    workbench_path.write_text(workbench[:match.start(2)]+card+workbench[match.end(2):], encoding='utf-8')
    changed = [p for p, sha in protected.items() if digest(ROOT / p) != sha]
    allowed = {'docs/CartCare-Codex-Workbench.html', 'docs/cartcare-workbench-progress.json'}
    if set(changed) != allowed:
        raise RuntimeError('unexpected original file changes: '+repr(changed))
    saved = json.loads(progress_path.read_text(encoding='utf-8'))
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    if any(saved['tasks'][k] != v for k, v in baseline['tasks'].items() if k != 'A05'):
        raise RuntimeError('unrelated task changed')
    if saved['tasks']['A05']['stages']['A05-P2-B0-CAL'] != baseline['tasks']['A05']['stages']['A05-P2-B0-CAL']:
        raise RuntimeError('B0 acceptance state changed')
    for path in OUT.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for path in OUT.glob('*.json'):
        json.loads(path.read_text(encoding='utf-8'))
    diff = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, text=True, capture_output=True)
    if diff.returncode:
        raise RuntimeError('diff check failed: '+diff.stdout+diff.stderr)
    validation = dict(task='A05-B1-PREP', head=resource['head'], status='blocked', outcome='partial',
        A05_status='doing', A05_outcome='partial', B1_status='blocked',
        authoritative_blocker='available physical RAM below user-required 4 GiB at the first stage gate',
        performed=['Windows available-memory and E-disk read-only measurement',
                   'evidence JSON parsing and Python AST syntax checks',
                   'all original tracked SHA256 protection checks except two authorized state documents',
                   'A05-only state update and unchanged B0-calibrated acceptance state', 'git diff --check'],
        changed_original_files=changed, all_other_original_tracked_hashes_unchanged=True,
        full_regression=dict(status='not_run', reason='resource gate blocked before any implementation/install/model smoke',
                             passed=None, failed=None, skipped=None),
        environment_lock='not_created', local_weight_hash='not_verified', smoke='not_run',
        new_network_download_bytes=0, model_CPU_time_seconds=None, embedding_process_peak_memory_bytes=None,
        Chroma_calls=0, collections_created=0, dev_calibration_executed=False, formal_test_executed=False,
        installed_or_loaded=False, terminated_other_processes=False, committed_or_pushed=False,
        production_request_path_changed=False, readme_core_wiki_update_needed=False,
        dependency_download_budget='not_resolved; not a pass',
        minimum_resolution=resource['minimum_resolution'],
        directory_permission_note='normal sandbox report directory creation denied; authorized elevated report-only write succeeded',
        artifacts_sha256={p.name: digest(p) for p in OUT.iterdir()
                          if p.is_file() and p.name != 'validation.json'})
    write_json(OUT / 'validation.json', validation)
    print(json.dumps({'task':'A05-B1-PREP','status':'blocked','RAM_GiB':resource['available_ram_GiB'],
                      'download_bytes':0,'diff_check':'passed','changed_original_files':changed}))


if __name__ == '__main__':
    main()
