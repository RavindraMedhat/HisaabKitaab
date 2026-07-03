import streamlit as st
from utils.ui import apply_styles, bottom_nav, fmt_amount, balance_pill, avatar
from utils.session import restore_login
from services.groups import (
    get_user_groups, get_group, create_group, add_member_by_uid,
    get_expenses, get_settlements, add_settlement, get_user_by_email,
    get_user_names,
)
from services.calculator import calc_my_balance, simplify_debts

st.set_page_config(page_title="Groups · HisaabKitaab", page_icon="📒", layout="centered")
apply_styles()
restore_login()

if not st.session_state.get("user"):
    st.switch_page("Home.py")

user = st.session_state["user"]
uid  = user["uid"]

# Extra CSS for this page
st.markdown("""
<style>
/* Make group-open buttons look like rows */
div[data-testid="stButton"].grp-row > button {
  background: var(--surface) !important;
  color: var(--ink) !important;
  border: none !important;
  border-bottom: 1px solid var(--sep) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  text-align: left !important;
  padding: .85rem 1rem !important;
  font-weight: 600 !important;
  justify-content: flex-start !important;
}
div[data-testid="stButton"].grp-row > button:hover { background: var(--bg) !important; }
</style>""", unsafe_allow_html=True)


def go(view_name, **kwargs):
    st.session_state.grp_view = view_name
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()


view = st.session_state.get("grp_view", "list")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Groups List
# ══════════════════════════════════════════════════════════════════════════════
if view == "list":
    st.markdown("""
    <div class="hk-header">
      <div class="hk-header-title" style="font-size:1.15rem;font-weight:900">Groups</div>
    </div>""", unsafe_allow_html=True)

    groups = get_user_groups(uid)

    if not groups:
        st.markdown("""
        <div style="text-align:center;padding:2.5rem 1rem;color:#8E8E93">
          <div style="font-size:2.8rem;margin-bottom:.75rem">👥</div>
          <div style="font-weight:800;font-size:1rem;color:#1C1C1E;margin-bottom:.3rem">No groups yet</div>
          <div style="font-size:.88rem">Create a group below and invite friends.</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="hk-section">Your Groups</div>', unsafe_allow_html=True)

        # Build group cards
        for g in groups:
            expenses    = get_expenses(g["id"])
            settlements = get_settlements(g["id"])
            bal         = calc_my_balance(expenses, settlements, uid)
            count       = len(g.get("members", []))

            col_card, col_arrow = st.columns([6, 1])
            with col_card:
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:.75rem;
                            padding:.75rem 0 .2rem">
                  {avatar(g["name"])}
                  <div style="flex:1">
                    <div style="font-weight:700;color:#1C1C1E">{g["name"]}</div>
                    <div style="font-size:.82rem;color:#8E8E93">{count} member{"s" if count != 1 else ""}</div>
                  </div>
                  {balance_pill(bal)}
                </div>""", unsafe_allow_html=True)
            with col_arrow:
                st.markdown("<div style='padding:.9rem 0'>", unsafe_allow_html=True)
                if st.button("›", key=f"open_{g['id']}", help=f"Open {g['name']}"):
                    go("detail", grp_id=g["id"])
                st.markdown("</div>", unsafe_allow_html=True)
            st.divider()

    # Create group
    st.markdown('<div class="hk-section">New Group</div>', unsafe_allow_html=True)
    with st.expander("+ Create a Group", expanded=not groups):
        new_name = st.text_input("Group name", placeholder="e.g. Goa Trip, Flatmates",
                                  key="new_group_name")
        if st.button("Create Group", key="create_grp"):
            if new_name.strip():
                gid = create_group(new_name.strip(), uid)
                st.success(f"Group '{new_name}' created!")
                go("detail", grp_id=gid)
            else:
                st.warning("Enter a group name.")

    bottom_nav("groups")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Group Detail
