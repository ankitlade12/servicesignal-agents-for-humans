'use strict';

function securityPanel() {
  const enabled = state.data.security?.mfa_enabled;
  return `<section class="panel form-panel spaced-panel"><h2>Two-factor authentication</h2><p>${enabled ? 'Enabled. Sign-in requires your password and an authenticator or recovery code.' : 'Add an authenticator app to protect your organization account.'}</p>${enabled ? `<form id="mfa-disable">${field('password','Current password','','password','autocomplete="current-password"')}${field('code','Authenticator or recovery code','','text','autocomplete="one-time-code"')}<button class="button secondary" type="submit">Disable authenticator & sign out</button></form>` : state.mfaSetup ? '' : `<form id="mfa-setup">${field('password','Current password','','password','autocomplete="current-password"')}<button class="button secondary" type="submit">Set up authenticator</button></form>`}${state.mfaSetup ? `<div class="spaced-panel"><h3>Scan with your authenticator</h3><img src="${esc(state.mfaSetup.qr)}" width="180" height="180" alt="Authenticator setup QR code"><p class="hint">Or enter this setup key. Keep it private.</p><code class="wrap-code">${esc(state.mfaSetup.secret)}</code><form id="mfa-enable">${field('password','Confirm current password','','password','autocomplete="current-password"')}${field('code','Six-digit authenticator code','','text','inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}"')}<button class="button" type="submit">Enable & save recovery codes</button></form></div>` : ''}<p class="hint">${state.data.security?.email_recovery_configured ? 'Email password recovery is configured. MFA remains required during recovery.' : 'Email recovery is not configured yet. An operator can assist with account recovery.'}</p></section>`;
}

function connections() {
  const info = state.deliveryInfo;
  if (!info) return heading('Connect your approved notices.','Preview each recipient and message before sending.') + '<button class="button" data-feature="load-connections">Load delivery settings</button>';
  const changes = state.data.changes.filter(c => c.approved_at && c.state !== 'SUPERSEDED' && c.actions.some(a => a.destination==='page' && a.state==='VERIFIED'));
  return heading('Connect your approved notices.','External sends and website writes require a separate owner approval.') + `<div class="form-layout"><div><form id="delivery-draft" class="panel form-panel"><h2>Prepare a delivery</h2><label class="label" for="delivery-change">Published notice</label><select id="delivery-change" name="change_id" required>${changes.map(c=>`<option value="${esc(c.id)}">${esc(c.facts.program)} · ${esc(dateLabel(c.facts.dates))}</option>`).join('')}</select><label class="label" for="delivery-channel">Channel</label><select id="delivery-channel" name="channel"><option value="email" ${info.email_configured?'':'disabled'}>Email${info.email_configured?'':' — not configured'}</option><option value="sms" ${info.sms_configured?'':'disabled'}>SMS${info.sms_configured?'':' — not configured'}</option><option value="wordpress" ${info.wordpress.length?'':'disabled'}>WordPress${info.wordpress.length?'':' — no registered page'}</option></select>${field('target','Recipient address, international phone number, or registered page ID','','text','maxlength="254"')}<p class="hint">Registered WordPress pages: ${info.wordpress.map(x=>`${esc(x.id)} — ${esc(x.label)}`).join('; ')||'None. The operator must register a dedicated page for this program.'}</p><label class="label" for="delivery-consent">Authorization and recipient consent</label><textarea id="delivery-consent" name="consent" required minlength="10" maxlength="300" placeholder="Explain who authorized this destination and how the recipient agreed to receive this update."></textarea><button class="button" type="submit" ${changes.length&&(info.email_configured||info.sms_configured||info.wordpress.length)?'':'disabled'}>Preview delivery</button></form>${state.deliveryDraft ? deliveryPreview() : ''}</div><aside class="panel"><h2>Connection status</h2><p>Email: ${info.email_configured?'configured':'not configured'}</p><p>SMS: ${info.sms_configured?'configured':'not configured'}</p><p>WordPress: ${info.wordpress.length} registered page(s)</p><p class="hint">Credentials stay on the server. Only registered WordPress pages can be changed. An accepted message is not proof that someone received or read it.</p><button class="button secondary" data-feature="load-connections">Refresh status</button>${state.operations ? `<h3>Operations</h3><p>${state.operations.queued_jobs} queued jobs · ${state.operations.failed_jobs} failed</p><p>Scheduled backup: ${esc(state.operations.backup.state)}</p><p>Off-host backup: ${state.operations.backup.off_host?'confirmed for latest backup':'not confirmed'}</p>`:''}</aside></div><section class="panel spaced-panel"><h2>Delivery history</h2>${info.deliveries.length?info.deliveries.map(x=>`<article class="program-row"><div class="program-info"><strong>${esc(x.channel)} · ${esc(x.target)}</strong><small>${esc(x.state)} · ${timeLabel(x.created_at)}</small><p>${esc(x.detail)}</p></div>${['DRAFT','QUEUED'].includes(x.state)?`<button class="text-button" data-cancel-delivery="${esc(x.id)}">Cancel</button>`:''}</article>`).join(''):'<p>No deliveries yet.</p>'}</section>`;
}

