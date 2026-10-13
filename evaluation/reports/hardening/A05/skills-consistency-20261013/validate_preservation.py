"""Offline protection, diffs and status checks. No services or model calls."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline=json.loads((OUT/'runtime_before.json').read_text(encoding='utf-8'))
    allowed={'skills/billing_support/SKILL.md','skills/general_customer_service/SKILL.md',
        'skills/technical_support/SKILL.md','skills/README.md','README.md',
        'docs/CartCare-Codex-Workbench.html','docs/cartcare-workbench-progress.json'}
    changed=[p for p,h in baseline['tracked_sha256'].items() if digest(ROOT/p)!=h]
    assert set(changed)<=allowed, changed
    assert digest(ROOT/'mcp/knowledge_assets/default_business_v1.json')=='17e3c606365c203589919321b166e942e6aab569d539ce631f447a5439cd018d'
    p=json.loads((ROOT/'docs/cartcare-workbench-progress.json').read_text(encoding='utf-8'))['tasks']['A05']
    assert p['status']=='doing' and p['outcome']=='partial'
    assert p['stages']['A05-SKILLS-CONSISTENCY']['status']=='verify'
    assert p['stages']['DEFAULT-KB-PUBLICATION']['status']=='verify'
    assert p['stages']['A05-B1']['status']=='blocked'
    assert p['stages']['A05-B1-PREP']['status']=='blocked'
    diffs=[]
    for name in ('billing_support','general_customer_service','technical_support'):
        old=OUT/'source_before'/f'{name}.bin'
        current=ROOT/'skills'/name/'SKILL.md'
        assert digest(old)==baseline['tracked_sha256'][f'skills/{name}/SKILL.md']
        diffs.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(keepends=True),
            current.read_text(encoding='utf-8').splitlines(keepends=True),
            fromfile=f'before/skills/{name}/SKILL.md',tofile=f'after/skills/{name}/SKILL.md'))
    (OUT/'skills_diff.patch').write_text(''.join(diffs),encoding='utf-8')
    result={'passed':True,'baseline_head':baseline['head'],'changed_tracked':changed,
        'all_other_tracked_sha256_unchanged':True,
        'protected_count':len(baseline['tracked_sha256'])-len(changed),
        'approved_asset_sha256':digest(ROOT/'mcp/knowledge_assets/default_business_v1.json'),
        'database_calls':0,'real_model_calls':0,'api_started':False}
    (OUT/'preservation_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paths=[q for q in OUT.rglob('*') if q.is_file() and q.name!='files_sha256.json']
    paths += [ROOT/n for n in allowed if (ROOT/n).exists()]
    paths += [ROOT/'tests/test_runtime_skills_consistency.py']
    (OUT/'files_sha256.json').write_text(json.dumps({q.relative_to(ROOT).as_posix():digest(q) for q in sorted(paths)},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