# ══════════════════════════════════════════════════════════════════════════════
elif view == "detail":
    gid = st.session_state.get("grp_id")
    if not gid:
        go("list")

    group = get_group(gid)
    if not group:
        st.error("Group not found.")
        if st.button("← Back to Groups"):
            go("list")
        st.stop()

    expenses    = get_expenses(gid)
    settlements = get_settlements(gid)
    members     = group.get("members", [])
    names       = get_user_names(members)
    my_bal      = calc_my_balance(expenses, settlements, uid)
    txns        = simplify_debts(expenses, settlements)

    # Header with back
    st.markdown(f"""
    <div class="hk-header">
      <div class="hk-header-title">{group["name"]}</div>
    </div>""", unsafe_allow_html=True)

    if st.button("← Groups", key="back_detail"):
        go("list")

    # My balance banner
    if my_bal > 0.01:
        banner_cls, label = "hk-banner-pos", "You are owed"
    elif my_bal < -0.01:
        banner_cls, label = "hk-banner-neg", "You owe"
    else:
        banner_cls, label = "hk-banner-nil", "All settled up"

    st.markdown(f"""
    <div class="hk-banner {banner_cls}">
      <div>
        <div style="font-size:.72rem;font-weight:700;color:#8E8E93;
                    text-transform:uppercase;letter-spacing:.04em;margin-bottom:.25rem">{label}</div>
        <div style="font-size:1.9rem;font-weight:900;color:#1C1C1E;
                    font-variant-numeric:tabular-nums">
          {"All settled" if abs(my_bal) < 0.01 else fmt_amount(my_bal)}
        </div>
      </div>
      <div style="font-size:2rem">
        {"✅" if abs(my_bal) < 0.01 else ("⬆️" if my_bal > 0 else "⬇️")}
      </div>
    </div>""", unsafe_allow_html=True)

    # Settle up
    my_txns = [t for t in txns if t["from"] == uid or t["to"] == uid]
    if my_txns:
        st.markdown('<div class="hk-section">Settle Up</div>', unsafe_allow_html=True)
        for t in my_txns:
            from_name = names.get(t["from"], t["from"][:6])
            to_name   = names.get(t["to"],   t["to"][:6])
            amt_str   = fmt_amount(t["amount"])

            if t["from"] == uid:
                desc = f"You owe **{to_name}**  ·  −{amt_str}"
            else:
                desc = f"**{from_name}** owes you  ·  +{amt_str}"

            col_desc, col_btn = st.columns([3, 1])
            with col_desc:
                st.markdown(f"<div style='padding:.6rem 0;font-size:.95rem'>{desc}</div>",
                            unsafe_allow_html=True)
            with col_btn:
                if st.button("Settle", key=f"settle_{t['from']}_{t['to']}"):
                    go("settle", grp_settle_tx=t, grp_settle_names=names)
    elif abs(my_bal) < 0.01 and not txns:
        st.markdown("""
        <div style="text-align:center;padding:.75rem 1rem;font-size:.92rem;
                    color:#34C759;font-weight:700">
          🎉 Everyone is settled up!
        </div>""", unsafe_allow_html=True)

    # Members
    st.markdown('<div class="hk-section">Members</div>', unsafe_allow_html=True)
    members_html = '<div class="hk-group">'
    for m in members:
        n   = names.get(m, m[:8])
        you = "  <small style='color:#8E8E93'>(you)</small>" if m == uid else ""
        members_html += f"""
        <div class="hk-row">
          {avatar(n)}
          <div style="font-weight:600;color:#1C1C1E">{n}{you}</div>
        </div>"""
    members_html += "</div>"
    st.markdown(members_html, unsafe_allow_html=True)

    with st.expander("+ Add Member"):
        email_in = st.text_input("Email address", key="add_mem_email",
                                  placeholder="friend@example.com")
        if st.button("Add Member", key="add_mem_btn"):
            found = get_user_by_email(email_in)
            if not found:
                st.warning("No HisaabKitaab account found for that email. They need to sign in first.")
            elif found["uid"] in members:
                st.info("Already a member of this group.")
            else:
                add_member_by_uid(gid, found["uid"])
                st.success(f"{found['name']} added to the group!")
                st.rerun()

    # Expenses
    st.markdown('<div class="hk-section">Expenses</div>', unsafe_allow_html=True)
    if expenses:
        rows_html = '<div class="hk-group">'
        for e in expenses:
            paid_name = names.get(e.get("paid_by", ""), "?")
            split     = e.get("split_among", [])
            share     = e["amount"] / len(split) if split else 0
            if e.get("paid_by") == uid:
                my_part = f'<span class="hk-pos hk-amt">+{fmt_amount(e["amount"] - (share if uid in split else 0))}</span>'
            elif uid in split:
                my_part = f'<span class="hk-neg hk-amt">−{fmt_amount(share)}</span>'
            else:
                my_part = f'<span class="hk-muted">{fmt_amount(e["amount"])}</span>'
            rows_html += f"""
            <div class="hk-row">
              <div style="flex:1;min-width:0">
                <div style="font-weight:700;color:#1C1C1E;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                  {e.get("description") or "Expense"}
                </div>
                <div class="hk-muted">{paid_name} paid {fmt_amount(e["amount"])}</div>
              </div>
              <div style="text-align:right;flex-shrink:0;padding-left:.5rem">{my_part}</div>
            </div>"""
        rows_html += "</div>"
        st.markdown(rows_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:1.5rem 1rem;color:#8E8E93;font-size:.9rem">
          No expenses yet.
        </div>""", unsafe_allow_html=True)

    # Add expense CTA
    st.markdown('<div style="padding:.5rem 1rem 0">', unsafe_allow_html=True)
    if st.button("+ Add Expense", key="add_exp_cta"):
        st.session_state.prefill_group_id = gid
        st.switch_page("pages/3_Add_Expense.py")
    st.markdown("</div>", unsafe_allow_html=True)

    bottom_nav("groups")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Settle Confirmation
# ══════════════════════════════════════════════════════════════════════════════
elif view == "settle":
    tx    = st.session_state.get("grp_settle_tx", {})
    names = st.session_state.get("grp_settle_names", {})
    gid   = st.session_state.get("grp_id")

    from_name = names.get(tx.get("from", ""), "Someone")
    to_name   = names.get(tx.get("to", ""),   "Someone")
    amount    = tx.get("amount", 0)
    paying    = tx.get("from") == uid

    st.markdown("""
    <div class="hk-header">
      <div class="hk-header-title">Settle Up</div>
    </div>""", unsafe_allow_html=True)

    if st.button("← Back", key="back_settle"):
        go("detail")

    # Summary
    payer_name   = from_name if paying else from_name
    receive_name = to_name
    if paying:
        title   = f"You owe {to_name}"
        color   = "#FF6B2B"
        emoji   = "⬇️"
    else:
        title   = f"{from_name} owes you"
        color   = "#34C759"
        emoji   = "⬆️"

    st.markdown(f"""
    <div class="hk-group" style="margin:.75rem 1rem">
      <div class="hk-row" style="flex-direction:column;align-items:center;
                                  gap:.5rem;padding:1.5rem 1rem">
        <div style="font-size:2.5rem">{emoji}</div>
        <div style="font-size:1rem;color:#8E8E93;font-weight:600">{title}</div>
        <div style="font-size:2.4rem;font-weight:900;color:{color};
                    font-variant-numeric:tabular-nums">{fmt_amount(amount)}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    note = st.text_input("Note (optional)", placeholder="Paid via UPI, Cash, etc.",
                          key="settle_note")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="btn-green">', unsafe_allow_html=True)
        if st.button("Mark as Paid ✓", key="confirm_settle"):
            add_settlement(
                gid,
                from_uid=tx["from"],
                to_uid=tx["to"],
                amount=amount,
                note=note,
            )
            st.success("Payment recorded!")
            st.session_state.pop("grp_settle_tx", None)
            st.session_state.pop("grp_settle_names", None)
            go("detail")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
        if st.button("Cancel", key="cancel_settle"):
            go("detail")
        st.markdown("</div>", unsafe_allow_html=True)

    bottom_nav("groups")
