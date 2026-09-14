'use strict';

function timeFields(f, choices=false, prefix="") {
  return `<div class="field full"><label class="label" for="${prefix}end-day">Session ends</label><select id="${prefix}end-day" name="end_day_offset"><option value="0" ${!f.end_day_offset?'selected':''}>On the start date</option><option value="1" ${f.end_day_offset?'selected':''}>The next day (overnight)</option></select><p class="hint">Affected dates and recurring weekdays refer to when each session starts.</p></div>${choices?`<div id="time-choices" class="field full">${foldFields(f.dates||[],f.time_choices||{})}</div><div class="field full"><button class="button secondary" type="button" data-capability="preview-times">Check exact session times</button><div id="time-preview" role="status"></div></div>`:''}`;
}
function foldFields(dates,choices) {
  const valid=[...new Set(dates)].filter(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)).slice(0,12);
  return `<details><summary class="details-summary">Daylight-saving repeated-hour choices</summary><p class="hint">Leave automatic unless a clock time occurs twice. First means before clocks move back; second means after. Nonexistent spring-forward times must be changed.</p>${valid.map(d=>`<fieldset><legend>${esc(d)} session</legend><div class="grid-2">${['start','end'].map(side=>`<div><label class="label" for="${side}-fold-${d}">${side==='start'?'Start':'End'} occurrence</label><select id="${side}-fold-${d}" name="${side}_fold:${d}">${[['','Automatic (unambiguous)'],['0','First occurrence'],['1','Second occurrence']].map(([value,label])=>`<option value="${value}" ${String(choices[d]?.[side+'_fold']??'')===value?'selected':''}>${label}</option>`).join('')}</select></div>`).join('')}</div></fieldset>`).join('')}</details>`;
}
function timeChoices(data) {
  const choices={};
  for(const [key,value] of data) if(/^(start|end)_fold:/.test(key)&&value!==''){
    const [side,day]=key.split(':');(choices[day]??={})[side]=Number(value);
  }
  return choices;
}
function reviewFacts(data) {
  return {program:state.data.program.name,kind:data.get('kind'),dates:String(data.get('dates')).split(',').map(x=>x.trim()).filter(Boolean),location:data.get('location'),room:data.get('room'),start_time:data.get('start_time'),end_time:data.get('end_time'),end_day_offset:Number(data.get('end_day_offset')||0),time_choices:timeChoices(data),timezone:state.data.program.timezone};
}
function directoryPanel() {
  const owner=state.data.mode==='pilot'&&state.data.actor.role==='owner';
  const preview=state.directoryPreview?.workspace_id===state.data.workspace_id?state.directoryPreview:null;
  return `<section class="panel spaced-panel"><h2>Community directory exchange</h2><p>Export this confirmed program as an Open Referral HSDS 3.2 service record.</p><a class="button secondary" href="/api/directory/export">Download HSDS JSON</a>${owner&&state.data.directory_source?'<a class="text-button" href="/api/directory/source">Download original imported record</a>':''}${owner?`<hr><label class="label" for="directory-file">Import directory services</label><input class="input" id="directory-file" type="file" accept="application/json,.json"><p class="hint">HSDS 3.2 service JSON, array or services collection; up to 50 services and 2 MB. Preview first, then review one service at a time.</p><div id="directory-message" role="status"></div>${preview?`<label class="label" for="directory-service">Choose a service to review</label><select id="directory-service">${preview.services.map(s=>`<option value="${s.index}" ${s.index===state.directoryIndex?'selected':''}>${esc(s.name)} · ${esc(s.status)}</option>`).join('')}</select>${directoryForm(preview.services[state.directoryIndex||0])}`:''}`:'<p class="hint">An organization owner can import services into new, unconfirmed programs.</p>'}</section>`;
}
function importField(name,label,value,type="text",extra="") {return field(name,label,value,type,extra).replaceAll(`id="${name}"`,`id="import-${name}"`).replaceAll(`for="${name}"`,`for="import-${name}"`);}
function directoryForm(item) {
  const p=item.program;
  return `<form id="directory-confirm" class="form-panel"><h3>Review imported program</h3><p>Source organization: ${esc(item.source_organization||'Not supplied')}</p><ul>${item.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul><div class="grid-2">${importField('name','Imported program name',p.name,'text','maxlength="100"')}${importField('schedule','Schedule description',p.schedule,'text','maxlength="120"')}${importField('timezone','Confirm IANA timezone',p.timezone)}${importField('location','Confirm street address',p.location,'text','maxlength="160"')}${importField('room','Confirm room',p.room,'text','maxlength="80"')}${importField('start_time','Starts at',p.start_time,'time')}${importField('end_time','Ends at',p.end_time,'time')}${timeFields(p,false,"import-")}</div><fieldset><legend>Confirm recurring start weekdays</legend><div class="examples">${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((day,i)=>`<label class="check-label"><input type="checkbox" name="weekdays" value="${i}" ${p.weekdays.includes(i)?'checked':''}>${day}</label>`).join('')}</div></fieldset><label class="check-label"><input type="checkbox" name="confirmed" required>I am authorized to manage this service and have reviewed these imported details.</label><button class="button" type="submit">Create unconfirmed program</button></form>`;
}
function inspectionPanel(c) {
  if(state.data.mode!=='pilot'||!c.facts||c.state==='SUPERSEDED')return '';
  const history=(state.data.external_checks||[]).filter(x=>x.change_id===c.id);
  return `<section class="panel spaced-panel"><h2>Inspect an external copy</h2><p>Compare a public HTTPS page or PDF with this notice’s confirmed facts. Checks read the copy once; they do not edit it.</p>${state.data.actor.role!=='viewer'?`<form id="inspect-copy"><label class="label" for="copy-url">Public notice URL</label><input class="input" id="copy-url" name="url" type="url" required maxlength="2048" placeholder="https://community.example.org/class-notice"><label class="check-label"><input type="checkbox" name="confirmed" required>This is a public copy I intend to inspect; the request will be sent to that website.</label><button class="button secondary" type="submit">Compare external copy</button><p id="inspection-message" role="status"></p></form>`:''}<p class="hint">HTML, plain text or PDFs up to 3 pages/5 MB. Login pages and JavaScript-only content may require manual inspection. These checks never mark the partner task as verified.</p>${history.map(h=>`<article class="spaced-panel"><h3>${h.result.state==='TEXT_MATCH'?'Expected text found — review context':'Review external copy'}</h3><a href="${esc(h.result.url)}" target="_blank" rel="noopener noreferrer">Open observed copy</a><p class="hint">Revision ${h.revision}${h.revision!==c.revision?' — older revision':''} · ${timeLabel(h.created_at)} · ${esc(h.result.media_type)}${h.result.ocr?' · OCR used':''}</p><div class="table-scroll"><table><thead><tr><th>Field</th><th>Expected</th><th>Observation</th></tr></thead><tbody>${h.result.fields.map(f=>`<tr><th scope="row">${esc(f.field.replaceAll('_',' '))}</th><td>${esc(f.expected)}</td><td>${f.state==='TEXT_FOUND'?'Text found':'Not found in this format'}${f.excerpt?`<small>${esc(f.excerpt)}</small>`:''}</td></tr>`).join('')}</tbody></table></div><p class="hint">${esc(h.result.limitations)}</p><details><summary>Observation fingerprint</summary><code>${esc(h.result.sha256)}</code></details></article>`).join('')}</section>`;
}
const capabilitiesPrograms=programs;
programs=function(){return capabilitiesPrograms()+directoryPanel();};
const capabilitiesDetail=detail;
detail=function(){const c=current();return capabilitiesDetail()+(c?inspectionPanel(c):'');};

