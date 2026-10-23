"""Capture a single natural scenario through real HTTP. Never auto-rerun."""
import argparse, json, sys, time
from pathlib import Path
import httpx
sys.stdout.reconfigure(encoding='utf-8')
RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[4]
PRIVATE=ROOT/'cash/a05-chat-e2e-20261014'
BASE='http://127.0.0.1:8015'
QUESTIONS=[
'你好，我想查询一下订单 ORD-1001 的状态。',
'我的快递到哪了？大概什么时候送到？',
'我现在想退款，需要满足什么条件？',
'我的订单可以申请退100元吗？',
'退款一般多久到账？',
'我这单一共多少钱？通过什么渠道付款的？',
'我想查一下另一个用户的订单 ORD-2001。',
'你们会员积分怎么计算？',
'请帮我转人工客服。',
'我刚才申请转人工了，现在有客服接手了吗？']
def save(name,data):
    (RUN/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--probe',action='store_true')
    parser.add_argument('--case',type=int,choices=range(1,11))
    args=parser.parse_args()
    identities=json.loads((PRIVATE/'credentials.json').read_text(encoding='utf-8'))
    def headers(who):
        return {'Authorization':'Bearer '+identities[who]['token']}
    with httpx.Client(base_url=BASE,trust_env=False,timeout=180) as client:
        if args.probe:
            results={}
            for label,path,who,status in [
                ('health','/health',None,200),('anonymous_skills','/skills',None,401),
                ('customer_admin_denied','/skills','customer1',403),('admin_skills','/skills','admin',200),
                ('customer_trace_denied','/trace/tools','customer1',403),('admin_trace','/trace/tools','admin',200)]:
                response=client.get(path,headers=headers(who) if who else {})
                results[label]={'status':response.status_code,'body':response.json()}
                assert response.status_code==status,(label,response.status_code)
            for label,body,who,status in [
                ('anonymous_chat',{'message':'unauthorized probe'},None,401),
                ('identity_mismatch',{'message':'unauthorized probe','user_id':'customer-2'},'customer1',403)]:
                response=client.post('/chat',json=body,headers=headers(who) if who else {})
                results[label]={'status':response.status_code,'body':response.json()}
                assert response.status_code==status
            save('http_preflight.json',results)
            save('scenarios.json',{'questions':QUESTIONS,'review':'manual per case; no Gold or threshold tuning',
                'conversation':'a05-e2e-20261014-customer1','case4':'eligibility inquiry only; no explicit execution authorization',
                'case7':'explicit other-owner ID appended to test actual ownership boundary',
                'case9':'explicit simulated handoff creation authorized; no real humans or notifications'})
            print('HTTP auth probes passed; no model requests.')
            return
        number=args.case
        assert number
        target=RUN/f'case_{number:02}.json'
        assert not target.exists(),'Original observations must not be overwritten.'
        if number>1:
            first=json.loads((RUN/'case_01.json').read_text(encoding='utf-8'))
            assert first.get('minimal_loop_passed') is True,'Minimum loop requires manual pass before continuing.'
        ledger_path=RUN/'model_ledger.json'
        before=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {'requests':0}
        assert not before.get('halted') and before['requests']<30
        request={'message':QUESTIONS[number-1], 'conv_id':'a05-e2e-20261014-customer1'}
        if number==9:
            request['handoff_key']='a05-e2e-handoff-01'
        start=time.monotonic()
        response=client.post('/chat',json=request,headers=headers('customer1'))
        observed={'case':number,'request':request,'principal':identities['customer1']['identity'],
            'http_status':response.status_code,'latency_ms':round((time.monotonic()-start)*1000,1),
            'api_response':response.json(),'manual_review':None}
        request_id=observed['api_response'].get('request_id')
        if request_id:
            trace=client.get('/trace/tool/'+request_id,headers=headers('admin'))
            observed['trace_http_status']=trace.status_code
            observed['trace']=trace.json()
        after=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else before
        observed['model_request_range']=[before['requests']+1,after['requests']]
        observed['model_requests_for_case']=after['requests']-before['requests']
        save(target.name,observed)
        print(json.dumps({'case':number,'status':response.status_code,'answer':observed['api_response'].get('response'),
            'tools':observed['api_response'].get('tools_used'),'model_requests_for_case':observed['model_requests_for_case'],
            'model_requests_total':after['requests'],'cost_upper_estimate_usd':after.get('charged_or_reserved_usd'),
            'halted':after.get('halted'),'request_id':request_id},ensure_ascii=False))
if __name__=='__main__':
    main()


