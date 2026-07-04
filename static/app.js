'use strict';

// ── State ─────────────────────────────────────────────────────────────────
const S = { user: null, inviteCount: 0 };

// ── API ───────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401) { go('#/login'); return null; }
  if (res.status === 204)  return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Something went wrong');
  return data;
}

// ── Router ────────────────────────────────────────────────────────────────
const ROUTES = [
  [/^#\/login$/,            viewLogin],
  [/^#\/invites$/,          viewInvites],
  [/^#\/groups\/([^/?]+)$/, (m) => viewGroup(m[1])],
  [/^#\/add(?:\?(.*))?$/,   (m) => viewAddExpense(m[1])],
  [/^#\/account$/,          viewAccount],
  [/^(#\/?)?$/,             viewDashboard],
  [/^#\/groups\/?$/,        viewGroups],
];

function route() {
  const h = location.hash || '#/';
  for (const [re, fn] of ROUTES) {
    const m = h.match(re);
    if (m) { fn(m); return; }
  }
  go('#/');
}

function go(hash) { location.hash = hash; }
window.addEventListener('hashchange', route);

// ── DOM helpers ───────────────────────────────────────────────────────────
const app = () => document.getElementById('app');
function render(html) { app().innerHTML = html; }

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmt(n) {
  const a = Math.abs(n);
  return '₹' + (Number.isInteger(a) ? a.toLocaleString('en-IN') : a.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
}

function pill(bal) {
  if (bal > 0.01)  return `<span class="pill pill-pos">+${fmt(bal)}</span>`;
  if (bal < -0.01) return `<span class="pill pill-neg">−${fmt(bal)}</span>`;
  return `<span class="pill pill-nil">Settled</span>`;
}

function av(name, cls = '') {
  const initials = String(name || '?').split(' ').map(w => w[0] || '').join('').slice(0, 2).toUpperCase() || '?';
  return `<div class="av ${cls}">${initials}</div>`;
}

function toast(msg, ms = 2800) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

// ── Nav ───────────────────────────────────────────────────────────────────
const NAV_ICONS = {
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12L12 3l9 9v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  groups: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
  account: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
};

function nav(active = '') {
  const badge = S.inviteCount > 0
    ? `<span class="nav-badge">${S.inviteCount > 9 ? '9+' : S.inviteCount}</span>`
    : '';
  return `
  <nav class="hk-nav">
    <button class="nav-item ${active==='home'?'on':''}" onclick="go('#/')">
      <span class="nav-icon-wrap">${NAV_ICONS.home}${badge}</span>
      <span>Home</span>
    </button>
    <button class="nav-item ${active==='groups'?'on':''}" onclick="go('#/groups')">
      ${NAV_ICONS.groups}<span>Groups</span>
    </button>
    <div class="nav-add-wrap">
      <button class="nav-add" onclick="go('#/add')" title="Add expense">+</button>
    </div>
    <button class="nav-item ${active==='account'?'on':''}" onclick="go('#/account')">
      ${NAV_ICONS.account}<span>Account</span>
    </button>
  </nav>`;
}

// ── Login ─────────────────────────────────────────────────────────────────
function viewLogin() {
  render(`
  <div class="page">
    <div class="login-wrap">
      <div class="login-icon">📒</div>
      <div class="login-title">HisaabKitaab</div>
      <div class="login-sub">Split expenses. Stay friends.</div>
      <a href="/auth/login" class="login-btn">
        <svg width="20" height="20" viewBox="0 0 48 48">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.36-8.16 2.36-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        </svg>
        Continue with Google
      </a>
      <div class="login-terms">By continuing you agree to pay your friends back.</div>
    </div>
  </div>`);
}

// ── Dashboard ─────────────────────────────────────────────────────────────
async function viewDashboard() {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  let data;
  try { data = await api('GET', '/api/dashboard'); }
  catch { toast('Could not load data'); return; }
  if (!data) return;

  const { net_balance, activity, uid, invite_count = 0 } = data;
  S.inviteCount = invite_count;
  const name = (S.user?.name || '').split(' ')[0];

  let bannerCls, bannerLabel, bannerEmoji;
  if (net_balance > 0.01)      { bannerCls = 'banner-pos'; bannerLabel = 'You are owed'; bannerEmoji = '✅'; }
  else if (net_balance < -0.01) { bannerCls = 'banner-neg'; bannerLabel = 'You owe';      bannerEmoji = '⚡'; }
  else                           { bannerCls = 'banner-nil'; bannerLabel = 'All settled up'; bannerEmoji = '🎉'; }

  const actRows = activity.map(item => {
    if (item.type === 'expense') {
      const split = item.split_among || [];
      const share = split.length ? item.amount / split.length : 0;
      let amtHtml = '';
      if (item.paid_by === uid)        amtHtml = `<span class="amt pos">+${fmt(item.amount - (split.includes(uid) ? share : 0))}</span>`;
      else if (split.includes(uid))    amtHtml = `<span class="amt neg">−${fmt(share)}</span>`;
      return `
        <div class="hk-row">
          <div class="av av-nil" style="font-size:1rem">🧾</div>
          <div class="flex1">
            <div class="fw700 trunc">${esc(item.description || 'Expense')}</div>
            <div class="muted">${esc(item.group_name)}</div>
          </div>
          <div>${amtHtml}</div>
        </div>`;
    } else {
      let label = '';
      if (item.from_uid === uid)    label = `<span class="amt pos">Paid ${fmt(item.amount)}</span>`;
      else if (item.to_uid === uid) label = `<span class="amt neg">Received ${fmt(item.amount)}</span>`;
      else                           label = `<span class="muted">${fmt(item.amount)} settled</span>`;
      return `
        <div class="hk-row">
          <div class="av av-pos" style="font-size:1rem">✅</div>
          <div class="flex1">
            <div class="fw700">Settlement</div>
            <div class="muted">${esc(item.group_name)}</div>
          </div>
          <div>${label}</div>
        </div>`;
    }
  }).join('');

  const inviteBanner = invite_count > 0 ? `
    <div class="invite-banner tap" onclick="go('#/invites')">
      <div>
        <div class="fw700">📬 ${invite_count} pending invite${invite_count !== 1 ? 's' : ''}</div>
        <div class="muted" style="font-size:.8rem">Tap to view and respond</div>
      </div>
      <span class="chevron">›</span>
    </div>` : '';

  render(`
  <div class="page">
    <div class="hk-header">
      <div class="flex1">
        <div class="muted" style="font-size:.75rem;font-weight:600">Welcome back</div>
        <div class="hk-title">${esc(name)} 👋</div>
      </div>
      <div style="font-size:1.4rem">📒</div>
    </div>
    <div class="page-body">
      ${inviteBanner}
      <div class="hk-banner ${bannerCls}">
        <div>
          <div class="banner-label">${bannerLabel}</div>
          <div class="banner-amount">${net_balance === 0 ? '₹0' : fmt(net_balance)}</div>
        </div>
        <div class="banner-emoji">${bannerEmoji}</div>
      </div>

      ${activity.length ? `
        <div class="hk-section">Recent Activity</div>
        <div class="hk-group">${actRows}</div>
      ` : `
        <div class="empty">
          <div class="empty-icon">👥</div>
          <div class="empty-title">No activity yet</div>
          <div class="empty-sub">Create a group and add expenses to get started.</div>
        </div>
      `}
    </div>
    ${nav('home')}
  </div>`);
}

// ── Invites ───────────────────────────────────────────────────────────────
async function viewInvites() {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  let invites;
  try { invites = await api('GET', '/api/invites'); }
  catch { toast('Could not load invites'); return; }
  if (!invites) return;

  const rows = invites.map(inv => `
    <div class="hk-row" style="flex-wrap:wrap;gap:.4rem">
      ${av(inv.group_name)}
      <div class="flex1">
        <div class="fw700">${esc(inv.group_name)}</div>
        <div class="muted" style="font-size:.82rem">Invited by ${esc(inv.invited_by_name)}</div>
      </div>
      <div class="invite-actions">
        <button class="btn btn-primary" onclick="respondInvite('${inv.id}','accept',this)">Accept</button>
        <button class="btn btn-ghost" onclick="respondInvite('${inv.id}','decline',this)">Decline</button>
      </div>
    </div>`).join('');

  render(`
  <div class="page">
    <div class="hk-header">
      <button class="btn-back" onclick="go('#/')">‹</button>
      <div class="hk-title">Invites</div>
    </div>
    <div class="page-body">
      ${invites.length
        ? `<div class="hk-section">Pending Invites</div><div class="hk-group">${rows}</div>`
        : `<div class="empty">
             <div class="empty-icon">📭</div>
             <div class="empty-title">No pending invites</div>
             <div class="empty-sub">When someone invites you to a group, it will show here.</div>
           </div>`}
    </div>
    ${nav('home')}
  </div>`);
}

async function respondInvite(inviteId, action, btn) {
  if (btn) btn.disabled = true;
  try {
    await api('POST', `/api/invites/${inviteId}/${action}`);
    S.inviteCount = Math.max(0, S.inviteCount - 1);
    toast(action === 'accept' ? 'Joined group!' : 'Invite declined');
    viewInvites();
  } catch (e) {
    toast(e.message);
    if (btn) btn.disabled = false;
  }
}

// ── Groups list ───────────────────────────────────────────────────────────
async function viewGroups() {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  let groups;
  try { groups = await api('GET', '/api/groups'); }
  catch { toast('Could not load groups'); return; }
  if (!groups) return;

  const rows = groups.map(g => `
    <div class="hk-row tap" onclick="go('#/groups/${g.id}')">
      ${av(g.name)}
      <div class="flex1">
        <div class="fw700 trunc">${esc(g.name)}</div>
        <div class="muted">${g.member_count} member${g.member_count !== 1 ? 's' : ''}</div>
      </div>
      ${pill(g.my_balance)}
      <span class="chevron">›</span>
    </div>`).join('');

  render(`
  <div class="page">
    <div class="hk-header">
      <div class="hk-title" style="font-size:1.15rem">Groups</div>
    </div>
    <div class="page-body">
      ${groups.length
        ? `<div class="hk-section">Your Groups</div><div class="hk-group">${rows}</div>`
        : `<div class="empty">
             <div class="empty-icon">👥</div>
             <div class="empty-title">No groups yet</div>
             <div class="empty-sub">Create one below to start splitting expenses.</div>
           </div>`}

      <div class="hk-section">New Group</div>
      <div style="padding:0 1rem .5rem">
        <div class="form-group" style="padding:0 0 .75rem">
          <label class="form-label">Group name</label>
          <input id="new-group-name" class="form-input" placeholder="e.g. Goa Trip, Flatmates">
        </div>
        <button class="btn btn-primary" onclick="createGroup()">Create Group</button>
      </div>
    </div>
    ${nav('groups')}
  </div>`);
}

async function createGroup() {
  const nameEl = document.getElementById('new-group-name');
  const name   = nameEl?.value.trim();
  if (!name) { toast('Enter a group name'); return; }
  try {
    const g = await api('POST', '/api/groups', { name });
    go(`#/groups/${g.id}`);
  } catch (e) { toast(e.message); }
}

// ── Group Detail ──────────────────────────────────────────────────────────
async function viewGroup(gid) {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  let g;
  try { g = await api('GET', `/api/groups/${gid}`); }
  catch (e) { toast(e.message); go('#/groups'); return; }
  if (!g) return;

  window.__groupData = g;

  const { uid, my_balance, transactions, members, expenses, name, is_creator } = g;

  // Balance banner
  let bannerCls, bannerLabel;
  if (my_balance > 0.01)      { bannerCls = 'banner-pos'; bannerLabel = 'You are owed'; }
  else if (my_balance < -0.01) { bannerCls = 'banner-neg'; bannerLabel = 'You owe'; }
  else                          { bannerCls = 'banner-nil'; bannerLabel = 'All settled up'; }

  // Settle up rows (only transactions involving me)
  const myTxns = transactions.filter(t => t.from_uid === uid || t.to_uid === uid);
  const settleRows = myTxns.map((t, i) => {
    const paying = t.from_uid === uid;
    const who    = paying ? t.to_name : t.from_name;
    const label  = paying
      ? `You owe <strong>${esc(who)}</strong>`
      : `<strong>${esc(t.from_name)}</strong> owes you`;
    const amtHtml = paying
      ? `<span class="amt neg">−${fmt(t.amount)}</span>`
      : `<span class="amt pos">+${fmt(t.amount)}</span>`;
    return `
      <div class="settle-row">
        ${av(paying ? t.to_name : t.from_name, paying ? '' : 'av-pos')}
        <div class="flex1">
          <div style="font-size:.93rem">${label}</div>
          <div>${amtHtml}</div>
        </div>
        <button class="settle-btn" onclick="openSettle(${i})">Settle</button>
      </div>`;
  }).join('');

  // Members — creator sees × remove button on other members
  const memberRows = members.map(m => `
    <div class="hk-row">
      ${av(m.name)}
      <div class="flex1 fw700">${esc(m.name)}${m.uid === uid ? ' <span class="muted">(you)</span>' : ''}</div>
      ${is_creator && m.uid !== uid
        ? `<button class="btn-icon-danger" onclick="removeMember('${gid}','${m.uid}','${esc(m.name)}')" title="Remove">×</button>`
        : ''}
    </div>`).join('');

  // Expense rows — tap left side for detail, edit icon for creator or payer
  const expRows = expenses.map(e => {
    const split = e.split_among || [];
    const share = split.length ? e.amount / split.length : 0;
    const paidName = members.find(m => m.uid === e.paid_by)?.name || '?';
    let myPart = '';
    if (e.paid_by === uid)        myPart = `<span class="amt pos">+${fmt(e.amount - (split.includes(uid) ? share : 0))}</span>`;
    else if (split.includes(uid)) myPart = `<span class="amt neg">−${fmt(share)}</span>`;
    const canEdit = is_creator || e.paid_by === uid;
    return `
      <div class="hk-row">
        <div class="flex1 tap" onclick="openExpenseDetail('${gid}','${e.id}')" style="min-width:0;cursor:pointer">
          <div class="fw700 trunc">${esc(e.description || 'Expense')}</div>
          <div class="muted">${esc(paidName)} paid ${fmt(e.amount)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:.5rem;flex-shrink:0">
          ${myPart}
          ${canEdit ? `<button class="btn-icon" onclick="event.stopPropagation();openEditExpense('${gid}','${e.id}')" title="Edit">✏</button>` : ''}
        </div>
      </div>`;
  }).join('');

  // Creator sees Delete Group; non-creator sees Leave Group
  const dangerZone = is_creator
    ? `<div style="padding:.25rem 1rem 1.25rem">
         <button class="btn btn-danger" onclick="deleteGroup('${gid}')">Delete Group</button>
       </div>`
    : `<div style="padding:.25rem 1rem 1.25rem">
         <button class="btn btn-danger-outline" onclick="leaveGroup('${gid}')">Leave Group</button>
       </div>`;

  render(`
  <div class="page">
    <div class="hk-header">
      <button class="btn-back" onclick="go('#/groups')">‹</button>
      <div class="hk-title">${esc(name)}</div>
    </div>
    <div class="page-body">
      <div class="hk-banner ${bannerCls}">
        <div>
          <div class="banner-label">${bannerLabel}</div>
          <div class="banner-amount">${Math.abs(my_balance) < 0.01 ? 'All clear' : fmt(my_balance)}</div>
        </div>
        <div class="banner-emoji">${my_balance > 0.01 ? '⬆️' : my_balance < -0.01 ? '⬇️' : '🎉'}</div>
      </div>

      ${myTxns.length ? `
        <div class="hk-section">Settle Up</div>
        <div class="hk-group" style="padding:.1rem 1rem">${settleRows}</div>
      ` : transactions.length === 0 ? `
        <div style="text-align:center;padding:.75rem;font-weight:700;color:var(--pos);font-size:.9rem">
          🎉 Everyone is settled up!
        </div>
      ` : ''}

      <div class="hk-section">Members</div>
      <div class="hk-group">${memberRows}</div>

      ${is_creator ? `
      <div style="padding:0 1rem .75rem">
        <details style="background:var(--surface);border-radius:var(--r);padding:.75rem 1rem;
                        box-shadow:0 1px 4px rgba(0,0,0,.05)">
          <summary style="font-weight:700;cursor:pointer;color:var(--neg)">+ Invite Member</summary>
          <div style="padding-top:.75rem">
            <input id="mem-email" class="form-input" placeholder="friend@example.com" type="email" style="margin-bottom:.5rem">
            <button class="btn btn-ghost" onclick="addMember('${gid}')">Send Invite</button>
          </div>
        </details>
      </div>` : ''}

      <div class="hk-section">Expenses</div>
      ${expenses.length
        ? `<div class="hk-group">${expRows}</div>`
        : `<div class="empty" style="padding:1.25rem">
             <div class="empty-sub">No expenses yet. Add one with the + button.</div>
           </div>`}

      <div style="padding:.25rem 1rem .5rem">
        <button class="btn btn-primary" onclick="go('#/add?group=${gid}')">+ Add Expense</button>
      </div>

      ${dangerZone}
    </div>
    ${nav('groups')}
  </div>`);

  window.__settleData = { gid, txns: myTxns, uid };
}

function openSettle(idx) {
  const { gid, txns, uid } = window.__settleData;
  const t = txns[idx];
  const paying  = t.from_uid === uid;
  const who     = paying ? t.to_name   : t.from_name;
  const color   = paying ? 'var(--neg)' : 'var(--pos)';
  const title   = paying ? `You owe ${esc(who)}` : `${esc(t.from_name)} owes you`;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-sheet">
      <div class="modal-handle"></div>
      <div class="modal-title">Settle Up</div>
      <div class="modal-amount" style="color:${color}">${fmt(t.amount)}</div>
      <div class="modal-sub">${title}</div>
      <input id="settle-note" class="form-input" placeholder="Note: UPI, Cash…" style="margin-bottom:.25rem">
      <div class="modal-btns">
        <button class="btn btn-ghost" id="cancel-settle">Cancel</button>
        <button class="btn btn-green" id="confirm-settle">Mark as Paid ✓</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);

  overlay.querySelector('#cancel-settle').onclick = () => overlay.remove();
  overlay.querySelector('#confirm-settle').onclick = async () => {
    const note = overlay.querySelector('#settle-note').value;
    const btn  = overlay.querySelector('#confirm-settle');
    btn.disabled = true;
    try {
      await api('POST', `/api/groups/${gid}/settlements`, {
        from_uid: t.from_uid,
        to_uid:   t.to_uid,
        amount:   t.amount,
        note,
      });
      overlay.remove();
      toast('Payment recorded ✓');
      viewGroup(gid);
    } catch (e) {
      toast(e.message);
      btn.disabled = false;
    }
  };
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

// #12 — validate email format before sending invite
async function addMember(gid) {
  const email = document.getElementById('mem-email')?.value.trim();
  if (!email) { toast('Enter an email address'); return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { toast('Enter a valid email address'); return; }
  try {
    await api('POST', `/api/groups/${gid}/members`, { email });
    toast('Invite sent!');
    viewGroup(gid);
  } catch (e) { toast(e.message); }
}

// #18 — creator removes a member
async function removeMember(gid, memberUid, memberName) {
  if (!confirm(`Remove ${memberName} from this group?`)) return;
  try {
    await api('DELETE', `/api/groups/${gid}/members/${memberUid}`);
    toast(`${memberName} removed`);
    viewGroup(gid);
  } catch (e) { toast(e.message); }
}

// #17 — non-creator leaves a group
async function leaveGroup(gid) {
  if (!confirm('Leave this group? Your balance must be zero.')) return;
  try {
    await api('POST', `/api/groups/${gid}/leave`);
    toast('You left the group');
    go('#/groups');
  } catch (e) { toast(e.message); }
}

// #19 — creator deletes a group (backend requires settled debts)
async function deleteGroup(gid) {
  if (!confirm('Delete this group? All data will be permanently removed.')) return;
  try {
    await api('DELETE', `/api/groups/${gid}`);
    toast('Group deleted');
    go('#/groups');
  } catch (e) { toast(e.message); }
}

// Expense detail modal — any group member can view full breakdown
function openExpenseDetail(gid, eid) {
  const g = window.__groupData;
  if (!g) return;
  const e = g.expenses.find(x => x.id === eid);
  if (!e) return;

  const members = g.members;
  const split   = e.split_among || [];
  const share   = split.length ? Math.round((e.amount / split.length) * 100) / 100 : 0;
  const paidName = members.find(m => m.uid === e.paid_by)?.name || '?';
  const date = e.created_at
    ? new Date(e.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';

  const splitRows = split.map(uid => {
    const name = members.find(m => m.uid === uid)?.name || uid.slice(0, 8);
    return `
      <div class="hk-row" style="padding:.55rem 1rem">
        ${av(name)}
        <div class="flex1 fw700">${esc(name)}</div>
        <span class="amt neg">−${fmt(share)}</span>
      </div>`;
  }).join('');

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-sheet" style="max-height:85dvh;overflow-y:auto">
      <div class="modal-handle"></div>
      <div class="modal-title">${esc(e.description || 'Expense')}</div>
      <div class="modal-amount">${fmt(e.amount)}</div>
      <div class="modal-sub">Paid by <strong>${esc(paidName)}</strong>${date ? ' &nbsp;·&nbsp; ' + date : ''}</div>
      <div class="hk-section" style="padding:.85rem 0 .3rem">
        Split among ${split.length} person${split.length !== 1 ? 's' : ''} · ${fmt(share)} each
      </div>
      <div class="hk-group" style="margin:0 0 1rem">${splitRows}</div>
      <button class="btn btn-ghost" id="close-detail">Close</button>
    </div>`;

  document.body.appendChild(overlay);
  overlay.querySelector('#close-detail').onclick = () => overlay.remove();
  overlay.addEventListener('click', ev => { if (ev.target === overlay) overlay.remove(); });
}

// #25 — edit expense modal (pre-filled, PUT request)
function openEditExpense(gid, eid) {
  const g = window.__groupData;
  if (!g) return;
  const e = g.expenses.find(x => x.id === eid);
  if (!e) return;

  const paidByOptions = g.members.map(m =>
    `<option value="${m.uid}" ${m.uid === e.paid_by ? 'selected' : ''}>${esc(m.name)}</option>`
  ).join('');

  const splitChecks = g.members.map(m => `
    <label class="check-item" style="padding:.55rem 1rem">
      <input type="checkbox" value="${m.uid}" ${(e.split_among || []).includes(m.uid) ? 'checked' : ''}>
      ${av(m.name)}
      <span class="fw700">${esc(m.name)}</span>
    </label>`).join('');

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-sheet" style="max-height:90dvh;overflow-y:auto">
      <div class="modal-handle"></div>
      <div class="modal-title">Edit Expense</div>
      <div class="form-group" style="padding:0 0 .6rem">
        <label class="form-label">Description</label>
        <input id="edit-desc" class="form-input" value="${esc(e.description)}" placeholder="Description">
      </div>
      <div class="form-group" style="padding:0 0 .6rem">
        <label class="form-label">Amount (₹)</label>
        <input id="edit-amount" class="form-input" type="number" min="0.01" step="0.01" value="${(+e.amount).toFixed(2)}">
      </div>
      <div class="form-group" style="padding:0 0 .6rem">
        <label class="form-label">Paid by</label>
        <select id="edit-paidby" class="form-select">${paidByOptions}</select>
      </div>
      <div class="form-group" style="padding:0 0 .6rem">
        <label class="form-label">Split among</label>
        <div class="hk-group" style="margin:0" id="edit-split-list">${splitChecks}</div>
      </div>
      <div class="modal-btns">
        <button class="btn btn-ghost" id="cancel-edit">Cancel</button>
        <button class="btn btn-primary" id="confirm-edit">Save Changes</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  overlay.querySelector('#cancel-edit').onclick = () => overlay.remove();
  overlay.addEventListener('click', ev => { if (ev.target === overlay) overlay.remove(); });

  overlay.querySelector('#confirm-edit').onclick = async () => {
    const desc   = overlay.querySelector('#edit-desc').value.trim();
    const amount = parseFloat(overlay.querySelector('#edit-amount').value);
    const paidBy = overlay.querySelector('#edit-paidby').value;
    const split  = [...overlay.querySelectorAll('#edit-split-list input:checked')].map(el => el.value);

    if (!desc)                  { toast('Enter a description'); return; }
    if (!amount || amount <= 0) { toast('Enter a valid amount'); return; }
    if (!split.length)          { toast('Select at least one person'); return; }

    const btn = overlay.querySelector('#confirm-edit');
    btn.disabled = true;
    try {
      await api('PUT', `/api/groups/${gid}/expenses/${eid}`, {
        description: desc,
        amount:      Math.round(amount * 100) / 100,
        paid_by:     paidBy,
        split_among: split,
      });
      overlay.remove();
      toast('Expense updated ✓');
      viewGroup(gid);
    } catch (err) {
      toast(err.message);
      btn.disabled = false;
    }
  };
}

// ── Add Expense ───────────────────────────────────────────────────────────
async function viewAddExpense(queryStr) {
  const params  = new URLSearchParams(queryStr || '');
  const prefill = params.get('group') || '';

  let groups;
  try { groups = await api('GET', '/api/groups'); }
  catch { toast('Could not load groups'); return; }
  if (!groups) return;

  if (!groups.length) {
    render(`
    <div class="page">
      <div class="hk-header">
        <button class="btn-back" onclick="history.back()">‹</button>
        <div class="hk-title">Add Expense</div>
      </div>
      <div class="page-body">
        <div class="empty">
          <div class="empty-icon">👥</div>
          <div class="empty-title">No groups yet</div>
          <div class="empty-sub">Create a group first, then add expenses.</div>
        </div>
        <div style="padding:0 1rem"><button class="btn btn-primary" onclick="go('#/groups')">Go to Groups</button></div>
      </div>
      ${nav('add')}
    </div>`);
    return;
  }

  const selectedIdx = prefill ? Math.max(0, groups.findIndex(g => g.id === prefill)) : 0;
  window.__addExpState = { groups, selectedIdx, members: [] };

  renderAddExpenseForm();
  await loadGroupMembers();
}

function renderAddExpenseForm() {
  const { groups, selectedIdx } = window.__addExpState;

  const groupOptions = groups.map((g, i) =>
    `<option value="${i}" ${i === selectedIdx ? 'selected' : ''}>${esc(g.name)}</option>`
  ).join('');

  render(`
  <div class="page">
    <div class="hk-header">
      <button class="btn-back" onclick="history.back()">‹</button>
      <div class="hk-title">Add Expense</div>
    </div>
    <div class="page-body">
      <div class="form-group" style="padding-top:.75rem">
        <label class="form-label">Group</label>
        <select id="exp-group" class="form-select" onchange="onGroupChange(this.value)">
          ${groupOptions}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Description</label>
        <input id="exp-desc" class="form-input" placeholder="Dinner, Petrol, Hotel…">
      </div>
      <div class="form-group">
        <label class="form-label">Amount (₹)</label>
        <input id="exp-amount" class="form-input" type="number" min="0.01" step="0.01"
               placeholder="0.00" oninput="updatePreview()">
      </div>
      <div class="form-group">
        <label class="form-label">Paid by</label>
        <select id="exp-paidby" class="form-select">
          <option>Loading…</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Split among</label>
        <div id="split-list" class="hk-group" style="margin:0;padding:.1rem 0">
          <div class="hk-row muted">Loading members…</div>
        </div>
      </div>
      <div id="preview-wrap"></div>
      <div style="padding:0 1rem .5rem">
        <button id="submit-expense-btn" class="btn btn-primary" onclick="submitExpense()">Add Expense</button>
      </div>
    </div>
    ${nav('add')}
  </div>`);
}

async function loadGroupMembers() {
  const { groups, selectedIdx } = window.__addExpState;
  const gid = groups[selectedIdx].id;
  let g;
  try { g = await api('GET', `/api/groups/${gid}`); }
  catch { toast('Could not load group members'); return; }
  if (!g) return;
  window.__addExpState.members = g.members;
  window.__addExpState.uid     = g.uid;
  renderMemberSelectors();
}

function renderMemberSelectors() {
  const { members, uid } = window.__addExpState;
  if (!members.length) return;

  const paidByEl  = document.getElementById('exp-paidby');
  const splitList = document.getElementById('split-list');
  if (!paidByEl || !splitList) return;

  paidByEl.innerHTML = members.map(m =>
    `<option value="${m.uid}" ${m.uid === uid ? 'selected' : ''}>${esc(m.name)}</option>`
  ).join('');

  splitList.innerHTML = members.map(m => `
    <label class="check-item" style="padding:.55rem 1rem">
      <input type="checkbox" value="${m.uid}" checked onchange="updatePreview()">
      ${av(m.name)}
      <span class="fw700">${esc(m.name)}</span>
    </label>`).join('');

  updatePreview();
}

function onGroupChange(idx) {
  window.__addExpState.selectedIdx = parseInt(idx);
  const desc   = document.getElementById('exp-desc')?.value;
  const amount = document.getElementById('exp-amount')?.value;
  loadGroupMembers().then(() => {
    if (desc)   document.getElementById('exp-desc').value   = desc;
    if (amount) document.getElementById('exp-amount').value = amount;
  });
}

function updatePreview() {
  const amount  = parseFloat(document.getElementById('exp-amount')?.value) || 0;
  const checked = document.querySelectorAll('#split-list input[type=checkbox]:checked');
  const wrap    = document.getElementById('preview-wrap');
  if (!wrap) return;
  if (amount > 0 && checked.length > 0) {
    const share = amount / checked.length;
    wrap.innerHTML = `
      <div class="preview-card">
        <div>
          <div class="muted" style="font-size:.7rem;font-weight:800;text-transform:uppercase;
                                    letter-spacing:.08em;margin-bottom:.2rem">Per person</div>
          <div class="preview-amount">${fmt(share)}</div>
          <div class="muted">${checked.length} people · ${fmt(amount)} total</div>
        </div>
      </div>`;
  } else {
    wrap.innerHTML = '';
  }
}

// #13 — disable submit button during submission to prevent double-tap
async function submitExpense() {
  const { groups, selectedIdx } = window.__addExpState;
  const gid    = groups[selectedIdx].id;
  const desc   = document.getElementById('exp-desc')?.value.trim();
  const amount = parseFloat(document.getElementById('exp-amount')?.value);
  const paidBy = document.getElementById('exp-paidby')?.value;
  const split  = [...document.querySelectorAll('#split-list input:checked')].map(el => el.value);

  if (!desc)               { toast('Enter a description');               return; }
  if (!amount || amount <= 0) { toast('Enter a valid amount');           return; }
  if (!split.length)       { toast('Select at least one person to split'); return; }

  const btn = document.getElementById('submit-expense-btn');
  if (btn) btn.disabled = true;

  try {
    await api('POST', `/api/groups/${gid}/expenses`, {
      description: desc,
      amount:      Math.round(amount * 100) / 100, // #27 — round to 2dp before sending
      paid_by:     paidBy,
      split_among: split,
      group_name:  groups[selectedIdx].name,
    });
    toast('Expense added ✓');
    go(`#/groups/${gid}`);
  } catch (e) {
    toast(e.message);
    if (btn) btn.disabled = false;
  }
}

// ── Account ───────────────────────────────────────────────────────────────
function viewAccount() {
  const u = S.user;
  if (!u) { go('#/login'); return; }

  const picHtml = u.picture
    ? `<img src="${esc(u.picture)}" class="profile-pic" alt="">`
    : `<div class="profile-av">${(u.name || '?')[0].toUpperCase()}</div>`;

  render(`
  <div class="page">
    <div class="hk-header">
      <div class="hk-title" style="font-size:1.1rem">Account</div>
    </div>
    <div class="page-body">
      <div class="hk-group" style="margin-top:.75rem">
        <div class="hk-row" style="gap:1rem">
          ${picHtml}
          <div>
            <div class="fw800" style="font-size:1rem">${esc(u.name)}</div>
            <div class="muted">${esc(u.email)}</div>
          </div>
        </div>
      </div>

      <div class="hk-section">About</div>
      <div class="hk-group">
        <div class="hk-row" style="justify-content:space-between">
          <span class="fw700">App</span><span class="muted">HisaabKitaab</span>
        </div>
        <div class="hk-row" style="justify-content:space-between">
          <span class="fw700">Version</span><span class="muted">2.0 · FastAPI</span>
        </div>
      </div>

      <div style="padding:.5rem 1rem">
        <a href="/auth/logout" class="btn btn-ghost" style="display:block;text-align:center;text-decoration:none">
          Sign Out
        </a>
      </div>
    </div>
    ${nav('account')}
  </div>`);
}

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get('auth_error')) {
    history.replaceState({}, '', '/');
    toast('Sign-in failed. Please try again.');
  }

  try {
    S.user = await api('GET', '/api/me');
    route();
  } catch {
    viewLogin();
  }
}

document.addEventListener('DOMContentLoaded', init);