document.addEventListener('change',async event=>{
  if(event.target.id==='next_dates') {$('#followup-time-choices').innerHTML=foldFields(event.target.value.split(',').map(x=>x.trim()),timeChoices(new FormData(event.target.form)));}
  if(event.target.id==='dates') {
    const form=event.target.form;
    $('#time-choices').innerHTML=foldFields(event.target.value.split(',').map(x=>x.trim()),timeChoices(new FormData(form)));
  }
  if(event.target.id==='directory-service'){state.directoryIndex=Number(event.target.value);draw();}
  if(event.target.id!=='directory-file')return;
  const file=event.target.files[0];if(!file)return;
  const message=$('#directory-message');message.textContent='Validating directory records…';
  try {
    if(file.size>2*1024**2)throw new Error('Directory files must be no larger than 2 MB.');
    const body=JSON.parse(await file.text());
    const result=await api('/api/directory/preview',body);
    state.directoryPreview={...result,workspace_id:state.data.workspace_id};state.directoryIndex=0;draw();
  } catch(error){message.textContent=error.message;}
});
document.addEventListener('click',async event=>{
  if(!event.target.closest('[data-capability="preview-times"]'))return;
  const out=$('#time-preview');out.textContent='Checking timezones…';
  try{const result=await api('/api/session-times',reviewFacts(new FormData($('#review-form'))));out.innerHTML=`<ul>${result.occurrences.map(x=>`<li><strong>${esc(x.start)}</strong> → <strong>${esc(x.end)}</strong><br><span class="hint">UTC: ${esc(x.start_utc)} → ${esc(x.end_utc)}</span></li>`).join('')}</ul><p class="hint">These are the exact instants used for publication expiration. Save the facts before approval.</p>`;}catch(error){out.textContent=error.message;}
});
document.addEventListener('submit',async event=>{
  if(!['directory-confirm','inspect-copy'].includes(event.target.id))return;
  event.preventDefault();const form=event.target,data=new FormData(form),button=form.querySelector('[type=submit]');button.disabled=true;state.busy=true;
  try{
    if(form.id==='directory-confirm'){
      const program=Object.fromEntries(data);delete program.confirmed;
      program.weekdays=data.getAll('weekdays').map(Number);program.end_day_offset=Number(program.end_day_offset);program.organization=state.data.program.organization;program.contact='';program.contact_es='';program.spanish_enabled=false;
      const result=await api('/api/directory/imports/'+state.directoryPreview.id+'/confirm',{index:state.directoryIndex||0,program,confirmed:data.has('confirmed')});
      await api('/api/account/programs/'+result.workspace_id+'/select',{});state.directoryPreview=null;await refresh();toast('Imported. Confirm the baseline before creating notices.');
    }else{
      $('#inspection-message').textContent='Reading public copy and comparing text…';
      await api('/api/changes/'+current().id+'/inspect',{url:data.get('url'),revision:current().revision,confirmed:data.has('confirmed')});await refresh();toast('Observation saved. Review the comparison below.');
    }
  }catch(error){toast(error.message,true);if($('#inspection-message'))$('#inspection-message').textContent=error.message;}
  finally{button.disabled=false;state.busy=false;}
});

if(location.hash.startsWith('#recover=')) recoveryScreen(location.hash.slice(9));
else boot();
