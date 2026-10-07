/* Same-origin API consumer; no policy decisions or action execution in the UI. */
(function (root) {
  "use strict";
  const pretty = value => JSON.stringify(value, null, 2);
  function view(chat, traceEnvelope) {
    const trace = traceEnvelope?.found ? traceEnvelope.trace : null;
    const calls = trace?.tool_calls || [];
    const citations = chat.retrieval_status === "usable" ? (chat.citations || []).map(c => {
      const hit = calls.flatMap(t => t.retrieval_hits || []).find(h =>
        h.document_id === c.document_id && h.chunk_index === c.chunk_index);
      return {...c, title: hit?.title || "文档标题未观测"};
    }) : [];
    return {request_id: chat.request_id, topology: chat.topology, agent_type: chat.agent_type,
      tools_used: chat.tools_used || [], latency_ms: chat.latency_ms,
      retrieval_status: chat.retrieval_status || "not_requested", citations, calls, trace,
      actions: calls.filter(t => t.action_result).map(t => t.action_result)};
  }
  const api = {view};
  if (typeof module !== "undefined") module.exports = api;
  root.CartCareDemo = api;
  if (typeof document === "undefined") return;
  const $ = id => document.getElementById(id);
  function element(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }
  function json(parent, title, data) {
    parent.append(element("h3", title), element("pre", pretty(data)));
  }
  let busy = false;
  function setBusy(value) {
    busy = value;
    document.querySelectorAll("button,input,textarea").forEach(el => {el.disabled = value;});
  }
  async function request(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: pretty(body)});
    const text = await response.text();
    let data;
    try {data = JSON.parse(text);} catch {throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);}
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${pretty(data.detail || data)}`);
    return data;
  }
  function renderAction(parent, initial, userId, requestId) {
    const box = element("div", undefined, "action");
    parent.append(box);
    const label = element("h3", "Action · " + (initial.action_id || "无 action_id"));
    const state = element("pre", pretty(initial));
    const commands = element("div", undefined, "toolbar");
    const log = element("div");
    box.append(label, state, commands, log);
    if (!initial.action_id) return;
    for (const command of ["Approve", "Reject", "Resume", "Refresh"]) {
      const button = element("button", command);
      button.type = "button";
      button.addEventListener("click", async () => {
        if (busy) return;
        setBusy(true);
        try {
          const path = `/actions/${encodeURIComponent(initial.action_id)}`;
          const result = command === "Refresh"
            ? await request(`${path}?user_id=${encodeURIComponent(userId)}`)
            : await request(`${path}/${command.toLowerCase()}`, {user_id: userId, request_id: requestId});
          state.textContent = pretty(result);
          log.append(element("p", `${command}: ${result.status} · ${result.error_code || ""}`));
        } catch (error) {log.append(element("p", error.message, "error"));}
        finally {setBusy(false);}
      });
      commands.append(button);
    }
    box.append(element("p", "按钮只调用现有 API；Approve 可能直接完成执行。上方 Tool Trace 是原始快照，本卡片显示最新 ActionResult。", "meta"));
  }
  function renderTurn(input, chat, envelope, traceError) {
    const data = view(chat, envelope);
    const card = element("article", undefined, "turn");
    card.append(element("h2", "用户 · " + input.user_id), element("p", input.message));
    card.append(element("p", `${data.request_id} · ${data.topology} / ${data.agent_type} · Agent ${data.latency_ms} ms`, "meta"));
    card.append(element("p", `Tools: ${data.tools_used.join(", ") || "未调用"}`, "meta"));
    card.append(element("h3", "Agent 最终回答"), element("p", chat.response, "answer"));
    const evidence = element("div", undefined, "evidence");
    const rag = element("div", undefined, "panel");
    rag.append(element("h3", "RAG / Citations"), element("span", data.retrieval_status,
      "badge" + (data.retrieval_status === "usable" ? "" : " warning")));
    if (!data.citations.length) rag.append(element("p", "没有可用 citation；未检索、低置信度、无答案和降级状态不作为可靠来源。"));
    for (const c of data.citations) {
      rag.append(element("p", c.title), element("p", `citation: ${c.reference}\nsource: ${c.source}\npolicy_version: ${c.policy_version || "不适用"}`, "meta"));
    }
    const actions = element("div", undefined, "panel");
    actions.append(element("h3", "Policy / HITL / Action"));
    if (!data.actions.length) actions.append(element("p", "未观测到 ActionService 结果；不能从 Agent 回复推定动作成功。"));
    data.actions.forEach(action => renderAction(actions, action, input.user_id, chat.request_id));
    evidence.append(rag, actions); card.append(evidence);
    const tools = element("div", undefined, "panel");
    tools.append(element("h3", "Tool Trace · 执行证据"));
    if (!data.trace) tools.append(element("p", traceError || "Trace 未找到（有界内存记录可能已淘汰）。", "error"));
    for (const call of data.calls) {
      json(tools, `${call.tool_name} · ${call.risk_level} · ${call.latency_ms} ms`, {
        validated_input: call.validated_input, success: call.success, result_success: call.result_success,
        business_result: call.business_result, action_result: call.action_result, helper_result: call.helper_result,
        retrieval_status: call.retrieval_status, citations: call.citations,
        error_code: call.error_code, error_type: call.error_type, error: call.error});
    }
    if (data.trace) json(tools, "Memory / Request timing", {
      memory: data.trace.memory || "未观测", request_latency_ms: data.trace.request_latency_ms,
      latency_scope: data.trace.latency_scope, model_call_count: data.trace.model_call_count,
      model_observation_scope: data.trace.model_observation_scope});
    const raw = element("details"); raw.append(element("summary", "原始 API / Trace JSON"));
    raw.append(element("pre", pretty({chat, trace: envelope}))); tools.append(raw); card.append(tools);
    $("turns").prepend(card);
    return card;
  }
  api.renderTurn = renderTurn;
  $("chat-form").addEventListener("submit", async event => {
    event.preventDefault(); if (busy) return;
    const input = {message: $("message").value.trim(), user_id: $("user-id").value.trim(),
      conv_id: $("conv-id").value.trim() || null};
    if (!input.message || !input.user_id) return;
    setBusy(true); $("status").textContent = "运行中…";
    try {
      const chat = await request("/chat", input);
      $("conv-id").value = chat.conv_id;
      let envelope = null, traceError = null;
      try {envelope = await request(`/trace/tool/${encodeURIComponent(chat.request_id)}`);}
      catch (error) {traceError = error.message;}
      renderTurn(input, chat, envelope, traceError);
      $("status").textContent = "已收到响应";
    } catch (error) {$("status").textContent = error.message;}
    finally {setBusy(false);}
  });
  $("new-conversation").addEventListener("click", () => {$("conv-id").value = ""; $("status").textContent = "下一次请求新建会话";});
  $("user-id").addEventListener("change", () => {$("conv-id").value = "";});
  fetch("/demo-assets/scenarios.json").then(r => {if (!r.ok) throw new Error("场景加载失败"); return r.json();}).then(scenarios => {
    for (const scenario of scenarios) {
      const button = element("button", scenario.label);
      button.type = "button"; button.disabled = busy;
      button.addEventListener("click", () => {
        $("message").value = scenario.message; $("user-id").value = scenario.user_id;
        $("conv-id").value = ""; $("status").textContent = "已填入场景，发送以获取真实结果";
      });
      $("scenarios").append(button);
    }
  }).catch(error => {$("status").textContent = error.message;});
})(typeof globalThis !== "undefined" ? globalThis : this);
