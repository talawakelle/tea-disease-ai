const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
let csrf = null;
let currentUser = null;
let locations = {estates:[], divisions:[], fields:[]};
let selectedFile = null;
let qualityState = null;
let qualityCheckToken = 0;
let cameraStream = null;
let activeReviewId = null;
let allHistory = [];

function toast(msg, error=false){ const el=$('#toast'); el.textContent=msg; el.className='toast show'+(error?' error':''); setTimeout(()=>el.className='toast',2800); }
async function api(url, opts={}){
  opts.headers = opts.headers || {};
  if (csrf && ['POST','PUT','PATCH','DELETE'].includes((opts.method||'GET').toUpperCase())) opts.headers['X-CSRF-Token']=csrf;
  if (opts.json !== undefined){ opts.headers['Content-Type']='application/json'; opts.body=JSON.stringify(opts.json); delete opts.json; }
  const r=await fetch(url,opts);
  const ct=r.headers.get('content-type')||'';
  const body=ct.includes('application/json')?await r.json():await r.text();
  if(!r.ok){
    if(r.status===401 && !url.includes('/auth/login')) showAuth();
    const detail=body?.detail;
    const msg=typeof detail==='string'?detail:(detail?.message||body?.message||(typeof body==='string'?body:`HTTP ${r.status}`));
    const err=new Error(msg);err.status=r.status;err.detail=detail;err.body=body;throw err;
  }
  return body;
}
function showAuth(){ $('#appShell').classList.add('hidden'); $('#authShell').classList.remove('hidden'); }
function showApp(){ $('#authShell').classList.add('hidden'); $('#appShell').classList.remove('hidden'); }

async function boot(){
  try{
    const s=await api('/api/setup/status');
    if(s.setup_required){ showAuth(); $('#setupPanel').classList.remove('hidden'); $('#loginPanel').classList.add('hidden'); return; }
    try{ const me=await api('/api/auth/me'); applyMe(me); showApp(); await afterLogin(); }
    catch{ showAuth(); $('#loginPanel').classList.remove('hidden'); $('#setupPanel').classList.add('hidden'); }
  }catch(e){ toast(e.message,true); }
}
function applyMe(me){ currentUser=me.user; csrf=me.csrf_token; $('#brandName').textContent=me.app.name; $('#brandCompany').textContent=me.app.company; $('#userName').textContent=currentUser.display_name; $('#userRole').textContent=currentUser.role; $('#userInitial').textContent=(currentUser.display_name||'U').trim()[0].toUpperCase(); $$('.admin-only').forEach(x=>x.classList.toggle('hidden',!['owner','admin'].includes(currentUser.role))); }
async function afterLogin(){ await Promise.all([loadLocations(),loadModelChip(),loadDashboard()]); switchView('scan'); }

$('#setupForm').addEventListener('submit', async e=>{ e.preventDefault(); const f=new FormData(e.currentTarget); try{ await api('/api/setup',{method:'POST',json:Object.fromEntries(f)}); toast('Owner account created. Sign in.'); $('#setupPanel').classList.add('hidden'); $('#loginPanel').classList.remove('hidden'); }catch(err){toast(err.message,true);} });
$('#loginForm').addEventListener('submit', async e=>{ e.preventDefault(); const f=new FormData(e.currentTarget); try{ const r=await api('/api/auth/login',{method:'POST',json:Object.fromEntries(f)}); csrf=r.csrf_token; const me=await api('/api/auth/me'); applyMe(me); showApp(); await afterLogin(); }catch(err){toast(err.message,true);} });
$('#logoutBtn').addEventListener('click', async()=>{ try{await api('/api/auth/logout',{method:'POST'});}catch{} csrf=null;currentUser=null;showAuth();$('#loginPanel').classList.remove('hidden'); });

