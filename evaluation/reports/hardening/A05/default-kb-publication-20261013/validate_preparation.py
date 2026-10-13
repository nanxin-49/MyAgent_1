"""Offline preservation/semantic validation. No network or collection access."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = OUT/'source_before/knowledge_base.py.txt'
    def methods(path):
        cls = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name=='KnowledgeBase')
        return {n.name:ast.dump(n, include_attributes=False) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    old,new = methods(before),methods(ROOT/'mcp/knowledge_base.py')
    changed = [name for name in old if old[name] != new[name]]
    assert changed == ['__init__','rebuild_demo_collection','_load_default_docs']
    preserved = {}
    lock = json.loads((ROOT/'evaluation/rag_quality/gold_v2_candidate_validation.json').read_text(encoding='utf-8'))
    for name, expected in lock['protected_sha256'].items():
        actual_path = (before if name=='mcp/knowledge_base.py' else
            ROOT/'evaluation/rag_quality/history/run_baseline_v1.py.txt' if name=='evaluation/rag_quality/run_baseline.py' else ROOT/name)
        assert digest(actual_path) == expected, name
        preserved[name] = digest(actual_path)
    scopes = ['evaluation/rag_quality','evaluation/reports/rag_quality',
        'evaluation/reports/hardening/A05/b0-calibrated-20261013',
        'evaluation/reports/hardening/A05/b1-prep-20261013T040128Z',
        'skills','policy','actions','business','pyproject.toml','uv.lock','mcp/knowledge_embeddings.py',
        'mcp/rag_contract.py','mcp/tool_manager.py','api/main.py']
    assert subprocess.run(['git','diff','--quiet','HEAD','--',*scopes],cwd=ROOT).returncode == 0
    tracked = subprocess.check_output(['git','ls-files','--',*scopes],cwd=ROOT,text=True).splitlines()
    current_hashes = {name:digest(ROOT/name) for name in tracked}
    progress = json.loads((ROOT/'docs/cartcare-workbench-progress.json').read_text(encoding='utf-8'))['tasks']['A05']
    assert progress['status']=='doing' and progress['outcome']=='partial'
    assert progress['stages']['A05-B1']['status']=='blocked'
    assert progress['stages']['A05-B1-PREP']['status']=='blocked'
    assert progress['stages']['DEFAULT-KB-PUBLICATION']['status']=='verify'
    result = {'passed':True,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'changed_kb_methods':changed,'all_other_kb_methods_ast_identical':True,
        'historical_source_sha256':digest(before),'historically_locked_hashes_verified':preserved,
        'protected_tracked_scope_git_diff_empty':True,'protected_current_file_sha256':current_hashes}
    (OUT/'preservation_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paths = [p for p in OUT.rglob('*') if p.is_file() and p.name != 'files_sha256.json']
    paths += [ROOT/name for name in ('.gitattributes','README.md',
        'docs/CartCare-Codex-Workbench.html','docs/cartcare-workbench-progress.json',
        'mcp/knowledge_base.py','mcp/seed_demo_knowledge.py','mcp/default_knowledge_asset.py',
        'mcp/default_knowledge_publication.py','mcp/knowledge_assets/default_business_v1.json',
        'mcp/knowledge_assets/default_business_v1.approval.json','evaluation/default_kb_publication.py',
        'tests/test_default_knowledge_publication.py','tests/test_rag_gold_v2_candidate.py')]
    hashes = {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(paths)}
    (OUT/'files_sha256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'protected_tracked_files':len(tracked),'locked_files':len(preserved),'changed_kb_methods':changed}))


if __name__=='__main__':
    main()
