"""Read-only final state check + protected-file hashes. Never publishes."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
os.environ['NO_PROXY']='127.0.0.1,localhost'
from mcp.seed_demo_knowledge import ExistingKnowledgeBase
from mcp.default_knowledge_publication import snapshot,encoded,read_backup


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    pre=json.loads((OUT/'preflight.json').read_text(encoding='utf-8'))
    allowed={'README.md','docs/CartCare-Codex-Workbench.html','docs/cartcare-workbench-progress.json'}
    changes=[n for n,h in pre['tracked_file_sha256'].items() if digest(ROOT/n)!=h]
    assert set(changes)<=allowed, changes
    assert digest(ROOT/'.env')==pre['env_file_sha256']
    assert digest(OUT/'before.json')==pre['before_sha256']==digest(Path(pre['second_copy']))
    k=ExistingKnowledgeBase(chroma_host='127.0.0.1',chroma_port=8001,seed_defaults=False)
    assert k.min_score==.35
    assert encoded(snapshot(k))==encoded(read_backup(k,OUT/'after.json'))
    p=json.loads((ROOT/'docs/cartcare-workbench-progress.json').read_text(encoding='utf-8'))['tasks']['A05']
    assert p['status']=='doing' and p['outcome']=='partial'
    assert p['stages']['A05-B1']['status']=='blocked' and p['stages']['A05-B1-PREP']['status']=='blocked'
    assert p['stages']['DEFAULT-KB-PUBLICATION']['status']=='verify'
    result={'passed':True,'tracked_changed_files':changes,
        'all_other_tracked_files_unchanged':True,'protected_tracked_count':len(pre['tracked_file_sha256'])-len(changes),
        'env_unchanged':True,'before_and_second_copy_sha256':pre['before_sha256'],
        'after_sha256':digest(OUT/'after.json'),'current_full_snapshot_equal_after':True}
    (OUT/'delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paths=[p for p in OUT.rglob('*') if p.is_file() and p.name!='files_sha256.json']
    hashes={p.relative_to(ROOT).as_posix():digest(p) for p in sorted(paths)}
    (OUT/'files_sha256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
