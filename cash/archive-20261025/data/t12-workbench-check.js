
const KEY="cartcare_workbench_v2";

function collectState(){
  const tasks={};
  document.querySelectorAll("[data-task]").forEach(card=>{
    const id=card.dataset.task; tasks[id]={};
    card.querySelectorAll("[data-field]").forEach(el=>tasks[id][el.dataset.field]=el.value);
  });
  const decisions={};
  document.querySelectorAll("[data-decision]").forEach(el=>decisions[el.dataset.decision]=el.value);
  const globals={};
  document.querySelectorAll("[data-global]").forEach(el=>globals[el.dataset.global]=el.value);
  return {version:2,updatedAt:new Date().toISOString(),tasks,decisions,globals};
}
function applyState(s){
  if(!s)return;
  document.querySelectorAll("[data-task]").forEach(card=>{
    const t=s.tasks?.[card.dataset.task]; if(!t)return;
    card.querySelectorAll("[data-field]").forEach(el=>{if(t[el.dataset.field]!==undefined)el.value=t[el.dataset.field]});
  });
  document.querySelectorAll("[data-decision]").forEach(el=>{if(s.decisions?.[el.dataset.decision]!==undefined)el.value=s.decisions[el.dataset.decision]});
  document.querySelectorAll("[data-global]").forEach(el=>{if(s.globals?.[el.dataset.global]!==undefined)el.value=s.globals[el.dataset.global]});
  updateUI(); setLastSaved(s.updatedAt);
}
function save(){
  const s=collectState(); localStorage.setItem(KEY,JSON.stringify(s)); setLastSaved(s.updatedAt);
  const el=document.getElementById("saveStatus"); el.textContent="已自动保存。";
  clearTimeout(window.__sv); window.__sv=setTimeout(()=>el.textContent="自动保存到浏览器 localStorage。",1200);
}
function updateUI(){
  const cards=[...document.querySelectorAll("[data-task]")];
  let done=0,doing=0,verify=0;
  cards.forEach(c=>{
    const st=c.querySelector('[data-field="status"]').value;
    c.classList.toggle("done",st==="done");
    if(st==="done")done++; if(st==="doing")doing++; if(st==="verify")verify++;
  });
  const pct=cards.length?Math.round(done/cards.length*100):0;
  document.getElementById("progressPct").textContent=pct+"%";
  document.getElementById("progressBar").style.width=pct+"%";
  document.getElementById("doneCount").textContent=done;
  document.getElementById("doingCount").textContent=doing;
  document.getElementById("verifyCount").textContent=verify;
}
function setLastSaved(iso){
  if(!iso)return; const d=new Date(iso);
  document.getElementById("lastSaved").textContent=d.toLocaleString("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"});
}
function exportState(){
  const s=collectState(); const blob=new Blob([JSON.stringify(s,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="cartcare-workbench-progress.json";a.click();URL.revokeObjectURL(a.href);
}
function importState(e){
  const f=e.target.files?.[0]; if(!f)return; const r=new FileReader();
  r.onload=()=>{try{const s=JSON.parse(r.result);localStorage.setItem(KEY,JSON.stringify(s));applyState(s);save()}catch(err){alert("JSON 无法解析："+err.message)}};
  r.readAsText(f,"utf-8"); e.target.value="";
}
function resetState(){
  if(!confirm("确定清空本浏览器中的工作台进度吗？"))return;
  localStorage.removeItem(KEY); location.reload();
}
function downloadSnapshot(){
  save();
  const clone=document.documentElement.cloneNode(true);
  const state=JSON.stringify(collectState()).replace(/</g,"\\u003c");
  const script=document.createElement("script");
  script.textContent=`localStorage.setItem("${KEY}", JSON.stringify(${state}));`;
  clone.querySelector("body").appendChild(script);
  const blob=new Blob(["<!DOCTYPE html>\n"+clone.outerHTML],{type:"text/html;charset=utf-8"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="CartCare-Workbench.html";a.click();URL.revokeObjectURL(a.href);
}
async function copyPrompt(){
  await navigator.clipboard.writeText(document.getElementById("handoffPrompt").innerText);
  alert("Codex Prompt 已复制");
}
async function copyProgressSummary(){
  const s=collectState();
  const rows=Object.entries(s.tasks).map(([id,t])=>`${id}: ${t.status}${t.evidence?` | ${t.evidence}`:""}${t.note?` | ${t.note}`:""}`).join("\n");
  await navigator.clipboard.writeText(`CartCare 当前工作台进度\n更新时间: ${s.updatedAt}\n\n${rows}`);
  alert("进度摘要已复制");
}
document.addEventListener("input",e=>{if(e.target.matches("[data-field],[data-decision],[data-global]")){updateUI();save()}});
document.addEventListener("change",e=>{if(e.target.matches("[data-field]")){updateUI();save()}});
const saved=localStorage.getItem(KEY); if(saved){try{applyState(JSON.parse(saved))}catch(e){}}
updateUI();
