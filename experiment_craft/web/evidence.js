/* Explicit, offline result reads. Collection alone calls the bound runtime. */
"use strict";
const evidenceStates = new Map();
let evidenceKey = null;
function evidenceState(id) {
  if (!evidenceStates.has(id)) evidenceStates.set(id, {page:null, offset:0, loading:false, error:"", report:null, readAt:null, auditAt:null, pending:null});
  return evidenceStates.get(id);
}
function evidencePath(id, kind, step, output) {
  return `/api/campaigns/${id}/${kind}/${encodeURIComponent(step)}/${encodeURIComponent(output)}`;
}
function redrawEvidence() { if(snapshot) renderEvidence(snapshot.campaigns.find(c=>c.id===selected)); }
async function loadArtifacts(id, after=0) {
  const state=evidenceState(id);if(state.loading)return;
  Object.assign(state,{loading:true,error:"",report:null});redrawEvidence();
  try {state.page=await api(`/api/campaigns/${id}/artifacts/${after}`);state.offset=after;state.readAt=new Date().toLocaleString();}
  catch(e){state.page=null;state.error=e.message;}
  finally{state.loading=false;redrawEvidence();}
}
async function collectOutput(id, row) {
  const state=evidenceState(id);if(state.pending)return;
  state.pending="requesting";state.error="";state.report=null;redrawEvidence();
  try {const op=await api(`/api/campaigns/${id}/collect-artifact`,true,{step:row.step,output:row.output});state.pending={id:op.id,after:snapshotRequests};await refresh();}
  catch(e){state.pending=null;state.error=e.message;}
  finally{redrawEvidence();}
}
async function viewAudit(id, row) {
  const state=evidenceState(id);state.loading=true;state.error="";state.report=null;redrawEvidence();
  try {state.report=await api(evidencePath(id,"verification",row.step,row.output)+"/json");state.auditAt=new Date().toLocaleString();}
  catch(e){state.error=e.message;}
  finally{state.loading=false;redrawEvidence();}
}
async function downloadEvidence(id, path, filename) {
  const state=evidenceState(id);state.error="";
  try {
    const blob=await api(path,false,{},true), url=URL.createObjectURL(blob), link=el("a");
    link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch(e) {state.error=e.message;state.report=null;redrawEvidence();}
}
function evidenceButton(label,key,off,fn) {
  const button=el("button",label,"secondary");button.dataset.evidence=key;button.disabled=off;button.onclick=fn;return button;
}
function renderEvidence(c) {
  if(!c)return;
  const state=evidenceState(c.id), panel=$("evidence");
  // Only a snapshot requested after the collection was accepted can show its
  // end. One without the operation means another operation took its place or
  // the dashboard restarted; either way its result is in the catalog.
  if(state.pending && state.pending!=="requesting" && snapshotRequest>state.pending.after) {
    const op=c.operations.find(o=>o.id===state.pending.id);
    if(!op){state.pending=null;state.error="This dashboard no longer reports the collection: another operation replaced it, or the dashboard restarted. Refresh artifacts to see its result.";}
    else if(!op.running) {state.pending=null;state.error=op.error?`${op.error.code}: ${op.error.message}`:"";
      if(!op.error)queueMicrotask(()=>loadArtifacts(c.id,state.offset));}
  }
  const off=!online||!!c.read_error||state.loading;
  const busy=c.operations.some(o=>o.running&&!["pause","stop"].includes(o.action));
  // Collection is advance-lane work that calls the runtime: it is off whenever
  // Continue and Refresh native state are.
  const advanceOff=!!snapshot.monitor_error||!fresh||historyError;
  const key=JSON.stringify([c.id,off,busy,advanceOff,state]);if(key===evidenceKey)return;
  const focus=panel.contains(document.activeElement)?document.activeElement.dataset.evidence:null;
  const open=panel.querySelector("details")?.open||false;
  const scrolls=Array.from(panel.querySelectorAll(".table-wrap"),x=>[x.scrollLeft,x.scrollTop]);
  const head=el("div",undefined,"section-head");head.append(el("h2","Artifacts & recorded audits"),
    evidenceButton(state.page?"Refresh artifacts":"Load artifacts","load",off||!!state.pending,()=>loadArtifacts(c.id,state.offset)));
  const children=[head,el("p",c.name,"detail-meta"),el("p","Load saved output metadata, collect a sealed file, or view the acceptance output of a certificate campaign. Reading results never starts work or runs a checker.","muted")];
  if(state.loading)children.push(el("p","Reading saved results…","detail-meta"));
  if(state.pending)children.push(el("p","Collecting the selected output through its bound runtime…","detail-meta"));
  if(state.error){const error=el("p",state.error,"error-text");error.setAttribute("role","alert");children.push(error);}
  if(c.read_error||!online)children.push(el("p","Connection or campaign state is unavailable. Previously loaded results below are retained observations.","error-text"));
  if(state.page) {
    children.push(el("p",`${state.page.total_outputs} declared outputs · Last explicit read ${state.readAt}. Refresh artifacts after native state changes; cached results are not live.`,"detail-meta"));
    const wrap=el("div",undefined,"table-wrap"), table=el("table",undefined,"artifact-table"), head=el("tr");
    ["STEP / OUTPUT","AVAILABILITY","BYTES / SHA-256","ACTIONS"].forEach(x=>head.append(el("th",x)));const thead=el("thead");thead.append(head);table.append(thead);
    table.setAttribute("role","table");thead.setAttribute("role","rowgroup");head.setAttribute("role","row");for(const th of head.children)th.setAttribute("role","columnheader");
    const body=el("tbody");body.setAttribute("role","rowgroup");
    for(const row of state.page.artifacts) {
      const tr=el("tr");tr.dataset.output=row.output;tr.dataset.step=row.step;tr.setAttribute("role","row");
      const name=el("td");name.append(el("strong",row.step),el("div",row.output));
      const meta=el("td",row.bytes===null?"Unknown":`${row.bytes} bytes`);const digest=el("div",row.sha256?row.sha256.slice(0,16)+"…":"Digest unknown","detail-meta");digest.title=row.sha256||"";meta.append(digest);
      const actions=el("td"), buttons=el("div",undefined,"artifact-actions"), suffix=`${row.step}:${row.output}`;
      buttons.append(evidenceButton("Collect",`collect:${suffix}`,off||busy||advanceOff||!!state.pending||!["sealed","retained"].includes(row.availability),()=>collectOutput(c.id,row)),
        evidenceButton("Download",`download:${suffix}`,off||row.availability!=="retained",()=>downloadEvidence(c.id,evidencePath(c.id,"artifact",row.step,row.output),`${row.step}--${row.output}`)),
        evidenceButton("View audit",`audit:${suffix}`,off||!!state.pending||row.availability==="sealed",()=>viewAudit(c.id,row)));
      actions.append(buttons);tr.append(name,el("td",row.availability),meta,actions);for(const td of tr.children)td.setAttribute("role","cell");body.append(tr);
    }
    table.append(body);wrap.append(table);children.push(wrap);
    if(!state.page.artifacts.length)children.push(el("p","No named command outputs on this page. Worker-specific results remain in the campaign report.","muted"));
    const pages=el("div",undefined,"actions");pages.append(evidenceButton("Previous outputs","previous",off||!!state.pending||state.offset===0,()=>loadArtifacts(c.id,Math.max(0,state.offset-100))),
      evidenceButton("Next outputs","next",off||!!state.pending||state.page.next_offset===null,()=>loadArtifacts(c.id,state.page.next_offset)));
    children.push(pages,el("p","View audit supports the generated CAP acceptance step. Collect a sealed receipt first. Other command shapes return an explicit unsupported result.","muted"));
  }
  if(state.report)children.push(renderAudit(c.id,state.report,off||!!state.pending,open,state.auditAt));
  panel.replaceChildren(...children);evidenceKey=key;
  panel.querySelectorAll(".table-wrap").forEach((x,i)=>{if(scrolls[i]){x.scrollLeft=scrolls[i][0];x.scrollTop=scrolls[i][1];}});
  if(focus)Array.from(panel.querySelectorAll("button")).find(b=>b.dataset.evidence===focus)?.focus({preventScroll:true});
}
function renderAudit(id,value,off,open,readAt) {
  const section=el("section",undefined,"audit-result");section.dataset.verdict=value.status;
  const title=el("div",undefined,"detail-title");title.append(el("h3","Recorded certificate audit"),badge(value.status,value.status==="reported_accepted"?"":"warn"));
  section.append(title,el("p",`Last explicit audit read ${readAt}`,"detail-meta"),el("p",`Application verdict: ${value.reported_outcome??"Unknown"} · Native step: ${value.source.step_status} · Native state: ${value.source.artifact.native_state??"Unknown"} · Exit code: ${value.source.native_process?.code??"Unknown"} · Signal: ${value.source.native_process?.signal??"None recorded"} · Execution consistent: ${value.execution_consistent??"Unknown"}`,"audit-native"));
  if(value.subject)section.append(el("p",`${value.subject.id} · ${value.subject.theorem} · Target epsilon ${value.subject.target_epsilon}`,"detail-meta"));
  section.append(el("p",value.summary?`${value.summary.reported_accepted_arms} / ${value.summary.total_arms} arms reported accepted · ${value.summary.right_censored_arms} right-censored`:
    "No retained acceptance observation. Arm counts and costs are unknown.","audit-summary"));
  if(value.arms.length) {
    const wrap=el("div",undefined,"table-wrap"),table=el("table",undefined,"audit-table"),thead=el("thead"),head=el("tr");
    ["ARM / METHOD / SEED","VERIFICATION","REPLAY","CERTIFICATE EVENT","RIGHT-CENSORED","ACCOUNTED SECONDS","REASON"].forEach(x=>head.append(el("th",x)));thead.append(head);table.append(thead);const body=el("tbody");
    for(const row of value.arms) {
      const tr=el("tr");tr.dataset.arm=row.arm;tr.title=`Candidate SHA-256: ${row.candidate_sha256}`;
      [ `${row.arm} / ${row.method} / ${row.seed}`,row.verification.outcome||row.verification.status,row.replay.outcome||row.replay.status,
        row.observation.event?"yes":"no",row.observation.right_censored?"yes":"no",row.observation.observed_seconds??"Unknown",row.observation.reason].forEach(x=>tr.append(el("td",String(x))));body.append(tr);
    }
    table.append(body);wrap.append(table);section.append(wrap);
  }
  for(const line of value.interpretation)section.append(el("p",line,"muted audit-note"));
  const downloads=el("div",undefined,"actions");for(const [format,label,file] of [["json","Download JSON","verification.json"],["md","Download Markdown","verification.md"],["csv","Download CSV","observations.csv"]])
    downloads.append(evidenceButton(label,`report:${format}`,off,()=>downloadEvidence(id,evidencePath(id,"verification",value.source.step,value.source.artifact.output)+"/"+format,file)));
  section.append(downloads);const details=el("details");details.open=open;details.append(el("summary","Subject, input and checker identities"),el("pre",JSON.stringify({subject:value.subject,source:value.source,input_hashes:value.input_hashes,checker_inputs:value.checker_inputs},null,2)));section.append(details);
  return section;
}
