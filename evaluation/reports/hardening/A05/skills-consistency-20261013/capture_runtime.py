"""Capture actual SDK-bound prompts using Fake SDK; never starts API/Chroma."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))
from tests.test_runtime_skills_consistency import capture


def main():
    phase=sys.argv[1]
    queries=['退款','退款发票订阅','订单会员客服','401 登录失败','订单退款接口500发票会员','请转人工客服','xyzq']
    rows=[]
    for message in queries:
        manager,sdk,runtime,req,result=capture(message)
        rows.append({'message':message,'loaded_paths':[s.path for s in manager.skills],
            'matched_by_keywords':[s.name for s in manager.skills if s.matches(message,None)],
            'sdk_calls':len(sdk.calls),'system_prompts':[r['system'] for r in sdk.calls],
            'supports_routing':runtime.supports_routing,'role_packet':runtime.make_agent()._build_role_packet(req),
            'handoff_created':result.handoff.handoff_created,'model_evidence':'Fake SDK only'})
    paths=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths if (ROOT/p).is_file()}
    data={'phase':phase,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tracked_sha256':hashes,'rows':rows,'real_model_calls':0,'Chroma_calls':0,'api_started':False}
    path=Path(__file__).with_name(f'runtime_{phase}.json')
    with path.open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'phase':phase,'captured':len(rows),'real_model_calls':0,'Chroma_calls':0}))


if __name__=='__main__':
    main()
