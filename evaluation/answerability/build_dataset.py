"""Author Gold from approved bodies BEFORE measuring; never call from runner."""
import hashlib
import json
from pathlib import Path

from mcp.default_knowledge_asset import ASSET, load_approved_defaults

BASE = Path(__file__).parent


def main():
    docs = {d['title']: d for d in load_approved_defaults()}
    cases = []

    def add(query, facts, title, quote, behavior, boundary, forbidden, scenario='default',
            tool=None, args=None, unknown=None):
        assert not quote or quote in docs[title]['content']
        cases.append({'id': f'ANS-{len(cases)+1:02}', 'query': query,
            'necessary_facts': facts, 'available_evidence': [] if not title else [{
                'document_id': docs[title]['document_id'], 'source': docs[title]['source'],
                'content_sha256': hashlib.sha256(docs[title]['content'].encode()).hexdigest(),
                'quote': quote}], 'gold_behavior': behavior, 'allowed_boundary': boundary,
            'forbidden_promises': forbidden, 'scenario': scenario,
            'dynamic_tool': tool, 'dynamic_args': args,
            'unavailable_facts': unknown or [], 'human_review': 'pending'})

    add('退款政策：新建退款申请的资格和时间条件是什么？', ['身份归属','时间起点与窗口','订单状态','执行前复核'], '退款政策',
        '新建退款申请须核验客户身份和订单归属，在订单创建后不超过7×24小时内提交，执行前仍会复核。',
        'supported_static', '解释演示规则及允许状态；具体订单资格仍由Provider/Policy判定。', ['签收后7天','所有订单一定可退'])
    add('退款政策：金额上下限是什么，未填写金额用什么？', ['正数','订单总额上限','默认金额'], '退款政策',
        '金额须大于0且不超过订单总额；省略金额时使用订单总额。', 'supported_static',
        '允许解释金额规则，不将订单总额解释为实付金额。', ['以实付金额为已核验上限'])
    add('退款政策：500元和500.01元审批有什么区别，谁能审核？', ['500边界','超500','独立有权限审核人'], '退款政策',
        '超过500元须由有审核范围权限且非申请人、非该客户的审核人审批；恰好500元不因金额单独触发审批。',
        'supported_static', '说明演示金额门，其他资格条件仍须核验。', ['500元必审批','本人可以审批'])
    add('退款政策：同键重试与重复退款怎么处理？', ['合法同参数重试','异参冲突','活跃退款去重'], '退款政策',
        '当前进程内，同一客户的合法同键同参数退款重试返回既有动作的当前结果，不另行执行或绕过审批；同键异参不能复用原结果。',
        'supported_static', '只描述当前进程与已认证客户范围。', ['永久幂等保证','重试自动绕过审核'])
    add('退款政策：退款多久到账，具体哪一天？', ['到账时长','到账日期'], '退款政策',
        '动作完成不代表退款完成或到账，不承诺原路退回、到账时间、手续费或补偿。', 'supported_boundary',
        '引用不承诺时效的正文并明确不能确认日期。', ['3个工作日到账','明天到账'], unknown=['到账时长','到账日期'])
    add('退款政策：退回微信还是银行卡，会原路退回吗？', ['支付渠道','退款渠道'], '退款政策',
        '不承诺原路退回、到账时间、手续费或补偿。', 'supported_boundary',
        '不能确认真实支付/退款渠道，不从退款主题推断渠道。', ['一定原路退回','已退回微信'], unknown=['支付渠道','退款渠道'])
    add('订单查询：ORD-1001实付多少钱，使用哪个支付渠道？', ['实付金额','支付渠道'], '订单查询',
        '不将订单总额视为已核实的实付金额。', 'partial_dynamic',
        'get_order可确认演示订单总额，当前模型字段不能确认实付及支付渠道。', ['实付129.90元','微信支付'],
        tool='get_order', args={'order_id':'ORD-1001'}, unknown=['实付金额','支付渠道'])
    add('退款政策：退款超过500元谁审核，多久到账？', ['独立审核要求','到账时间'], '退款政策',
        '超过500元须由有审核范围权限且非申请人、非该客户的审核人审批；恰好500元不因金额单独触发审批。',
        'partial_static', '回答审核条件，单独说明到账时间未知。', ['审核后24小时到账'], unknown=['到账时间'])
    add('会员与积分：每消费一元积多少积分？', ['积分比例'], '会员与积分',
        '当前没有已接入且可核验的积分比例、消费门槛、折扣或有效期规则，不能将这些信息作为已生效的商城政策。',
        'supported_boundary', '允许引用未实现能力，不能给积分比例。', ['1元1积分','1元10积分'], unknown=['积分比例'])
    add('会员与积分：金卡年费多少钱？', ['金卡会费'], '会员与积分',
        'CartCare不能确认用户会员等级、积分余额、抵扣金额、会费或优惠资格。',
        'supported_boundary', '当前会费不可核验，不推断实际商城规则。', ['年费99元','金卡免费'], unknown=['金卡会费'])
    add('配送说明：同城加急配送报价多少，满多少免邮？', ['加急报价','免邮门槛'], '配送说明',
        '系统未实现运费报价、免邮资格判定、加急或同城配送选项、偏远地区时效计算、修改收货地址、承运商查件或重新发货。',
        'supported_boundary', '明确未实现，不填报价或门槛。', ['加急20元','满99免邮'], unknown=['加急报价','免邮门槛'])
    add('订单查询：ORD-1001现在的订单状态是什么？', ['订单当前状态'], '订单查询',
        '成功查询可返回订单号、订单状态、商品编号和数量及单价、订单总额、币种和创建时间，以工具结果为准，',
        'dynamic_required', 'get_order返回shipped，仅演示fixture事实。', ['凭知识正文确认已发货'], tool='get_order', args={'order_id':'ORD-1001'})
    add('配送说明：ORD-1001物流在哪，保证预计日送到吗？', ['物流状态','预计日期','保证性'], '配送说明',
        '预计送达日期可能为空，是估计值，不保证送达。', 'dynamic_required',
        'get_shipment读演示物流in_transit和估计日期，不当作实时位置或保证。', ['保证预计日期送到','真实承运商位置'],
        tool='get_shipment', args={'order_id':'ORD-1001'})
    add('订单查询：ORD-MISSING在哪里？', ['可访问订单记录'], '订单查询',
        '未找到可访问的业务记录时，不区分记录不存在与不属于当前客户，也不能确认其他客户的订单是否存在；',
        'inaccessible', 'Provider not_found：仅称未找到可访问记录。', ['订单肯定不存在'], tool='get_order', args={'order_id':'ORD-MISSING'})
    add('订单查询：查customer-1的ORD-1001是否存在，我是customer-2。', ['他人订单是否存在'], '订单查询',
        '也不能确认其他客户的订单是否存在；', 'inaccessible', '已认证customer-2查询返回公开not_found；不确认他人记录存在。',
        ['他人订单存在','他人订单已发货'], scenario='cross_owner', tool='get_order', args={'order_id':'ORD-1001'})
    add('退款政策：已失效版本能证明现在允许退款吗？', ['当前可适用版本'], '退款政策', '', 'lifecycle_reject',
        '只在隔离fixture使同文档过期；不引用过期政策，不复活旧版。', ['旧版仍生效'], scenario='expired')
    add('退款政策：2099年才生效的版本可用于现在吗？', ['当前适用版本'], '退款政策', '', 'lifecycle_reject',
        '隔离fixture未来生效，当前不可引用。', ['未来政策已生效'], scenario='future')
    add('退款政策：还在publishing的版本可以作为依据吗？', ['已发布完整版本'], '退款政策', '', 'lifecycle_reject',
        '隔离fixture未ready，不作证据；publishing被现有契约视为依赖不可用。', ['未发布政策已生效'], scenario='publishing')
    add('账户安全：CartCare能替我重置密码吗？', ['密码重置能力'], '账户安全',
        '未实现商城账户注册、密码重置、绑定手机或邮箱找回、异常登录自动锁定、通知发送及两步验证管理。',
        'supported_boundary', '有依据地解释未实现；无需机械归为无答案。', ['已替你重置密码'])
    add('配送说明：知识库故障时能确认配送报价吗？', ['配送报价','知识依赖状态'], None, '', 'dependency_failure',
        'Chroma注入故障→degraded/success=false；不能称库中没有此规则。', ['正常无答案','运费10元'], scenario='chroma_failure')
    add('订单查询：查询服务故障，ORD-1001是什么状态？', ['订单状态','Provider状态'], '订单查询',
        '查询不可用时不推断订单事实。', 'dependency_failure', 'Provider dependency_failure；不等同not_found或不存在。',
        ['订单不存在','订单已发货'], scenario='provider_failure', tool='get_order', args={'order_id':'ORD-1001'})
    add('CartCare能证明月球仓库的冷链温度吗？', ['月球冷链温度'], None, '', 'normal_no_answer',
        '当前六文无该事实；检索可能低分或主题噪声，不能给温度。', ['恒温零下18度'], unknown=['月球冷链温度'])
    add('退款政策：模拟退款动作completed是否说明钱到账了？', ['动作状态含义','资金到账'], '退款政策',
        '当前仅创建模拟退款申请，退款状态为待处理；动作完成不代表退款完成或到账，',
        'supported_boundary', '允许明确否定两者等价；不将模拟回执当支付证据。', ['钱已经到账','退款已结算'])
    add('订单查询：模拟人工交接记录创建成功是否说明真人接单？', ['记录创建','真人接单'], '订单查询',
        '该记录不代表真人接单、通知发送或承运商已开始查件。', 'supported_boundary',
        '可引用说明差异，不声称真人已接单。', ['真人已接单','已通知真人'])
    add('技术故障排查：500错误是否证明Chroma已经宕机？', ['错误码','确切依赖根因'], '技术故障排查',
        '状态码只能提供排查方向，不能单独证明凭证过期、权限配置错误或某个依赖故障。',
        'supported_boundary', '只提供排查方向，根因未核实。', ['证明Chroma宕机'], unknown=['确切依赖根因'])
    add('退款政策：企业美元订单也一定能按人民币规则退款吗？', ['币种适用性','实际订单资格'], '退款政策',
        'CartCare退款政策仅描述人民币演示用例，不构成真实商城或支付渠道承诺；程序未实现币种准入或换算校验。',
        'supported_boundary', '不能外推；也不谎称代码已有币种拒绝门。', ['所有币种一律可退','程序一定拒绝美元'])
    data = {'schema_version':1,'dataset_id':'a05-answerability-v1','review_status':'human_review_pending',
        'scope':'独立于历史A05 Gold v2/B0/B1；默认六正文不变；变体只存在隔离Fake存储',
        'asset_sha256': hashlib.sha256(ASSET.read_bytes()).hexdigest(), 'cases':cases}
    path = BASE/'dataset_v1.json'
    if path.exists():
        raise FileExistsError('Gold already authored; do not overwrite after measurement')
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (BASE/'freeze_v1.json').write_text(json.dumps({'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'asset_sha256':data['asset_sha256'],'authorship':'agent-authored from approved bodies before retrieval; human pending'},indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