function deliveryPreview() {
  const draft=state.deliveryDraft;
  return `<section class="panel form-panel spaced-panel"><h2>Review the exact delivery</h2><p>Status: ${esc(draft.state)}</p><pre class="evidence">${esc(draft.body.text)}</pre>${draft.body.html ? `<div class="callout">This replaces the entire content of the registered dedicated WordPress page.</div><details><summary>Existing page content</summary><pre class="evidence">${esc(draft.body.previous_content)}</pre></details><p>Destination: ${esc(draft.body.public_url)}</p>`:''}<p>Authorization: ${esc(draft.body.consent)}</p><form id="delivery-approve"><label class="check-label"><input type="checkbox" name="confirmed" required><span>I reviewed the exact recipient/destination, content and consent. Authorize this send or page replacement.</span></label><button class="button" type="submit" ${draft.state==='DRAFT'?'':'disabled'}>Approve external delivery</button></form></section>`;
}

const baseTeam = team;
team = function() { return baseTeam() + securityPanel() + (state.data.actor.role==='owner'&&state.operations?`<section class="panel spaced-panel"><h2>Operations</h2><p>Scheduled backup: ${esc(state.operations.backup.state)}</p><p>${state.operations.queued_jobs} queued publication jobs · ${state.operations.failed_jobs} needing attention.</p><p class="hint">Local encrypted backups and off-host copies are distinct. Latest off-host backup: ${state.operations.backup.off_host?'confirmed':'not configured or not yet completed'}.</p></section>`:''); };
const baseLoginScreen = loginScreen;
loginScreen = function(join=false) {
  state.mfaSetup=null; state.deliveryInfo=null; state.deliveryDraft=null;
  baseLoginScreen(join);
  if (!join) {
    const form=$('#account-login');
    form.querySelector('[type=submit]').insertAdjacentHTML('beforebegin','<label class="label" for="login-code">Authenticator or recovery code (if enabled)</label><input class="input" id="login-code" name="code" autocomplete="one-time-code" maxlength="100"><button type="button" class="text-button" data-feature="forgot-password">Forgot password?</button>');
  }
};

function recoveryScreen(token='') {
  state.data=null;
  state.recoveryToken=token;
  history.replaceState(null,'',location.pathname);
  $('#app').innerHTML=`<main id="main" class="login-layout"><div class="login-intro"><a class="brand" href="/">◈ ServiceSignal</a><h1>Recover your account.</h1><p>Reset links expire after 30 minutes. Existing two-factor protection stays enabled.</p></div><form id="recovery-form" class="panel form-panel"><h2>${token?'Choose a new password':'Request a reset link'}</h2><p id="recovery-message" role="status"></p>${token?field('password','New password','','password','autocomplete="new-password" minlength="12" maxlength="128"')+'<label class="label" for="recovery-code">Authenticator or recovery code (if enabled)</label><input class="input" id="recovery-code" name="code" maxlength="100" autocomplete="one-time-code">':field('email','Account email','','email','autocomplete="username"')}<button class="button" type="submit">${token?'Reset password':'Email reset link'}</button><a href="/" class="text-button">Back to sign in</a></form></main>`;
}

async function loadConnections() {
  const [info,operations]=await Promise.all([api('/api/delivery/status'),api('/api/operations')]);
  state.deliveryInfo=info; state.operations=operations;
  draw();
}

document.addEventListener('click',event=>{
  const button=event.target.closest('[data-feature],[data-cancel-delivery]');
  if(!button)return;
  if(button.dataset.feature==='forgot-password'){recoveryScreen();return;}
  if(button.dataset.feature==='codes-saved'){loginScreen();return;}
  runAction(async()=>{
    if(button.dataset.cancelDelivery){await api('/api/delivery/'+button.dataset.cancelDelivery+'/cancel',{});}
    await loadConnections();
  });
});

document.addEventListener('submit',async event=>{
  const form=event.target;
  if(!['mfa-setup','mfa-enable','mfa-disable','recovery-form','delivery-draft','delivery-approve'].includes(form.id))return;
  event.preventDefault();
  const body=Object.fromEntries(new FormData(form)),button=form.querySelector('[type=submit]');
  button.disabled=true;
  try {
    if(form.id==='mfa-setup'){state.mfaSetup=await api('/api/account/mfa/setup',body);draw();}
    if(form.id==='mfa-enable'){
      const result=await api('/api/account/mfa/enable',body);state.data=null;state.mfaSetup=null;
      $('#app').innerHTML=`<main id="main" class="public-notice"><h1>Save your recovery codes</h1><p>These codes are shown once. Store them privately; each can be used once to sign in if your authenticator is unavailable.</p><pre class="evidence">${esc(result.recovery_codes.join('\n'))}</pre><button class="button" data-feature="codes-saved">I saved these codes — sign in</button></main>`;
    }
    if(form.id==='mfa-disable'){await api('/api/account/mfa/disable',body);loginScreen();}
    if(form.id==='recovery-form'){
      if(state.recoveryToken){await api('/api/account/recovery/complete',{...body,token:state.recoveryToken});state.recoveryToken='';loginScreen();toast('Password reset. Sign in again.');}
      else {const result=await api('/api/account/recovery/request',body);$('#recovery-message').textContent=result.message;}
    }
    if(form.id==='delivery-draft'){state.deliveryDraft=await api('/api/delivery/draft',body);draw();}
    if(form.id==='delivery-approve'){await api('/api/delivery/'+state.deliveryDraft.id+'/approve',{content_hash:state.deliveryDraft.content_hash,confirmed:body.confirmed==='on'});state.deliveryDraft=null;await loadConnections();toast('Delivery approved and queued.');}
  } catch(error) {
    const target=$('#recovery-message');if(target)target.textContent=error.message;
    else toast(error.message,true);
  } finally {button.disabled=false;}
});
