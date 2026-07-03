import streamlit as st
from datetime import datetime, timezone
from utils.ui import apply_styles, bottom_nav, fmt_amount, balance_text, avatar
from utils.session import restore_login
from services.groups import get_user_groups, get_expenses, get_settlements
from services.calculator import calc_my_balance

_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)

st.set_page_config(page_title="HisaabKitaab", page_icon="📒", layout="centered")
apply_styles()
restore_login()

if not st.session_state.get("user"):
    st.switch_page("Home.py")

user = st.session_state["user"]
uid = user["uid"]
name_first = user["name"].split()[0]

# ── Fetch data ────────────────────────────────────────────────────────────────
groups = get_user_groups(uid)

net_balance = 0.0
all_activity = []  # list of (timestamp, display_dict)

for g in groups:
    gid = g["id"]
    expenses = get_expenses(gid)
    settlements = get_settlements(gid)
    net_balance += calc_my_balance(expenses, settlements, uid)

    for e in expenses:
        all_activity.append({
            "ts":        e.get("created_at"),
            "type":      "expense",
            "group":     g.get("name", ""),
            "desc":      e.get("description", ""),
            "amount":    e.get("amount", 0),
            "paid_by":   e.get("paid_by", ""),
            "paid_self": e.get("paid_by") == uid,
            "split":     e.get("split_among", []),
            "group_id":  gid,
        })
    for s in settlements:
        all_activity.append({
            "ts":       s.get("created_at"),
            "type":     "settle",
            "group":    g.get("name", ""),
            "amount":   s.get("amount", 0),
            "from_uid": s.get("from_uid"),
            "to_uid":   s.get("to_uid"),
            "group_id": gid,
        })

def _ts(x):
    t = x.get("ts")
    if t is None:
        return _MIN_DT
    if hasattr(t, "tzinfo") and t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t

all_activity.sort(key=_ts, reverse=True)
recent = all_activity[:15]
net_balance = round(net_balance, 2)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hk-header">
  <div style="flex:1">
    <div style="font-size:.75rem;color:#8E8E93;font-weight:600">Welcome back</div>
    <div style="font-size:1.05rem;font-weight:900;color:#1C1C1E">{name_first} 👋</div>
  </div>
  <div style="font-size:1.4rem">📒</div>
</div>
""", unsafe_allow_html=True)

# ── Net balance banner ────────────────────────────────────────────────────────
if net_balance > 0.01:
    banner_cls = "hk-banner-pos"
    label = "You are owed overall"
    emoji = "✅"
elif net_balance < -0.01:
    banner_cls = "hk-banner-neg"
    label = "You owe overall"
    emoji = "⚡"
else:
    banner_cls = "hk-banner-nil"
    label = "All settled up"
    emoji = "🎉"

st.markdown(f"""
<div class="hk-banner {banner_cls}">
  <div>
    <div style="font-size:.75rem;font-weight:700;color:#8E8E93;letter-spacing:.04em;
                text-transform:uppercase;margin-bottom:.2rem">{label}</div>
    <div style="font-size:1.9rem;font-weight:900;color:#1C1C1E;
                font-variant-numeric:tabular-nums;letter-spacing:-.02em">
      {"₹0" if abs(net_balance) < 0.01 else fmt_amount(net_balance)}
    </div>
  </div>
  <div style="font-size:2.2rem">{emoji}</div>
</div>
""", unsafe_allow_html=True)

# ── Groups quick row ──────────────────────────────────────────────────────────
if groups:
    st.markdown('<div class="hk-section">Your Groups</div>', unsafe_allow_html=True)
    rows_html = '<div class="hk-group">'
    for g in groups[:5]:
        count = len(g.get("members", []))
        rows_html += f"""
        <a href="/Groups" style="text-decoration:none">
          <div class="hk-row" style="cursor:pointer">
            {avatar(g["name"])}
            <div style="flex:1">
              <div style="font-weight:700;color:#1C1C1E">{g["name"]}</div>
              <div class="hk-muted">{count} member{"s" if count != 1 else ""}</div>
            </div>
            <div style="color:#C7C7CC;font-size:1.1rem">›</div>
          </div>
        </a>"""
    rows_html += "</div>"
    st.markdown(rows_html, unsafe_allow_html=True)

# ── Recent activity ───────────────────────────────────────────────────────────
if recent:
    st.markdown('<div class="hk-section">Recent Activity</div>', unsafe_allow_html=True)
    rows_html = '<div class="hk-group">'
    for item in recent:
        if item["type"] == "expense":
            split = item["split"]
            share = item["amount"] / len(split) if split else 0
            paid_self = item["paid_self"]
            if paid_self:
                amt_label = f'<span class="hk-pos hk-amt">+{fmt_amount(item["amount"] - (share if uid in split else 0))}</span>'
            elif uid in split:
                amt_label = f'<span class="hk-neg hk-amt">−{fmt_amount(share)}</span>'
            else:
                amt_label = ""
            rows_html += f"""
            <div class="hk-row">
              <div style="width:2.2rem;height:2.2rem;border-radius:50%;background:#F2F2F7;
                          display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">
                🧾
              </div>
              <div style="flex:1;min-width:0">
                <div style="font-weight:700;color:#1C1C1E;white-space:nowrap;overflow:hidden;
                            text-overflow:ellipsis">{item["desc"] or "Expense"}</div>
                <div class="hk-muted">{item["group"]}</div>
              </div>
              <div style="text-align:right;flex-shrink:0">{amt_label}</div>
            </div>"""
        else:
            if item.get("from_uid") == uid:
                settle_txt = f'<span class="hk-pos hk-amt">You paid {fmt_amount(item["amount"])}</span>'
            elif item.get("to_uid") == uid:
                settle_txt = f'<span class="hk-neg hk-amt">Received {fmt_amount(item["amount"])}</span>'
            else:
                settle_txt = f'<span class="hk-muted">{fmt_amount(item["amount"])} settled</span>'
            rows_html += f"""
            <div class="hk-row">
              <div style="width:2.2rem;height:2.2rem;border-radius:50%;background:#E3F9E8;
                          display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0">
                ✅
              </div>
              <div style="flex:1;min-width:0">
                <div style="font-weight:700;color:#1C1C1E">Settlement</div>
                <div class="hk-muted">{item["group"]}</div>
              </div>
              <div style="text-align:right;flex-shrink:0">{settle_txt}</div>
            </div>"""
    rows_html += "</div>"
    st.markdown(rows_html, unsafe_allow_html=True)
elif not groups:
    st.markdown("""
    <div style="text-align:center;padding:2rem 1rem;color:#8E8E93">
      <div style="font-size:2.5rem;margin-bottom:.75rem">👥</div>
      <div style="font-weight:700;color:#1C1C1E;margin-bottom:.3rem">No groups yet</div>
      <div style="font-size:.9rem">Go to Groups to create one</div>
    </div>""", unsafe_allow_html=True)

bottom_nav("home")