const titles={scan:['FIELD SCREENING','New Tea Leaf Scan'],dashboard:['OPERATIONS OVERVIEW','Disease Intelligence Dashboard'],history:['TRACEABILITY','Scan History'],review:['HUMAN-IN-THE-LOOP','Review Queue'],locations:['MASTER DATA','Estate / Division / Field Registry'],users:['ACCESS CONTROL','System Users'],model:['MODEL GOVERNANCE','Model & Validation']};
function switchView(name){ $$('.view').forEach(v=>v.classList.remove('active')); $(`#view-${name}`)?.classList.add('active'); $$('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===name)); $('#pageEyebrow').textContent=titles[name]?.[0]||''; $('#pageTitle').textContent=titles[name]?.[1]||''; $('.sidebar').classList.remove('open'); if(name==='dashboard')loadDashboard(); if(name==='history')loadHistory(); if(name==='review')loadReview(); if(name==='locations')renderLocationsAdmin(); if(name==='users')loadUsers(); if(name==='model')loadModelPage(); }
$('#nav').addEventListener('click',e=>{const b=e.target.closest('button[data-view]');if(b)switchView(b.dataset.view);});
$$('[data-jump]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.jump)));
$('#openHistoryBtn').addEventListener('click',()=>switchView('history'));
$('#menuBtn').addEventListener('click',()=>$('.sidebar').classList.toggle('open'));

async function loadModelChip(){ try{const m=await api('/api/model/status');const chip=$('#modelChip');$('.status-dot',chip).style.background=m.available?'#69d18a':'#e1a348';$('span:last-child',chip).textContent=m.available?`${m.version} • ready`:'model file missing';}catch{} }
async function loadLocations(){ try{locations=await api('/api/locations'); renderLocationSelects();}catch(e){toast(e.message,true);} }
function renderLocationSelects(){
  fill($('#estateSelect'),locations.estates,'id','name','Not selected');
  const currentE=+$('#estateSelect').value||null; const divs=currentE?locations.divisions.filter(x=>x.estate_id===currentE):locations.divisions;
  fill($('#divisionSelect'),divs,'id','name','Not selected');
  const currentD=+$('#divisionSelect').value||null; const fs=currentD?locations.fields.filter(x=>x.division_id===currentD):locations.fields;
  fill($('#fieldSelect'),fs,'id','field_code','Not selected');
  fill($('#divisionEstate'),locations.estates,'id','name','Choose estate');
  fill($('#fieldDivision'),locations.divisions,'id','name','Choose division');
}
function fill(sel,items,valKey,labelKey,placeholder){ if(!sel)return; const old=sel.value; sel.innerHTML=`<option value="">${placeholder}</option>`+items.map(x=>`<option value="${x[valKey]}">${escapeHtml(x[labelKey])}</option>`).join(''); if([...sel.options].some(o=>o.value===old))sel.value=old; }
$('#estateSelect').addEventListener('change',()=>{const e=+$('#estateSelect').value||null;fill($('#divisionSelect'),e?locations.divisions.filter(x=>x.estate_id===e):locations.divisions,'id','name','Not selected');$('#divisionSelect').dispatchEvent(new Event('change'));});
$('#divisionSelect').addEventListener('change',()=>{const d=+$('#divisionSelect').value||null;fill($('#fieldSelect'),d?locations.fields.filter(x=>x.division_id===d):locations.fields,'id','field_code','Not selected');});

const imageInput=$('#imageInput');
$('#chooseBtn').addEventListener('click',e=>{e.preventDefault(); imageInput.click();});
async function openLiveCamera(){
  const err=$('#cameraError');err.classList.add('hidden');err.textContent='';
  if(!navigator.mediaDevices?.getUserMedia){toast('Live camera is not supported in this browser. Use Choose Image instead.',true);return;}
  try{
    cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1440}},audio:false});
    const video=$('#cameraVideo');video.srcObject=cameraStream;$('#cameraDialog').showModal();await video.play();
  }catch(e){err.textContent='Camera access failed. Allow camera permission or use Choose Image.';err.classList.remove('hidden');toast('Camera access failed.',true);}
}
function closeLiveCamera(){
  if(cameraStream){cameraStream.getTracks().forEach(t=>t.stop());cameraStream=null;}
  $('#cameraVideo').srcObject=null;if($('#cameraDialog').open)$('#cameraDialog').close();
}
$('#cameraBtn').addEventListener('click',e=>{e.preventDefault();openLiveCamera();});
$('#cameraClose').addEventListener('click',closeLiveCamera);$('#cameraCancel').addEventListener('click',closeLiveCamera);
$('#cameraDialog').addEventListener('cancel',e=>{e.preventDefault();closeLiveCamera();});
$('#cameraCapture').addEventListener('click',()=>{
  const video=$('#cameraVideo');if(!video.videoWidth||!video.videoHeight){toast('Camera is not ready yet.',true);return;}
  const canvas=$('#cameraCanvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;const ctx=canvas.getContext('2d',{alpha:false});ctx.drawImage(video,0,0,canvas.width,canvas.height);
  canvas.toBlob(blob=>{if(!blob){toast('Could not capture photo.',true);return;}const file=new File([blob],`tea_leaf_${Date.now()}.jpg`,{type:'image/jpeg',lastModified:Date.now()});closeLiveCamera();setFile(file);},'image/jpeg',0.94);
});
imageInput.addEventListener('change',()=>setFile(imageInput.files?.[0]));
['dragenter','dragover'].forEach(ev=>$('#dropzone').addEventListener(ev,e=>{e.preventDefault();$('#dropzone').classList.add('drag');}));
['dragleave','drop'].forEach(ev=>$('#dropzone').addEventListener(ev,e=>{e.preventDefault();$('#dropzone').classList.remove('drag');}));
$('#dropzone').addEventListener('drop',e=>setFile(e.dataTransfer.files?.[0]));
function setFile(file){
  if(!file)return;
  if(!file.type.startsWith('image/')){toast('Please choose an image file.',true);return;}
  selectedFile=file;qualityState=null;qualityCheckToken+=1;
  const url=URL.createObjectURL(file);$('#imagePreview').src=url;$('#imagePreview').classList.remove('hidden');$('#dropEmpty').classList.add('hidden');
  $('#imageMeta').textContent=`${file.name} • ${(file.size/1024/1024).toFixed(2)} MB`;$('#imageMeta').classList.remove('hidden');
  $('#predictBtn').disabled=true;$('#scanError').classList.add('hidden');
  renderQualityChecking();runQualityCheck(file,qualityCheckToken);
}
function renderQualityChecking(){
  $('#qualityPanel').classList.remove('hidden');$('#qualityGrade').textContent='Checking…';$('#qualityGrade').className='quality-grade checking';$('#qualityScore').textContent='—';
  $('.quality-score-ring').style.setProperty('--quality-pct','0%');$('#qualityDecision').textContent='Inspecting image';$('#qualityDecisionText').textContent='Checking sharpness, exposure, resolution and framing before disease inference.';
  $('#qualityChecks').innerHTML='<div class="quality-check"><div><span>OpenCV</span><strong>Quality engine</strong></div><em class="qstate watch">RUNNING</em></div>';
  $('#qualityWarnings').classList.add('hidden');
}
function qualityStateLabel(ok,watch=false){return ok?(watch?'watch':'good'):'bad'}
function renderQuality(q){
  qualityState=q;const score=Number(q.quality_score||0);const passed=!!q.passed;
  $('#qualityPanel').classList.remove('hidden');$('#qualityScore').textContent=score.toFixed(0);$('.quality-score-ring').style.setProperty('--quality-pct',`${Math.max(0,Math.min(100,score))}%`);
  const grade=$('#qualityGrade');grade.textContent=q.grade||'—';grade.className='quality-grade '+(!passed?'fail':(q.grade==='Fair'||q.grade==='Poor'?'warn':'pass'));
  $('#qualityDecision').textContent=passed?'Capture accepted':'Retake required';
  $('#qualityDecisionText').textContent=passed?'The image passed the hard quality gate. AI screening can proceed.':'The image failed a hard capture-quality rule. Disease inference has been blocked.';
  const sharpGood=q.blur_variance>=80, sharpPass=q.blur_variance>=25;
  const expPass=q.brightness_mean>=20&&q.brightness_mean<=245&&q.dark_ratio<=.80&&q.bright_ratio<=.80;
  const expGood=q.brightness_mean>=45&&q.brightness_mean<=220&&q.dark_ratio<=.35&&q.bright_ratio<=.35;
  const resPass=Math.min(q.width,q.height)>=320,resGood=Math.min(q.width,q.height)>=640;
  const frameGood=q.leaf_like_coverage>=.05&&q.center_leaf_like_coverage>=.03;
  const item=(label,value,cls,state)=>`<div class="quality-check"><div><span>${label}</span><strong>${escapeHtml(value)}</strong></div><em class="qstate ${cls}">${state}</em></div>`;
  $('#qualityChecks').innerHTML=[
    item('Sharpness',`Laplacian ${Number(q.blur_variance).toFixed(0)}`,qualityStateLabel(sharpPass,!sharpGood),sharpGood?'GOOD':(sharpPass?'WATCH':'FAIL')),
    item('Exposure',`Mean ${Number(q.brightness_mean).toFixed(0)} / 255`,qualityStateLabel(expPass,!expGood),expGood?'GOOD':(expPass?'WATCH':'FAIL')),
    item('Resolution',`${q.width} × ${q.height}`,qualityStateLabel(resPass,!resGood),resGood?'GOOD':(resPass?'WATCH':'FAIL')),
    item('Leaf framing',`${(Number(q.leaf_like_coverage)*100).toFixed(0)}% broad coverage`,frameGood?'good':'watch',frameGood?'GOOD':'WATCH')
  ].join('');
  const messages=[...(q.hard_fail_reasons||[]),...(q.warnings||[])];const w=$('#qualityWarnings');
  if(messages.length){w.innerHTML=`<strong>${passed?'Capture notes':'Why this photo was blocked'}</strong><ul>${messages.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul>`;w.classList.remove('hidden');}else{w.classList.add('hidden');}
  $('#predictBtn').disabled=!passed;
  if(!passed){$('#scanError').textContent='OpenCV quality gate: retake the photo before AI diagnosis.';$('#scanError').className='inline-error quality-fail';$('#scanError').classList.remove('hidden');}
  else{$('#scanError').classList.add('hidden');$('#scanError').className='inline-error hidden';}
}
async function runQualityCheck(file,token){
  const fd=new FormData();fd.append('image',file);
  try{const q=await api('/api/quality/check',{method:'POST',body:fd});if(token!==qualityCheckToken||file!==selectedFile)return;renderQuality(q);}
  catch(err){if(token!==qualityCheckToken)return;qualityState=null;$('#predictBtn').disabled=true;$('#qualityGrade').textContent='Unavailable';$('#qualityGrade').className='quality-grade fail';$('#qualityDecision').textContent='Quality engine unavailable';$('#qualityDecisionText').textContent=err.message;$('#qualityChecks').innerHTML='';$('#scanError').textContent=err.message;$('#scanError').className='inline-error quality-fail';$('#scanError').classList.remove('hidden');toast(err.message,true);}
}
function resetScan(){selectedFile=null;qualityState=null;qualityCheckToken+=1;imageInput.value='';$('#imagePreview').classList.add('hidden');$('#dropEmpty').classList.remove('hidden');$('#imageMeta').classList.add('hidden');$('#qualityPanel').classList.add('hidden');$('#predictBtn').disabled=true;$('#scanNotes').value='';$('#resultCard').classList.add('hidden');$('#resultBusy').classList.add('hidden');$('#resultEmpty').classList.remove('hidden');$('#scanError').classList.add('hidden');}
$('#newScanBtn').addEventListener('click',resetScan);
$('#predictBtn').addEventListener('click',async()=>{
  if(!selectedFile||!qualityState?.passed)return;
  const fd=new FormData();fd.append('image',selectedFile);if($('#estateSelect').value)fd.append('estate_id',$('#estateSelect').value);if($('#divisionSelect').value)fd.append('division_id',$('#divisionSelect').value);if($('#fieldSelect').value)fd.append('field_id',$('#fieldSelect').value);if($('#scanNotes').value.trim())fd.append('notes',$('#scanNotes').value.trim());
  $('#resultEmpty').classList.add('hidden');$('#resultCard').classList.add('hidden');$('#resultBusy').classList.remove('hidden');$('#predictBtn').disabled=true;$('#scanError').classList.add('hidden');
  try{const r=await api('/api/predict',{method:'POST',body:fd});if(r.quality)renderQuality(r.quality);showResult(r);await loadDashboard();}
  catch(err){$('#resultBusy').classList.add('hidden');$('#resultEmpty').classList.remove('hidden');if(err.detail?.code==='CAPTURE_QUALITY_REJECTED'&&err.detail?.quality)renderQuality(err.detail.quality);$('#scanError').textContent=err.message;$('#scanError').className='inline-error quality-fail';$('#scanError').classList.remove('hidden');toast(err.message,true);}finally{$('#predictBtn').disabled=!qualityState?.passed;}
});
function prettyClass(s){return (s||'').replaceAll('_',' ')}
function showResult(r){
  $('#resultBusy').classList.add('hidden');$('#resultCard').classList.remove('hidden');$('#resultRef').textContent=r.scan_ref;$('#resultClass').textContent=prettyClass(r.predicted_class);
  const pct=r.confidence*100;$('#resultConfidence').textContent=`${pct.toFixed(1)}%`;$('#gaugeArc').style.strokeDashoffset=314.159*(1-r.confidence);$('#resultStatus').textContent=r.review_recommended?'REVIEW RECOMMENDED':'AI SCREENING RESULT';$('#resultStatus').classList.toggle('warn',r.review_recommended);
  $('#resultMessage').textContent=r.predicted_class==='Healthy'?'No listed disease class was the top prediction. Continue field observation.':'AI visual screening indicates this class as the most likely match.';
  $('#top3Bars').innerHTML=r.top3.map(x=>`<div class="rank-row"><span>${prettyClass(x.class)}</span><div class="rank-bar"><div style="width:${Math.max(2,x.confidence*100)}%"></div></div><strong>${(x.confidence*100).toFixed(1)}%</strong></div>`).join('');
  const rn=$('#reviewNotice');rn.classList.toggle('hidden',!r.review_recommended);rn.textContent=r.review_recommended?`Manual review recommended: ${r.review_reason}.`:'';
  $('#evModel').textContent=r.model_version;$('#evEstate').textContent=r.estate||'Not linked';$('#evField').textContent=[r.division,r.field].filter(Boolean).join(' / ')||'Not linked';$('#evTime').textContent=new Date(r.created_at).toLocaleString();
  $('#evQuality').textContent=r.quality?`${r.quality.quality_score.toFixed(0)}/100 • ${r.quality.grade}`:'Legacy scan';$('#evQualityEngine').textContent=r.quality?.engine_version||'Not recorded';
}

async function loadDashboard(){ try{const d=await api('/api/dashboard');$('#mTotal').textContent=d.total_scans;$('#mReview').textContent=d.review_queue;$('#mConfidence').textContent=`${(d.average_confidence*100).toFixed(1)}%`;$('#mQuality').textContent=d.average_capture_quality?`${d.average_capture_quality.toFixed(0)}/100`:'—';$('#mModel').textContent=d.model.available?'Ready':'Missing';$('#mModelSub').textContent=d.model.available?d.model.version:'Copy model into package';$('#reviewBadge').textContent=d.review_queue;$('#reviewBadge').classList.toggle('hidden',!d.review_queue);renderBars($('#diseaseBars'),d.disease_distribution);renderBars($('#estateBars'),d.estate_activity);$('#recentTable').innerHTML=tableHtml(d.recent); }catch(e){ if(!String(e.message).includes('Authentication'))toast(e.message,true); } }
function renderBars(el,items){if(!items?.length){el.className='bar-list empty-state';el.textContent='No data yet.';return;}el.className='bar-list';const max=Math.max(...items.map(x=>x.count));el.innerHTML=items.map(x=>`<div class="bar-item"><span title="${escapeHtml(x.label)}">${escapeHtml(prettyClass(x.label))}</span><div class="bar-track"><div class="bar-fill" style="width:${100*x.count/max}%"></div></div><strong>${x.count}</strong></div>`).join('');}
function tableHtml(rows,reviewActions=false){if(!rows?.length)return '<div class="empty-state">No records yet.</div>';return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Scan</th><th>Date</th><th>Location</th><th>AI result</th><th>Confidence</th><th>Capture</th><th>Status</th>${reviewActions?'<th></th>':''}</tr></thead><tbody>${rows.map(r=>`<tr><td class="mono">${r.scan_ref}</td><td>${new Date(r.created_at).toLocaleString()}</td><td>${escapeHtml([r.estate,r.division,r.field].filter(Boolean).join(' / ')||'—')}</td><td>${escapeHtml(prettyClass(r.predicted_class))}</td><td class="conf">${(r.confidence*100).toFixed(1)}%</td><td class="quality-cell">${qualityTag(r.quality)}</td><td>${statusTag(r)}</td>${reviewActions?`<td><button class="btn secondary small-btn review-open" data-id="${r.id}">Review</button></td>`:''}</tr>`).join('')}</tbody></table></div>`;}
function qualityTag(q){if(!q)return '<span class="tag quality-missing">legacy</span>';const cls=(q.grade==='Excellent'||q.grade==='Good')?'quality-good':'quality-fair';return `<span class="tag ${cls}" title="OpenCV capture quality">${Math.round(q.quality_score)}/100 · ${escapeHtml(q.grade)}</span>`;}
function statusTag(r){if(r.review_status!=='unreviewed')return `<span class="tag done">${escapeHtml(r.review_status)}</span>`;if(r.review_recommended)return '<span class="tag review">review</span>';return '<span class="tag">screened</span>';}

async function loadHistory(){try{allHistory=await api('/api/predictions?limit=500');renderHistory();}catch(e){toast(e.message,true);}}
function renderHistory(){const q=$('#historySearch').value.trim().toLowerCase();const rows=q?allHistory.filter(r=>JSON.stringify(r).toLowerCase().includes(q)):allHistory;$('#historyTable').innerHTML=tableHtml(rows);}
$('#historySearch').addEventListener('input',renderHistory);$('#refreshHistory').addEventListener('click',loadHistory);

async function loadReview(){try{const rows=await api('/api/predictions?limit=200&review_only=true');$('#reviewTable').innerHTML=tableHtml(rows,true);$$('.review-open').forEach(b=>b.addEventListener('click',()=>openReview(+b.dataset.id)));}catch(e){toast(e.message,true);}}
async function openReview(id){try{const r=await api(`/api/predictions/${id}`);activeReviewId=id;$('#dialogTitle').textContent=`Review ${r.scan_ref}`;$('#dialogImage').src=r.image_url;$('#dialogAI').innerHTML=`AI result: <strong>${escapeHtml(prettyClass(r.predicted_class))}</strong> at <strong>${(r.confidence*100).toFixed(1)}%</strong>${r.quality?`<br>Capture quality: <strong>${Math.round(r.quality.quality_score)}/100 · ${escapeHtml(r.quality.grade)}</strong>`:''}${r.review_reason?`<br><span class="muted">${escapeHtml(r.review_reason)}</span>`:''}`;$('#reviewStatus').value='confirmed';$('#correctedClassWrap').classList.add('hidden');$('#reviewNotes').value='';$('#reviewDialog').showModal();}catch(e){toast(e.message,true);}}
$('#reviewStatus').addEventListener('change',()=>$('#correctedClassWrap').classList.toggle('hidden',$('#reviewStatus').value!=='corrected'));
$('#dialogClose').addEventListener('click',()=>$('#reviewDialog').close());
$('#reviewForm').addEventListener('submit',async e=>{e.preventDefault();if(!activeReviewId)return;const status=$('#reviewStatus').value;try{await api(`/api/predictions/${activeReviewId}/review`,{method:'POST',json:{status,reviewed_class:status==='corrected'?$('#reviewedClass').value:null,notes:$('#reviewNotes').value||null}});$('#reviewDialog').close();toast('Review saved.');await Promise.all([loadReview(),loadDashboard()]);}catch(err){toast(err.message,true);}});

function renderLocationsAdmin(){renderLocationSelects();$('#estateList').innerHTML=locations.estates.map(x=>`<div class="simple-row"><span>${escapeHtml(x.name)}</span><small>#${x.id}</small></div>`).join('')||'<div class="empty-state">No estates.</div>';$('#divisionList').innerHTML=locations.divisions.map(x=>`<div class="simple-row"><span>${escapeHtml(x.name)}</span><small>${escapeHtml(locations.estates.find(e=>e.id===x.estate_id)?.name||'')}</small></div>`).join('')||'<div class="empty-state">No divisions.</div>';$('#fieldList').innerHTML=locations.fields.map(x=>`<div class="simple-row"><span><strong>${escapeHtml(x.field_code)}</strong>${x.clone?` · ${escapeHtml(x.clone)}`:''}</span><small>${x.hectares??'—'} ha</small></div>`).join('')||'<div class="empty-state">No fields.</div>';}
$('#estateForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await api('/api/locations/estates',{method:'POST',json:Object.fromEntries(f)});e.currentTarget.reset();await loadLocations();renderLocationsAdmin();toast('Estate added.');}catch(err){toast(err.message,true);}});
$('#divisionForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget);const p=Object.fromEntries(f);p.estate_id=+p.estate_id;try{await api('/api/locations/divisions',{method:'POST',json:p});e.currentTarget.reset();await loadLocations();renderLocationsAdmin();toast('Division added.');}catch(err){toast(err.message,true);}});
$('#fieldForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget);const p=Object.fromEntries(f);p.division_id=+p.division_id;p.hectares=p.hectares?+p.hectares:null;p.clone=p.clone||null;try{await api('/api/locations/fields',{method:'POST',json:p});e.currentTarget.reset();await loadLocations();renderLocationsAdmin();toast('Field added.');}catch(err){toast(err.message,true);}});

async function loadUsers(){if(!['owner','admin'].includes(currentUser?.role))return;try{const rows=await api('/api/users');$('#userTable').innerHTML=`<div class="table-wrap"><table class="data-table"><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th></tr></thead><tbody>${rows.map(u=>`<tr><td>${escapeHtml(u.display_name)}</td><td class="mono">${escapeHtml(u.username)}</td><td>${escapeHtml(u.role)}</td><td>${u.is_active?'Active':'Disabled'}</td></tr>`).join('')}</tbody></table></div>`;}catch(e){toast(e.message,true);}}
$('#userForm').addEventListener('submit',async e=>{e.preventDefault();const p=Object.fromEntries(new FormData(e.currentTarget));try{await api('/api/users',{method:'POST',json:p});e.currentTarget.reset();await loadUsers();toast('User created.');}catch(err){toast(err.message,true);}});

async function loadModelPage(){try{const m=await api('/api/model/status');$('#modelNameBig').textContent=m.version;$('#modelAvailability').textContent=m.available?`Ready • ${String(m.format).toUpperCase()}`:'Model file missing';$('#modelAvailability').className='availability '+(m.available?'ok':'bad');$('#localValidation').textContent=m.local_validation_status;$('#modelDetails').innerHTML=`<div><span>Model path</span>${escapeHtml(m.path||'Not found')}</div><div><span>SHA-256</span>${escapeHtml(m.sha256||'Not available')}</div><div><span>Format</span>${escapeHtml(m.format||'—')}</div><div><span>Version</span>${escapeHtml(m.version)}</div>`;const q=m.capture_quality||{};$('#cvAvailability').textContent=q.available?`Ready • OpenCV ${q.opencv_version}`:'Unavailable';$('#cvAvailability').className='pill '+(q.available?'':'warning');$('#cvDetails').innerHTML=`<div><span>Engine</span>${escapeHtml(q.engine||'—')}</div><div><span>OpenCV</span>${escapeHtml(q.opencv_version||'—')}</div><div><span>Hard blur gate</span>${escapeHtml(q.hard_gate?.blur_variance_min??'—')} Laplacian variance</div><div><span>Minimum resolution</span>${escapeHtml(q.hard_gate?.min_short_side_px??'—')} px short side</div><div><span>Preprocessing</span>EXIF orientation + colour-preserving resize only</div><div><span>Scope</span>Capture quality only — no lesion segmentation or severity</div>`;}catch(e){toast(e.message,true);}}

function escapeHtml(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}

boot();
