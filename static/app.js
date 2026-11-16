'use strict';

// ── State ─────────────────────────────────────────────────────────────────
const S = { user: null };

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
  [/^#\/login$/,              viewLogin],
  [/^#\/friends\/([^/?]+)$/,   (m) => viewFriend(m[1])],
  [/^#\/friends\/?$/,          viewFriends],
  [/^#\/add(?:\?(.*))?$/,      (m) => viewAddExpense(m[1])],
  [/^#\/insights$/,           () => viewInsights('month')],
  [/^#\/account$/,            viewAccount],
  [/^(#\/?)?$/,               viewDashboard],
];

let lastLoad = Date.now();
const REFRESHABLE = /^(#\/?|#\/friends(\/[^/?]+)?|#\/insights)$/;

function route() {
  lastLoad = Date.now();
  const h = location.hash || '#/';
  for (const [re, fn] of ROUTES) {
    const m = h.match(re);
    if (m) { fn(m); return; }
  }
  go('#/');
}

function go(hash) { location.hash = hash; }
window.addEventListener('hashchange', route);

const REFRESH_BTN = `<button class="btn-more" onclick="route()" title="Refresh" aria-label="Refresh">↻</button>`;

function maskUpi(u) {
  const [name, bank] = String(u || '').split('@');
  return name ? name.slice(0, 2) + '•••@' + (bank || '') : '';
}

// Eye button: a password field flips type; the UPI field flips a CSS mask (so it stays a normal text input)
function togglePw(id, btn) {
  const el = document.getElementById(id);
  const isPw = el.dataset.kind === 'pw';
  const hidden = isPw ? el.type === 'password' : el.classList.contains('masked');
  if (isPw) el.type = hidden ? 'text' : 'password';
  else el.classList.toggle('masked', !hidden);
  btn.textContent = hidden ? '🙈' : '👁';
  btn.setAttribute('aria-label', hidden ? 'Hide' : 'Show');
}

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

// Every person gets a bingo-ball colour, stable per name
const BALLS = ['#FF5A5F', '#FFB400', '#00B894', '#3D7BFF', '#9B5DE5', '#F15BB5', '#00A8E8', '#FF8C42'];
function ballColor(name) {
  let h = 0;
  for (const c of String(name || '?')) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return BALLS[h % BALLS.length];
}

function av(name, cls = '') {
  const initials = String(name || '?').trim().split(/\s+/).map(w => w[0] || '').join('').slice(0, 2).toUpperCase() || '?';
  return `<div class="av ball ${cls}" style="--ball:${ballColor(name)}"><span>${esc(initials)}</span></div>`;
}

// Per-person amounts for an expense: exact split if set, otherwise equal
function shares(e) {
  if (e.split_amounts) return e.split_amounts;
  const sp = e.split_among || [];
  const each = sp.length ? e.amount / sp.length : 0;
  return Object.fromEntries(sp.map(u => [u, each]));
}

// What this expense does to my balance (+ I'm owed, − I owe, 0 not involved)
function myDelta(e, uid) {
  const mine = shares(e)[uid] || 0;
  return e.paid_by === uid ? e.amount - mine : -mine;
}

function deltaHtml(d) {
  if (d > 0.005)  return `<span class="amt pos">+${fmt(d)}</span>`;
  if (d < -0.005) return `<span class="amt neg">−${fmt(d)}</span>`;
  return `<span class="muted" style="font-size:.78rem">not in it</span>`;
}

const CATS = [
  [/dinner|lunch|breakfast|food|restaurant|biryani|pizza|burger|meal|thali|cafe/i, '🍽️'],
  [/chai|tea|coffee|snack/i, '☕'],
  [/drink|beer|bar|pub|wine|alcohol|cocktail/i, '🍺'],
  [/cab|uber|ola|taxi|auto|metro|bus|train|flight|ticket/i, '🚕'],
  [/petrol|diesel|fuel|toll|parking/i, '⛽'],
  [/hotel|stay|room|resort|airbnb|hostel/i, '🏨'],
  [/movie|show|entry|park|ride|game/i, '🎟️'],
  [/grocer|milk|veg|mart|bigbasket|blinkit|zepto/i, '🛒'],
];
function catEmoji(desc) {
  for (const [re, em] of CATS) if (re.test(desc || '')) return em;
  return '🧾';
}

function dayLabel(iso) {
  if (!iso) return '';
  const d = new Date(iso), t = new Date(), y = new Date();
  y.setDate(t.getDate() - 1);
  if (d.toDateString() === t.toDateString()) return 'Today';
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: d.getFullYear() !== t.getFullYear() ? 'numeric' : undefined });
}

function upiLink(upi, name, amount, note) {
  return `upi://pay?pa=${encodeURIComponent(upi)}&pn=${encodeURIComponent(name)}&am=${(+amount).toFixed(2)}&cu=INR&tn=${encodeURIComponent(note)}`;
}

function waOpen(text) {
  window.open('https://wa.me/?text=' + encodeURIComponent(text), '_blank');
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
  insights: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="20" x2="6" y2="11"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="18" y1="20" x2="18" y2="14"/></svg>`,
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12L12 3l9 9v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  groups: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
  account: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
};

function nav(active = '') {
  const item = (key, hash, icon, label) => `
    <button class="nav-item ${active === key ? 'on' : ''}" onclick="go('${hash}')">${icon}<span>${label}</span></button>`;
  return `
  <nav class="hk-nav">
    ${item('home', '#/', NAV_ICONS.home, 'Home')}
    ${item('friends', '#/friends', NAV_ICONS.groups, 'Friends')}
    <div class="nav-add-wrap">
      <button class="nav-add" onclick="go('#/add')" title="Add expense">+</button>
    </div>
    ${item('insights', '#/insights', NAV_ICONS.insights, 'Insights')}
    ${item('account', '#/account', NAV_ICONS.account, 'Account')}
  </nav>`;
}

// ── Login ─────────────────────────────────────────────────────────────────
function viewLogin() {
  render(`
  <div class="page">
    <div class="login-wrap">
      <div class="login-balls">${[['B','#FF5A5F'],['I','#FFB400'],['N','#00B894'],['G','#3D7BFF'],['O','#9B5DE5']].map(([l,c],i)=>`<div class="av ball ball-xl" style="--ball:${c};animation-delay:${i*70}ms"><span>${l}</span></div>`).join('')}</div>
      <div class="login-title">HisaabKitaab</div>
      <div class="login-sub">Sign in with your mobile number and password.<br>Friends find you by your number.</div>
      <form id="login-form" class="login-form" onsubmit="submitLogin(event)">
        <label class="form-label">Mobile number</label>
        <div class="phone-field"><span>+91</span><input id="lg-mobile" type="tel" inputmode="numeric" maxlength="14" placeholder="98765 43210" autocomplete="tel" autofocus></div>
        <label class="form-label" style="margin-top:.7rem">Password</label>
        <div class="pw-field"><input id="lg-pass" class="form-input" type="password" data-kind="pw" maxlength="64" placeholder="Your password" autocomplete="current-password"><button type="button" class="pw-eye" onclick="togglePw('lg-pass', this)" aria-label="Show">👁</button></div>
        <div id="lg-new" hidden>
          <div class="hint" style="margin:.8rem 0">New here — pick a password above and tell us your name so friends recognise you.</div>
          <label class="form-label">Your name</label>
          <input id="lg-name" class="form-input" maxlength="40" placeholder="e.g. Ravi" autocomplete="name">
          <label class="form-label" style="margin-top:.7rem">UPI ID <span class="muted" style="font-weight:500">(optional)</span></label>
          <input id="lg-upi" class="form-input" placeholder="name@oksbi" autocapitalize="off" autocorrect="off" spellcheck="false">
        </div>
        <button id="lg-btn" class="btn btn-primary" style="margin-top:1rem">Continue</button>
      </form>
    </div>
  </div>`);
}

async function submitLogin(ev) {
  ev.preventDefault();
  const mobile = document.getElementById('lg-mobile').value.trim();
  const newBox = document.getElementById('lg-new');
  const password = document.getElementById('lg-pass').value;
  const name = document.getElementById('lg-name').value.trim();
  const upi  = document.getElementById('lg-upi').value.trim();
  const btn  = document.getElementById('lg-btn');
  if (!mobile) { toast('Enter your mobile number'); return; }
  if (!password) { toast('Enter your password'); return; }
  if (!newBox.hidden && !name) { toast('Enter your name'); return; }
  btn.disabled = true;
  try {
    const res = await fetch('/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile, password, name: name || null, upi: upi || null }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not sign in');
    if (data.needs_name) {
      newBox.hidden = false;
      btn.textContent = 'Create my account';
      document.getElementById('lg-name').focus();
      btn.disabled = false;
      return;
    }
    S.user = await api('GET', '/api/me');
    go('#/');
    route();
  } catch (e) {
    toast(e.message);
    btn.disabled = false;
  }
}

// ── Dashboard ─────────────────────────────────────────────────────────────
// The plan can hold several pieces for the same person (a direct part and a routed part) — show ONE row per person
function mergePlan(plan) {
  const byPair = new Map();
  for (const t of plan) {
    const key = t.from_uid + '>' + t.to_uid;
    const m = byPair.get(key) || { ...t, amount: 0, notes: [] };
    m.amount = Math.round((m.amount + t.amount) * 100) / 100;
    if (t.via.length) m.notes.push({ amount: t.amount, via: t.via });
    byPair.set(key, m);
  }
  return [...byPair.values()];
}

// "₹200 of this clears what you owe Dev" lines
function planNotes(t, paying) {
  return t.notes.map(n => paying
    ? `${fmt(n.amount)} of this also clears what you owe ${n.via.join(', ')}`
    : `${fmt(n.amount)} of this also clears what ${n.via.join(', ')} owes you`);
}

function actRow(item, uid) {
  const names = item.names || {};
  if (item.type === 'expense') {
    window.__expPool[item.id] = item;
    return `
      <div class="tl-row tap" onclick="openExpenseDetail('${item.id}')">
        <div class="tl-ico">${catEmoji(item.description)}</div>
        <div class="flex1" style="min-width:0">
          <div class="fw700 trunc">${esc(item.description || 'Expense')}</div>
          <div class="muted trunc">${esc((names[item.paid_by] || '?').split(' ')[0])} paid ${fmt(item.amount)}${item.tags?.length ? ' · ' + item.tags.map(t => '#' + esc(t)).join(' ') : ''}</div>
        </div>
        ${deltaHtml(myDelta(item, uid))}
      </div>`;
  }
  const mine = item.from_uid === uid;
  return `
    <div class="tl-row">
      <div class="tl-ico tl-ico-pay">✓</div>
      <div class="flex1" style="min-width:0">
        <div class="fw700 trunc">${mine ? 'You paid ' + esc(item.to_name.split(' ')[0]) : esc(item.from_name.split(' ')[0]) + ' paid you'}</div>
        <div class="muted trunc">${item.note ? esc(item.note) : 'Payment'}</div>
      </div>
      <span class="amt ${mine ? 'neg' : 'pos'}">${mine ? '−' : '+'}${fmt(item.amount)}</span>
    </div>`;
}

// One "Load more" for every paged list. The cursor and next URL live on the button itself.
const PAGERS = {};   // kind -> row builder, set by the view that owns the list
function moreBtn(kind, url, cursor) {
  return cursor
    ? `<button class="btn btn-ghost" data-kind="${kind}" data-url="${url}" data-cursor="${esc(cursor)}" onclick="loadMore(this)">Load more</button>`
    : '';
}

async function loadMore(btn) {
  const { kind, url, cursor } = btn.dataset;
  btn.disabled = true;
  try {
    const r = await api('GET', `${url}${url.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(cursor)}`);
    document.getElementById(`${kind}-list`).insertAdjacentHTML('beforeend', groupByDay(r.items, PAGERS[kind]));
    document.getElementById(`${kind}-more`).innerHTML = moreBtn(kind, url, r.next_cursor);
  } catch (e) { toast(e.message); btn.disabled = false; }
}

function groupByDay(items, rowFn) {
  let last = '', html = '';
  for (const it of items) {
    const d = dayLabel(it.created_at);
    if (d !== last) { html += `<div class="day-label">${esc(d)}</div>`; last = d; }
    html += rowFn(it);
  }
  return html;
}

async function viewDashboard() {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  window.__expPool = {};
  let data;
  try { data = await api('GET', '/api/dashboard'); }
  catch { toast('Could not load data'); return; }
  if (!data) return;

  const { net_balance, owed, owe, items: activity, uid, friends, next_cursor, plan } = data;
  const merged = mergePlan(plan);
  window.__plan = merged;
  PAGERS.feed = i => actRow(i, uid);
  const first = (S.user?.name || '').split(' ')[0];
  const label = net_balance > 0.01 ? 'You are owed' : net_balance < -0.01 ? 'You owe' : 'All settled up';
  const cls   = net_balance > 0.01 ? 'hero-pos' : net_balance < -0.01 ? 'hero-neg' : '';

  const pending = friends.filter(f => Math.abs(f.balance) > 0.01);
  const friendRows = pending.map(f => `
    <div class="hk-row tap" onclick="go('#/friends/${f.uid}')">
      ${av(f.name)}
      <div class="flex1" style="min-width:0">
        <div class="fw700 trunc">${esc(f.name)}</div>
        <div class="muted">${f.balance > 0 ? 'owes you' : 'you owe'}</div>
      </div>
      ${pill(f.balance)}
      <span class="chevron">›</span>
    </div>`).join('');

  render(`
  <div class="page">
    <div class="hk-header">
      <div class="flex1">
        <div class="muted" style="font-size:.75rem;font-weight:600">Welcome back</div>
        <div class="hk-title">${esc(first)} 👋</div>
      </div>
      ${REFRESH_BTN}
      ${av(S.user?.name)}
    </div>
    <div class="page-body">
      <div class="hero ${cls}">
        <div class="hero-label">${label}</div>
        <div class="hero-amt">${Math.abs(net_balance) < 0.01 ? '₹0' : fmt(net_balance)}</div>
        <div class="hero-foot">
          <div class="hero-members" style="margin:0">You get ${fmt(owed)}</div>
          <div class="hero-total">You owe ${fmt(owe)}</div>
        </div>
      </div>
      <div class="quick-actions">
        <button class="qa" onclick="go('#/add')"><span>＋</span>Add expense</button>
        <button class="qa qa-wa" onclick="go('#/friends')"><span>👥</span>Friends</button>
      </div>

      ${!friends.length ? `
        <div class="empty">
          <div class="empty-icon">🎱</div>
          <div class="empty-title">Waiting for the gang</div>
          <div class="empty-sub">Everyone who signs in shows up here. Send them the invite!</div>
        </div>` : ''}

      ${merged.length ? `<div class="hk-section">Suggested payments</div><div class="hk-group" style="padding:.1rem 1rem">${merged.map((t, i) => {
        const paying = t.from_uid === uid, o = paying ? t.to : t.from;
        return `<div class="settle-row">${av(o.name)}
          <div class="flex1" style="min-width:0">
            <div class="trunc" style="font-size:.93rem">${paying ? 'Pay' : ''} <strong>${esc(o.name)}</strong>${paying ? '' : ' pays you'}</div>
            <div class="amt ${paying ? 'neg' : 'pos'}">${fmt(t.amount)}</div>
            ${planNotes(t, paying).map(n => `<div class="muted" style="font-size:.74rem">${esc(n)}</div>`).join('')}
          </div>
          <button class="settle-btn ${paying ? '' : 'settle-btn-alt'}" onclick="openPlan(${i})">${paying ? 'Pay' : 'Received'}</button></div>`;
      }).join('')}</div>` : ''}

      ${pending.length ? `<div class="hk-section">Balances</div><div class="hk-group">${friendRows}</div>` : ''}

      ${activity.length ? `<div class="hk-section">Recent</div><div class="timeline" id="feed-list">${groupByDay(activity, PAGERS.feed)}</div>
        <div id="feed-more" style="padding:.4rem 1rem 1rem">${moreBtn('feed', '/api/feed', next_cursor)}</div>` : ''}
    </div>
    ${nav('home')}
  </div>`);
}

// ── Friends ───────────────────────────────────────────────────────────────
async function viewFriends() {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  let friends;
  try { friends = await api('GET', '/api/friends'); }
  catch { toast('Could not load friends'); return; }
  if (!friends) return;

  const rows = friends.map(f => `
    <div class="hk-row tap" onclick="go('#/friends/${f.uid}')">
      ${av(f.name)}
      <div class="flex1" style="min-width:0">
        <div class="fw700 trunc">${esc(f.name)}</div>
        <div class="muted">+91 ${esc(f.mobile)}</div>
      </div>
      ${pill(f.balance)}
      <span class="chevron">›</span>
    </div>`).join('');

  render(`
  <div class="page">
    <div class="hk-header"><div class="hk-title flex1" style="font-size:1.15rem">Friends</div>${REFRESH_BTN}</div>
    <div class="page-body">
      <div class="hint" style="margin:.75rem 1rem 0">Everyone who signs in joins automatically. Share the app with the rest of the gang:
        <button class="link-btn" onclick="inviteOnWhatsApp()">Invite on WhatsApp</button></div>
      ${friends.length
        ? `<div class="hk-section">Your friends</div><div class="hk-group">${rows}</div>`
        : `<div class="empty"><div class="empty-icon">👥</div><div class="empty-title">No friends yet</div><div class="empty-sub">Friends appear here as soon as they sign in.</div></div>`}
    </div>
    ${nav('friends')}
  </div>`);
}

function inviteOnWhatsApp() {
  const me = S.user?.name?.split(' ')[0] || 'Your friend';
  waOpen(
`Hey! 🎱 ${me} here.

I'm using *HisaabKitaab* to split our bills, trips and dinners, so we can stop scrolling the group chat for who owes what.

How to join (takes 1 minute):
1. Open ${location.origin}
2. Enter your mobile number and choose a password
3. Add your name (and UPI ID, so friends can pay you in one tap)

You'll show up in my friends list automatically. 🙌`);
}

async function addFriend() {
  const mobile = document.getElementById('fr-mobile')?.value.trim();
  if (!mobile) { toast('Enter a mobile number'); return; }
  try {
    const f = await api('POST', '/api/friends', { mobile });
    toast(`${f.name} added ✓`);
    go(`#/friends/${f.uid}`);
  } catch (e) { toast(e.message); }
}

// pair effect of one expense between me and a friend (+ they owe me)
function pairDelta(e, me, fid) {
  const sh = shares(e);
  if (e.paid_by === me)  return sh[fid] || 0;
  if (e.paid_by === fid) return -(sh[me] || 0);
  return 0;
}

async function viewFriend(fid) {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  window.__expPool = {};
  let d;
  try { d = await api('GET', `/api/friends/${fid}`); }
  catch (e) { toast(e.message); go('#/friends'); return; }
  if (!d) return;

  const { friend, balance, items, uid, next_cursor } = d;
  const fname = friend.name.split(' ')[0];
  const label = balance > 0.01 ? `${fname} owes you` : balance < -0.01 ? `You owe ${fname}` : 'You are all settled';
  const cls   = balance > 0.01 ? 'hero-pos' : balance < -0.01 ? 'hero-neg' : '';
  window.__settleData = { friend, balance, uid };

  const row = it => {
    if (it.type === 'expense') {
      window.__expPool[it.id] = it;
      const names = it.names || {};
      const pd = pairDelta(it, uid, fid);
      return `
        <div class="tl-row tap" onclick="openExpenseDetail('${it.id}')">
          <div class="tl-ico">${catEmoji(it.description)}</div>
          <div class="flex1" style="min-width:0">
            <div class="fw700 trunc">${esc(it.description)}</div>
            <div class="muted trunc">${esc((names[it.paid_by] || '?').split(' ')[0])} paid ${fmt(it.amount)}${it.split_amounts ? ' · custom' : ''}${it.tags?.length ? ' · ' + it.tags.map(t => '#' + esc(t)).join(' ') : ''}</div>
          </div>
          ${pd ? deltaHtml(pd) : '<span class="muted" style="font-size:.78rem">no effect</span>'}
        </div>`;
    }
    const mine = it.from_uid === uid;
    return `
      <div class="tl-row">
        <div class="tl-ico tl-ico-pay">✓</div>
        <div class="flex1" style="min-width:0">
          <div class="fw700 trunc">${mine ? 'You paid ' + esc(fname) : esc(fname) + ' paid you'}</div>
          <div class="muted trunc">${it.note ? esc(it.note) : 'Payment'}</div>
        </div>
        <span class="amt ${mine ? 'neg' : 'pos'}">${mine ? '−' : '+'}${fmt(it.amount)}</span>
      </div>`;
  };

  PAGERS.hist = row;
  const paying = balance < -0.01;
  const settleBtn = Math.abs(balance) > 0.01
    ? `<button class="qa qa-pay" onclick="openSettle()">${paying ? 'Pay ' + fmt(balance) : 'Received'}</button>` : '';

  render(`
  <div class="page">
    <div class="hk-header">
      <button class="btn-back" onclick="go('#/friends')">‹</button>
      <div class="flex1" style="min-width:0"><div class="hk-title trunc" style="font-size:1.05rem">${esc(friend.name)}</div></div>
      ${REFRESH_BTN}
      ${av(friend.name)}
    </div>
    <div class="page-body">
      <div class="hero ${cls}">
        <div class="hero-label">${label}</div>
        <div class="hero-amt">${Math.abs(balance) < 0.01 ? '₹0' : fmt(balance)}</div>
        <div class="hero-foot"><div class="hero-members" style="margin:0">+91 ${esc(friend.mobile)}</div>
        <div class="hero-total">${friend.upi ? `<span class="tap" title="Tap to show" onclick="this.textContent=this.dataset.v" data-v="${esc(friend.upi)}">${esc(maskUpi(friend.upi))} 👁</span>` : 'no UPI ID yet'}</div></div>
      </div>
      <div class="quick-actions">
        <button class="qa" onclick="go('#/add?friend=${fid}')"><span>＋</span>Expense</button>
        ${settleBtn}
        ${balance !== 0 ? `<button class="qa qa-wa" onclick="shareBalance()"><span>↗</span>WhatsApp</button>` : ''}
      </div>
      <div class="hk-section">History</div>
      ${items.length
        ? `<div class="timeline" id="hist-list">${groupByDay(items, row)}</div><div id="hist-more" style="padding:.4rem 1rem">${moreBtn('hist', `/api/friends/${fid}/history`, next_cursor)}</div>`
        : `<div class="empty" style="padding:2.5rem 1rem"><div class="empty-icon">🧾</div><div class="empty-title">Nothing yet</div><div class="empty-sub">Add a bill you shared with ${esc(fname)}.</div></div>`}
      <div style="height:5rem"></div>
    </div>
    ${nav('friends')}
  </div>`);
}

// ── Payments: UPI link, QR, WhatsApp ──────────────────────────────────────
// QR as a PNG data-URL (white background, quiet zone) — scans from a phone screen or a shared image
function qrPng(text) {
  const q = qrcode(0, 'M');
  q.addData(text); q.make();
  const n = q.getModuleCount(), scale = 8, margin = 4;
  const c = document.createElement('canvas');
  c.width = c.height = (n + margin * 2) * scale;
  const g = c.getContext('2d');
  g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = '#000';
  for (let r = 0; r < n; r++) for (let k = 0; k < n; k++) if (q.isDark(r, k)) g.fillRect((k + margin) * scale, (r + margin) * scale, scale, scale);
  return c.toDataURL('image/png');
}

// Clickable web link (WhatsApp won't linkify upi://) that opens a page with the QR and a Pay button
function payPage(upi, name, amount, note) {
  return `${location.origin}/pay?pa=${encodeURIComponent(upi)}&pn=${encodeURIComponent(name)}&am=${(+amount).toFixed(2)}&tn=${encodeURIComponent(note)}`;
}

// "Please pay me" message: text + one-tap pay link (my UPI ID + amount), and the QR image where the phone can share files
async function sendPayRequest(otherName, amount) {
  const fn = otherName.split(' ')[0];
  const me = S.user;
  const link = me?.upi ? payPage(me.upi, me.name, amount, 'HisaabKitaab') : '';
  const text = link
    ? `Hi ${fn} 👋\nQuick reminder from HisaabKitaab 🎱 — you owe me *${fmt(amount)}*.\n\n` +
      `💸 Pay in one tap — open the link, then scan the QR or press "Pay with UPI app":\n${link}\n\n` +
      `UPI ID: ${me.upi}\n\nOnce it's done, just send me a 👍. Thanks! 🙏`
    : `Hi ${fn} 👋\nQuick reminder from HisaabKitaab 🎱 — you owe me *${fmt(amount)}*.\n\n` +
      `Whenever you get a chance, please pay me by UPI or cash and send me a 👍. Thanks! 🙏`;
  if (link && navigator.canShare) {
    try {
      const blob = await (await fetch(qrPng(upiLink(me.upi, me.name, amount, 'HisaabKitaab')))).blob();
      const file = new File([blob], 'pay-me.png', { type: 'image/png' });
      if (navigator.canShare({ files: [file] })) { await navigator.share({ files: [file], text }); return; }
    } catch (e) { if (e?.name === 'AbortError') return; }
  }
  waOpen(text);
}

function shareBalance() {
  const { friend, balance } = window.__settleData;
  if (balance > 0) return sendPayRequest(friend.name, balance);
  waOpen(`Hi ${friend.name.split(' ')[0]} 👋\nQuick update from HisaabKitaab 🎱 — I owe you *${fmt(balance)}*.\n\nI'll pay you soon. Thanks for waiting! 🙏`);
}

// One sheet for every payment: a direct balance with a friend, or a suggested (possibly routed) payment.
// opts: { other:{uid,name,upi}, paying, amount, plan, via:[names], onDone }
function openPayment(opts) {
  const { other, paying, amount, plan, notes = [], onDone } = opts;
  const me = S.user;
  const fn = other.name.split(' ')[0];
  const note = 'HisaabKitaab settle up';

  let extra = '';
  if (plan && notes.length) extra += `<div class="hint">${notes.map(esc).join('<br>')}</div>`;
  if (paying && other.upi) {
    extra += `
      <a class="btn btn-upi" id="upi-pay" href="${esc(upiLink(other.upi, other.name, amount, note))}">Pay ${fmt(amount)} with UPI</a>
      <button class="btn btn-ghost" id="show-qr" style="margin-top:.4rem">Show QR to scan</button>
      <div id="qr-box" hidden class="qr-box"><img alt="UPI QR"><div class="upi-to">${esc(other.upi)}</div></div>`;
  } else if (paying) {
    extra += `<div class="hint">${esc(fn)} hasn't added a UPI ID yet. Pay by cash, or ask them to add it under Account.</div>`;
  } else {
    extra += `<button class="btn btn-wa" id="remind">${me.upi ? 'Send payment QR on WhatsApp' : `Remind ${esc(fn)} on WhatsApp`}</button>
      ${me.upi ? '' : '<div class="upi-to">Add your UPI ID in Account to include a QR and one-tap pay link.</div>'}`;
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-sheet" style="max-height:92dvh;overflow-y:auto">
      <div class="modal-handle"></div>
      <div class="modal-title">${paying ? `Pay ${esc(other.name)}` : `${esc(other.name)} pays you`}</div>
      <div class="modal-amount" style="color:${paying ? 'var(--neg)' : 'var(--pos)'}">${fmt(amount)}</div>
      ${extra}
      <div class="settle-done">
        <div class="hk-section" style="padding:1rem 0 .4rem">${paying ? 'Paid already?' : 'Got the money?'} Record it</div>
        <div class="form-group" style="padding:0 0 .5rem">
          <label class="form-label">Amount (₹)</label>
          <input id="settle-amt" class="form-input" type="number" inputmode="decimal" min="0.01" step="0.01" value="${amount.toFixed(2)}">
        </div>
        <input id="settle-note" class="form-input" maxlength="200" placeholder="Optional label, e.g. food #garaba #ravibirthday" style="margin-bottom:.5rem">
        <div class="modal-btns">
          <button class="btn btn-ghost" id="cancel-settle">Cancel</button>
          <button class="btn btn-green" id="confirm-settle">${paying ? 'I’ve paid ✓' : 'Got it ✓'}</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const amtEl = overlay.querySelector('#settle-amt');
  const upiEl = overlay.querySelector('#upi-pay');
  const qrBtn = overlay.querySelector('#show-qr');
  const qrBox = overlay.querySelector('#qr-box');
  const curAmt = () => { const v = parseFloat(amtEl.value); return v > 0 ? v : amount; };
  const drawQr = () => { qrBox.querySelector('img').src = qrPng(upiLink(other.upi, other.name, curAmt(), note)); };
  if (upiEl) amtEl.addEventListener('input', () => {
    upiEl.href = upiLink(other.upi, other.name, curAmt(), note);
    if (!qrBox.hidden) drawQr();
  });
  if (qrBtn) qrBtn.onclick = () => {
    qrBox.hidden = !qrBox.hidden;
    qrBtn.textContent = qrBox.hidden ? 'Show QR to scan' : 'Hide QR';
    if (!qrBox.hidden) drawQr();
  };
  const rem = overlay.querySelector('#remind');
  if (rem) rem.onclick = () => sendPayRequest(other.name, curAmt());

  overlay.querySelector('#cancel-settle').onclick = () => overlay.remove();
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  overlay.querySelector('#confirm-settle').onclick = async () => {
    const btn = overlay.querySelector('#confirm-settle');
    const amt = parseFloat(amtEl.value);
    if (!amt || amt <= 0) { toast('Enter the amount paid'); return; }
    btn.disabled = true;
    try {
      await api('POST', plan ? '/api/settle-plan' : '/api/settlements', {
        from_uid: paying ? me.uid : other.uid,
        to_uid:   paying ? other.uid : me.uid,
        amount:   Math.round(amt * 100) / 100,
        note:     overlay.querySelector('#settle-note').value,
      });
      overlay.remove();
      toast('Payment recorded ✓');
      onDone();
    } catch (e) { toast(e.message); btn.disabled = false; }
  };
}

// friend page: settle the direct balance with this friend
function openSettle() {
  const { friend, balance } = window.__settleData;
  openPayment({ other: friend, paying: balance < 0, amount: Math.abs(balance), plan: false, onDone: () => viewFriend(friend.uid) });
}

// home: a suggested payment (may be routed through someone you owe)
function openPlan(i) {
  const t = window.__plan[i];
  const paying = t.from_uid === S.user.uid;
  openPayment({ other: paying ? t.to : t.from, paying, amount: t.amount, plan: true, notes: planNotes(t, paying), onDone: viewDashboard });
}

// ── Expense detail ────────────────────────────────────────────────────────
function openExpenseDetail(eid) {
  const e = window.__expPool?.[eid];
  if (!e) return;
  const uid = S.user.uid;
  const names = e.names || {};
  const sh = shares(e);
  const ids = Object.keys(sh);
  const nameOf = id => id === uid ? 'You' : (names[id] || id);
  const date = e.created_at ? new Date(e.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  const canEdit = true;   // anyone involved can fix a mistake

  const splitRows = ids.map(u => `
    <div class="hk-row" style="padding:.55rem 1rem">
      ${av(nameOf(u))}
      <div class="flex1 fw700">${esc(nameOf(u))}${u === e.paid_by ? ' <span class="muted" style="font-weight:600">paid</span>' : ''}</div>
      <span class="amt neg">${fmt(sh[u])}</span>
    </div>`).join('');

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-sheet" style="max-height:88dvh;overflow-y:auto">
      <div class="modal-handle"></div>
      <div class="modal-title">${catEmoji(e.description)} ${esc(e.description)}</div>
      <div class="modal-amount">${fmt(e.amount)}</div>
      <div class="modal-sub">Paid by <strong>${esc(nameOf(e.paid_by))}</strong>${date ? ' &nbsp;·&nbsp; ' + date : ''}</div>
      ${e.tags?.length ? `<div class="tag-row">${e.tags.map(t => `<span class="tag">#${esc(t)}</span>`).join('')}</div>` : ''}
      ${e.note ? `<div class="modal-sub" style="margin-top:-.4rem">${esc(e.note)}</div>` : ''}
      <div class="hk-section" style="padding:.85rem 0 .3rem">${e.split_amounts ? 'Custom split' : `Split equally · ${fmt(e.amount / ids.length)} each`}</div>
      <div class="hk-group" style="margin:0 0 1rem">${splitRows}</div>
      <div class="modal-btns">
        ${canEdit ? `<button class="btn btn-danger-outline" id="del-exp">Delete</button><button class="btn btn-primary" id="edit-exp">Edit</button>` : `<button class="btn btn-ghost" id="close-detail">Close</button>`}
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', ev => { if (ev.target === overlay) overlay.remove(); });
  const close = overlay.querySelector('#close-detail');
  if (close) close.onclick = () => overlay.remove();
  const edit = overlay.querySelector('#edit-exp');
  if (edit) edit.onclick = () => { overlay.remove(); go(`#/add?edit=${eid}`); };
  const del = overlay.querySelector('#del-exp');
  if (del) del.onclick = async () => {
    if (!confirm(`Delete “${e.description}”? Balances will update.`)) return;
    del.disabled = true;
    try { await api('DELETE', `/api/expenses/${eid}`); overlay.remove(); toast('Expense deleted'); route(); }
    catch (err) { toast(err.message); del.disabled = false; }
  };
}

// ── Add / edit expense ────────────────────────────────────────────────────
const QUICK = [['🍽️', 'Dinner'], ['☕', 'Chai & snacks'], ['🍺', 'Drinks'], ['🚕', 'Cab'], ['⛽', 'Petrol'], ['🏨', 'Stay'], ['🎟️', 'Tickets'], ['🛒', 'Groceries']];

async function viewAddExpense(queryStr) {
  const params = new URLSearchParams(queryStr || '');
  const editId = params.get('edit') || '';
  const pre    = params.get('friend') || '';

  let friends, edit = null;
  try {
    if (editId) { edit = await api('GET', `/api/expenses/${editId}`); friends = edit.friends; }
    else        { friends = await api('GET', '/api/friends'); }
  } catch (e) { toast(e.message); go('#/'); return; }
  if (!friends) return;

  if (!friends.length) {
    render(`
    <div class="page">
      <div class="hk-header"><button class="btn-back" onclick="history.back()">‹</button><div class="hk-title">Add expense</div></div>
      <div class="page-body">
        <div class="empty"><div class="empty-icon">👥</div><div class="empty-title">No one to split with yet</div>
        <div class="empty-sub">Friends appear automatically once they sign in. Send them the invite.</div></div>
        <div style="padding:0 1rem"><button class="btn btn-primary" onclick="go('#/friends')">Invite the gang</button></div>
      </div>
      ${nav('add')}
    </div>`);
    return;
  }

  const me = { uid: S.user.uid, name: S.user.name };
  const selected = new Set(edit ? edit.participants.filter(u => u !== me.uid) : (pre ? [pre] : []));
  window.__addExpState = {
    me, friends, selected, editId, edit,
    mode: edit?.split_amounts ? 'exact' : 'equal',
    eq: {}, ex: edit?.split_amounts ? { ...edit.split_amounts } : {}, paidBy: edit ? edit.paid_by : me.uid,
  };
  if (edit) { (edit.split_among || []).forEach(u => {}); window.__addExpState.eq = Object.fromEntries((edit.split_among || []).map(u => [u, true])); }

  renderAddExpenseForm();
  if (edit) {
    document.getElementById('exp-desc').value   = edit.description || '';
    document.getElementById('exp-amount').value = (+edit.amount).toFixed(2);
    document.getElementById('exp-note').value   = edit.note || '';
    markChips();
  }
  renderMemberSelectors();
}

function people() {
  const X = window.__addExpState;
  return [X.me, ...X.friends.filter(f => X.selected.has(f.uid))];
}

function renderAddExpenseForm() {
  const X = window.__addExpState;
  const editing = !!X.editId;
  render(`
  <div class="page">
    <div class="hk-header">
      <button class="btn-back" onclick="history.back()">‹</button>
      <div class="hk-title">${editing ? 'Edit expense' : 'Add expense'}</div>
    </div>
    <div class="page-body">
      <div class="amount-hero">
        <span class="amount-sym">₹</span>
        <input id="exp-amount" type="number" inputmode="decimal" min="0.01" step="0.01" placeholder="0" oninput="updatePreview()" autofocus>
      </div>

      <div class="form-group">
        <input id="exp-desc" class="form-input" placeholder="What was it for?" maxlength="200" oninput="markChips()">
        <div class="quick-chips" id="quick-chips">
          ${QUICK.map(([em, label]) => `<button type="button" class="qchip" data-label="${esc(label)}" onclick="pickQuick(this)">${em} ${esc(label)}</button>`).join('')}
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Split with</label>
        <div class="quick-chips wrap">
          ${X.friends.map(f => `<button type="button" class="qchip friend-chip ${X.selected.has(f.uid) ? 'on' : ''}" data-uid="${f.uid}" onclick="toggleFriend('${f.uid}')">${esc(f.name.split(' ')[0])}</button>`).join('')}
        </div>
      </div>

      <div id="split-area"></div>

      <div class="form-group">
        <label class="form-label">Label <span class="muted" style="font-weight:500;text-transform:none;letter-spacing:0">(optional)</span></label>
        <input id="exp-note" class="form-input" maxlength="200" placeholder="e.g. #garaba #ravibirthday">
      </div>

      <div style="padding:0 1rem .5rem">
        <button id="submit-expense-btn" class="btn btn-primary" onclick="submitExpense()">${editing ? 'Save changes' : 'Add expense'}</button>
      </div>
    </div>
    ${nav('add')}
  </div>`);
}

// remember what's typed so re-rendering the split area doesn't lose it
function snapshotSplit() {
  const X = window.__addExpState;
  document.querySelectorAll('#split-list input[type=checkbox]').forEach(c => { X.eq[c.value] = c.checked; });
  document.querySelectorAll('.exact-in').forEach(el => { X.ex[el.dataset.uid] = el.value; });
  const paid = document.getElementById('exp-paidby');
  if (paid) X.paidBy = paid.value;
}

function renderMemberSelectors() {
  const X = window.__addExpState;
  const ppl = people();
  if (!ppl.some(p => p.uid === X.paidBy)) X.paidBy = X.me.uid;
  const area = document.getElementById('split-area');
  if (!area) return;

  if (!X.selected.size) {
    area.innerHTML = `<div class="hint" style="margin:0 1rem">Pick at least one friend to split with.</div>`;
    document.getElementById('preview-wrap')?.remove();
    return;
  }

  const rows = X.mode === 'equal'
    ? ppl.map(m => `
      <label class="check-item" style="padding:.55rem 1rem">
        <input type="checkbox" value="${m.uid}" ${X.eq[m.uid] === false ? '' : 'checked'} onchange="updatePreview()">
        ${av(m.name)}
        <span class="fw700 flex1">${esc(m.uid === X.me.uid ? 'You' : m.name)}</span>
        <span class="share-amt" data-uid="${m.uid}"></span>
      </label>`).join('')
    : ppl.map(m => `
      <div class="check-item" style="padding:.45rem 1rem">
        ${av(m.name)}
        <span class="fw700 flex1">${esc(m.uid === X.me.uid ? 'You' : m.name)}</span>
        <span class="exact-wrap">₹<input class="exact-in" data-uid="${m.uid}" type="number" inputmode="decimal" min="0" step="0.01"
          placeholder="0" value="${X.ex[m.uid] ?? ''}" oninput="updatePreview()"></span>
      </div>`).join('');

  area.innerHTML = `
    <div class="form-group">
      <label class="form-label">Paid by</label>
      <select id="exp-paidby" class="form-select">
        ${ppl.map(m => `<option value="${m.uid}" ${m.uid === X.paidBy ? 'selected' : ''}>${esc(m.uid === X.me.uid ? 'You' : m.name)}</option>`).join('')}
      </select>
    </div>
    <div class="form-group">
      <div class="seg" id="seg">
        <button type="button" class="seg-btn ${X.mode === 'equal' ? 'on' : ''}" data-mode="equal" onclick="setMode('equal')">Split equally</button>
        <button type="button" class="seg-btn ${X.mode === 'exact' ? 'on' : ''}" data-mode="exact" onclick="setMode('exact')">Exact amounts</button>
      </div>
      <div class="split-tools">${X.mode === 'equal'
        ? `<button type="button" class="link-btn" onclick="toggleAll()">Select all / none</button>`
        : `<span class="muted" style="font-size:.8rem">Type what each person owes. Leave blank if not part of it.</span>`}</div>
      <div id="split-list" class="hk-group" style="margin:0;padding:.1rem 0">${rows}</div>
    </div>
    <div id="preview-wrap"></div>`;
  updatePreview();
}

function toggleFriend(uid) {
  snapshotSplit();
  const X = window.__addExpState;
  if (X.selected.has(uid)) X.selected.delete(uid); else X.selected.add(uid);
  document.querySelectorAll('.friend-chip').forEach(c => c.classList.toggle('on', X.selected.has(c.dataset.uid)));
  renderMemberSelectors();
}

function setMode(mode) {
  const X = window.__addExpState;
  if (X.mode === mode) return;
  snapshotSplit();
  if (mode === 'exact') {
    const amount = parseFloat(document.getElementById('exp-amount')?.value) || 0;
    const ids = people().filter(p => X.eq[p.uid] !== false).map(p => p.uid);
    X.ex = {};
    if (amount > 0 && ids.length) {
      const each = Math.floor(amount / ids.length * 100) / 100;
      ids.forEach(u => { X.ex[u] = each.toFixed(2); });
      X.ex[ids[0]] = (Math.round((amount - each * (ids.length - 1)) * 100) / 100).toFixed(2);
    }
  } else {
    X.eq = Object.fromEntries(people().map(p => [p.uid, parseFloat(X.ex[p.uid]) > 0]));
    if (!Object.values(X.eq).some(Boolean)) X.eq = {};
  }
  X.mode = mode;
  renderMemberSelectors();
}

function toggleAll() {
  const boxes = [...document.querySelectorAll('#split-list input[type=checkbox]')];
  const all = boxes.every(b => b.checked);
  boxes.forEach(b => { b.checked = !all; });
  updatePreview();
}

function pickQuick(btn) {
  document.getElementById('exp-desc').value = btn.dataset.label;
  markChips();
  document.getElementById('exp-amount').focus();
}

function markChips() {
  const v = (document.getElementById('exp-desc')?.value || '').trim();
  document.querySelectorAll('#quick-chips .qchip').forEach(c => c.classList.toggle('on', c.dataset.label === v));
}

function updatePreview() {
  const X = window.__addExpState;
  const amount = parseFloat(document.getElementById('exp-amount')?.value) || 0;
  const wrap = document.getElementById('preview-wrap');
  if (!wrap) return;

  if (X.mode === 'equal') {
    const boxes = [...document.querySelectorAll('#split-list input[type=checkbox]')];
    const on = boxes.filter(c => c.checked);
    const each = on.length ? amount / on.length : 0;
    boxes.forEach(c => {
      const el = document.querySelector(`.share-amt[data-uid="${c.value}"]`);
      if (el) el.textContent = c.checked && amount > 0 ? fmt(each) : '';
    });
    wrap.innerHTML = amount > 0 && on.length
      ? `<div class="preview-card"><div>
           <div class="preview-amount">${fmt(each)} <span class="preview-unit">each</span></div>
           <div class="muted">${on.length} ${on.length === 1 ? 'person' : 'people'} · ${fmt(amount)} total</div>
         </div></div>` : '';
    return;
  }

  const sum  = [...document.querySelectorAll('.exact-in')].reduce((a, el) => a + (parseFloat(el.value) || 0), 0);
  const left = Math.round((amount - sum) * 100) / 100;
  let cls = 'ok', txt = 'Adds up ✓';
  if (amount <= 0)       { cls = ''; txt = 'Enter the total amount above'; }
  else if (left > 0.05)  { cls = 'warn'; txt = `${fmt(left)} still to assign`; }
  else if (left < -0.05) { cls = 'bad';  txt = `${fmt(left)} too much`; }
  wrap.innerHTML = `<div class="preview-card"><div>
      <div class="preview-amount">${fmt(sum)} <span class="preview-unit">of ${fmt(amount)}</span></div>
      <div class="split-status ${cls}">${txt}</div></div></div>`;
}

async function submitExpense() {
  const X = window.__addExpState;
  const desc   = document.getElementById('exp-desc')?.value.trim();
  const amount = Math.round((parseFloat(document.getElementById('exp-amount')?.value) || 0) * 100) / 100;
  const paidBy = document.getElementById('exp-paidby')?.value;
  const note   = document.getElementById('exp-note')?.value.trim();

  if (!amount || amount <= 0) { toast('Enter the amount'); return; }
  if (!desc)                  { toast('Add what it was for'); return; }
  if (!X.selected.size)       { toast('Pick at least one friend'); return; }

  let split, amounts = null;
  if (X.mode === 'equal') {
    split = [...document.querySelectorAll('#split-list input:checked')].map(el => el.value);
    if (!split.length) { toast('Pick at least one person'); return; }
  } else {
    amounts = {};
    document.querySelectorAll('.exact-in').forEach(el => {
      const v = Math.round((parseFloat(el.value) || 0) * 100) / 100;
      if (v > 0) amounts[el.dataset.uid] = v;
    });
    split = Object.keys(amounts);
    if (!split.length) { toast('Enter an amount for at least one person'); return; }
    const sum = Object.values(amounts).reduce((a, b) => a + b, 0);
    if (Math.abs(sum - amount) > 0.05) { toast(`Amounts add up to ${fmt(sum)}, not ${fmt(amount)}`); return; }
  }

  const btn = document.getElementById('submit-expense-btn');
  if (btn) btn.disabled = true;
  const body = { description: desc, amount, paid_by: paidBy, split_among: split, split_amounts: amounts, note };
  try {
    if (X.editId) await api('PUT', `/api/expenses/${X.editId}`, body);
    else          await api('POST', '/api/expenses', body);
    toast(X.editId ? 'Saved ✓' : 'Expense added ✓');
    const other = [...X.selected][0];
    go(X.selected.size === 1 ? `#/friends/${other}` : '#/');
  } catch (e) {
    toast(e.message);
    if (btn) btn.disabled = false;
  }
}

// ── Insights ──────────────────────────────────────────────────────────────
const CAT_COLORS = { Food: '#FF8C42', Drinks: '#F15BB5', Travel: '#3D7BFF', 'Fuel & tolls': '#00A8E8', Stay: '#9B5DE5', Fun: '#FFB400', Groceries: '#00B894', Other: '#9A97B5' };

async function viewInsights(range = 'month') {
  render(`<div class="page"><div class="page-body"><div class="empty"><div class="empty-icon">⏳</div></div></div></div>`);
  let d;
  try { d = await api('GET', `/api/insights?range=${range}`); }
  catch { toast('Could not load insights'); return; }
  if (!d) return;

  const tabs = [['month', 'This month'], ['3m', '3 months'], ['all', 'All time']]
    .map(([v, l]) => `<button class="seg-btn ${v === range ? 'on' : ''}" onclick="viewInsights('${v}')">${l}</button>`).join('');

  const tile = (label, val, cls = '') => `<div class="tile"><div class="tile-val ${cls}">${val}</div><div class="tile-label">${label}</div></div>`;

  const top = d.by_category[0];
  const topFriend = d.by_friend[0];
  const notes = [];
  if (top) notes.push(`<strong>${esc(top.name)}</strong> is your biggest spend — ${top.pct}% of what you've spent (${fmt(top.amount)}).`);
  if (d.expense_count) notes.push(`You've been part of <strong>${d.expense_count}</strong> expense${d.expense_count === 1 ? '' : 's'}, about <strong>${fmt(d.avg)}</strong> your share each.`);
  if (topFriend) notes.push(`You share the most spending with <strong>${esc(topFriend.name.split(' ')[0])}</strong> (${fmt(topFriend.shared)} across ${topFriend.count} bills).`);
  if (d.owe > 0.01) notes.push(`You still owe <strong>${fmt(d.owe)}</strong> in total.`);
  if (d.owed > 0.01) notes.push(`Friends still owe you <strong>${fmt(d.owed)}</strong>.`);

  const catBars = d.by_category.map(c => `
    <div class="bar-row">
      <div class="bar-head"><span>${esc(c.name)}</span><span>${fmt(c.amount)} · ${c.pct}%</span></div>
      <div class="bar"><div style="width:${Math.max(c.pct, 2)}%;background:${CAT_COLORS[c.name] || '#9A97B5'}"></div></div>
    </div>`).join('');

  const maxM = Math.max(1, ...d.by_month.map(m => m.amount));
  const months = d.by_month.map(m => {
    const lab = new Date(m.month + '-01').toLocaleDateString('en-IN', { month: 'short' });
    return `<div class="col"><div class="col-val">${m.amount >= 1000 ? Math.round(m.amount / 100) / 10 + 'k' : Math.round(m.amount)}</div>
      <div class="col-bar" style="height:${Math.max(4, m.amount / maxM * 100)}px"></div><div class="col-lab">${lab}</div></div>`;
  }).join('');

  const tagChips = d.by_tag.map(t => `<span class="tag tag-big">#${esc(t.tag)} <b>${fmt(t.amount)}</b></span>`).join('');

  const friendRows = d.by_friend.map(f => `
    <div class="hk-row tap" onclick="go('#/friends/${f.uid}')">
      ${av(f.name)}
      <div class="flex1" style="min-width:0"><div class="fw700 trunc">${esc(f.name)}</div>
        <div class="muted">${fmt(f.shared)} shared · ${f.count} bill${f.count === 1 ? '' : 's'}</div></div>
      ${pill(f.balance)}
    </div>`).join('');

  render(`
  <div class="page">
    <div class="hk-header"><div class="hk-title flex1" style="font-size:1.15rem">Insights</div>${REFRESH_BTN}</div>
    <div class="page-body">
      <div style="padding:.75rem 1rem 0"><div class="seg">${tabs}</div></div>
      ${!d.expense_count ? `<div class="empty"><div class="empty-icon">📊</div><div class="empty-title">Nothing to analyse yet</div><div class="empty-sub">Add some expenses and your spending patterns will show up here.</div></div>` : `
      <div class="tiles">
        ${tile('Your share of spending', fmt(d.my_spend))}
        ${tile('You paid upfront', fmt(d.paid))}
        ${tile('Friends owe you', fmt(d.owed), 'pos')}
        ${tile('You owe', fmt(d.owe), 'neg')}
        ${tile('You paid back', fmt(d.settled))}
        ${tile('You received', fmt(d.received))}
      </div>
      <div class="notes">${notes.map(n => `<p>${n}</p>`).join('')}</div>
      ${d.by_category.length ? `<div class="hk-section">Where it goes</div><div class="card">${catBars}</div>` : ''}
      ${d.by_month.length > 1 ? `<div class="hk-section">Month by month</div><div class="card"><div class="cols">${months}</div></div>` : ''}
      ${d.by_tag.length ? `<div class="hk-section">Your #labels</div><div class="tag-row" style="padding:0 1rem">${tagChips}</div>` : ''}
      ${d.by_friend.length ? `<div class="hk-section">By friend</div><div class="hk-group">${friendRows}</div>` : ''}
`}
      <div style="height:2rem"></div>
    </div>
    ${nav('insights')}
  </div>`);
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
            <div class="muted">+91 ${esc(u.mobile)}</div>
          </div>
        </div>
      </div>

      <div class="hk-section">Your name</div>
      <div class="hk-group" style="padding:.9rem 1rem">
        <input id="acc-name" class="form-input" maxlength="40" value="${esc(u.name)}" autocomplete="name">
        <div class="muted" style="font-size:.8rem;margin:.4rem 0 .7rem">This is how friends see you, everywhere in the app.</div>
        <button class="btn btn-primary" onclick="saveName()">Save name</button>
      </div>

      <div class="hk-section">Get paid faster</div>
      <div class="hk-group" style="padding:.9rem 1rem">
        <label class="form-label">Your UPI ID</label>
        <div class="pw-field"><input id="upi-id" class="form-input masked" placeholder="name@oksbi" value="${esc(u.upi || '')}" autocapitalize="off" autocorrect="off" spellcheck="false" autocomplete="off"><button type="button" class="pw-eye" onclick="togglePw('upi-id', this)" aria-label="Show">👁</button></div>
        <div class="muted" style="font-size:.8rem;margin:.4rem 0 .7rem">Friends who owe you will see a one-tap “Pay with UPI” button that opens GPay, PhonePe or Paytm with the amount filled in.</div>
        <button class="btn btn-primary" onclick="saveUpi()">Save UPI ID</button>
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

async function saveName() {
  const name = document.getElementById('acc-name').value;
  try {
    const r = await api('PUT', '/api/me/name', { name });
    S.user.name = r.name;
    toast('Name saved ✓');
    viewAccount();
  } catch (e) { toast(e.message); }
}

async function saveUpi() {
  const v = document.getElementById('upi-id').value.trim();
  try {
    const r = await api('PUT', '/api/me/upi', { upi: v });
    S.user.upi = r.upi;
    toast(r.upi ? 'UPI ID saved ✓' : 'UPI ID removed');
  } catch (e) { toast(e.message); }
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

// Pick up other people's entries without a manual reload: when you come back to the app, and on pull-down
const busy = () => document.querySelector('.modal-overlay');
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && REFRESHABLE.test(location.hash || '#/') && Date.now() - lastLoad > 20000 && !busy()) route();
});
let pull = null;
document.addEventListener('touchstart', e => {
  const body = e.target.closest?.('.page-body');
  pull = body && body.scrollTop === 0 && REFRESHABLE.test(location.hash || '#/') ? e.touches[0].clientY : null;
}, { passive: true });
document.addEventListener('touchend', e => {
  if (pull !== null && e.changedTouches[0].clientY - pull > 90 && !busy()) { toast('Refreshing…', 900); route(); }
  pull = null;
}, { passive: true });

document.addEventListener('DOMContentLoaded', init);
