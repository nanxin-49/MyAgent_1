/* Browser rendering and HTTP consumer tests; fake DOM/API, not live integration. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../demo/static/demo.js'), 'utf8');
class Element {
  constructor(tag) {this.tagName = tag; this.children = []; this.events = {}; this.textContent = ''; this.value = '';}
  append(...els) {this.children.push(...els);}
  prepend(el) {this.children.unshift(el);}
  addEventListener(event, handler) {this.events[event] = handler;}
}
function browser(responses = []) {
  const ids = Object.fromEntries(['chat-form','scenarios','message','user-id','conv-id','status','turns','new-conversation'].map(id => [id, new Element(id)]));
  const all = Object.values(ids), requests = [];
  const context = {document: {getElementById: id => ids[id], createElement: tag => {
    const el = new Element(tag); all.push(el); return el;
  }, querySelectorAll: () => all}, fetch: async (url, options) => {
    requests.push({url, body: options?.body ? JSON.parse(options.body) : undefined});
    const result = url.includes('scenarios.json') ? [] : responses.shift();
    if (result instanceof Error) throw result;
    return {ok: true, status: 200, json: async () => result, text: async () => JSON.stringify(result)};
  }};
  vm.runInNewContext(source, context);
  return {...context, ids, all, requests};
}
function text(el) {return [el.textContent, ...el.children.map(text)].join('\n');}
const citation = {reference: 'policy@v1#chunk-0', source: 'demo:refund', document_id: 'policy', chunk_index: 0, policy_version: 'v1'};
const chat = {request_id: 'req-1', conv_id: 'conv-1', response: '<img onerror=alert(1)>', topology: 'single', agent_type: 'support',
  primary_agent: null, supporting_agents: null, routing_reason: null, routing_confidence: null, latency_ms: 12,
  tools_used: ['search_knowledge_base'], retrieval_status: 'usable', citations: [citation]};
const trace = {found: true, trace: {memory: {read_status: 'completed'}, request_latency_ms: 15,
  tool_calls: [{tool_name: 'search_knowledge_base', risk_level: 'read', validated_input: {query: 'policy'},
    retrieval_status: 'usable', citations: [citation], retrieval_hits: [{...citation, title: 'Refund policy'}]}]}};
test('trace, citation title/source/version, nullable routing and safe text rendering', () => {
  const b = browser();
  const card = b.CartCareDemo.renderTurn({message: 'policy', user_id: 'customer-1'}, chat, trace);
  const rendered = text(card);
  for (const value of ['req-1', 'single / support', '12 ms', 'Refund policy', 'demo:refund', 'v1', 'validated_input', 'read_status', chat.response]) assert.ok(rendered.includes(value));
  assert.equal(b.all.filter(el => el.tagName === 'img').length, 0);
});
for (const status of ['low_confidence','no_answer','degraded', null]) {
  test(`${status}: no fabricated normal citation even if payload contains one`, () => {
    const b = browser();
    const card = b.CartCareDemo.renderTurn({message: 'policy', user_id: 'customer-1'}, {...chat, retrieval_status: status}, trace);
    assert.equal(b.CartCareDemo.view({...chat, retrieval_status: status}, trace).citations.length, 0);
    // Raw trace remains inspectable; citation panel alone contains no source.
    const ragPanel = card.children.find(el => el.className === 'evidence').children[0];
    assert.ok(text(ragPanel).includes(status || 'not_requested'));
    assert.ok(!text(ragPanel).includes('demo:refund'));
  });
}
for (const command of ['Approve','Reject','Resume']) {
  test(`${command} consumes Action API and renders observed status`, async () => {
    const status = command === 'Reject' ? 'rejected' : command === 'Resume' ? 'awaiting_approval' : 'completed';
    const b = browser([{status, action_id: 'action-1', success: true}]);
    const envelope = {found: true, trace: {tool_calls: [{tool_name: 'request_refund', risk_level: 'dangerous',
      validated_input: {order_id: 'ORDER'}, action_result: {action_id: 'action-1', status: 'awaiting_approval',
        policy_decision: 'require_approval', reason_code: 'amount_requires_approval', policy_version: 'v1'}}]}};
    const card = b.CartCareDemo.renderTurn({message: 'refund', user_id: 'customer-1'}, chat, envelope);
    b.ids['user-id'].value = 'customer-2';
    await b.all.find(el => el.textContent === command).events.click();
    const request = b.requests.at(-1);
    assert.equal(request.url, `/actions/action-1/${command.toLowerCase()}`);
    assert.equal(request.body.user_id, 'customer-1');
    assert.equal(request.body.request_id, 'req-1');
    assert.ok(text(card).includes(`${command}: ${status}`));
    assert.ok(text(card).includes('require_approval'));
    assert.equal(envelope.trace.tool_calls[0].action_result.status, 'awaiting_approval');
  });
}
test('chat smoke fetches matching trace and retains answer if trace unavailable', async () => {
  const b = browser([chat, new Error('trace unavailable')]);
  b.ids.message.value = 'hello'; b.ids['user-id'].value = 'customer-1';
  await b.ids['chat-form'].events.submit({preventDefault() {}});
  assert.equal(b.requests[1].url, '/chat');
  assert.equal(b.requests[2].url, '/trace/tool/req-1');
  assert.equal(b.ids['conv-id'].value, 'conv-1');
  assert.ok(text(b.ids.turns).includes(chat.response));
  assert.ok(text(b.ids.turns).includes('trace unavailable'));
});
test('policy deny and completed simulated action render actual outcomes', () => {
  const b = browser();
  const envelope = {found: true, trace: {tool_calls: [
    {tool_name: 'request_refund', risk_level: 'dangerous', action_result: {status: 'rejected', policy_decision: 'deny', reason_code: 'unauthorized'}},
    {tool_name: 'request_cancel_order', risk_level: 'dangerous', action_result: {status: 'completed', policy_decision: 'allow', execution_simulated: true}}
  ]}};
  const card = b.CartCareDemo.renderTurn({message: 'action', user_id: 'customer-1'}, chat, envelope);
  for (const value of ['rejected', 'deny', 'unauthorized', 'completed', 'allow', 'execution_simulated']) assert.ok(text(card).includes(value));
  assert.equal(b.all.filter(el => ['Approve','Reject','Resume'].includes(el.textContent)).length, 0);
});
test('no trace cannot manufacture successful action from answer text', () => {
  const b = browser();
  const card = b.CartCareDemo.renderTurn({message: 'refund', user_id: 'customer-1'}, {...chat, response: 'refund completed'}, {found: false});
  assert.ok(text(card).includes('未观测到 ActionService 结果'));
  assert.ok(text(card).includes('Trace 未找到'));
});
test('deterministic helper output is visible as tool evidence', () => {
  const b = browser();
  const card = b.CartCareDemo.renderTurn({message: 'help', user_id: 'customer-1'}, chat,
    {found: true, trace: {tool_calls: [{tool_name: 'create_handoff_summary', risk_level: 'read',
      helper_result: {reason: 'requires review', sensitive_data_required: false}}]}});
  assert.ok(text(card).includes('helper_result'));
  assert.ok(text(card).includes('requires review'));
});
