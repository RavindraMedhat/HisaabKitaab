import streamlit as st
from utils.ui import apply_styles, bottom_nav, fmt_amount
from utils.session import restore_login
from services.groups import get_user_groups, get_user_names, add_expense

st.set_page_config(page_title="Add Expense · HisaabKitaab", page_icon="📒", layout="centered")
apply_styles()
restore_login()

if not st.session_state.get("user"):
    st.switch_page("Home.py")

user = st.session_state["user"]
uid  = user["uid"]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hk-header">
  <div class="hk-header-title" style="font-size:1.1rem">Add Expense</div>
</div>""", unsafe_allow_html=True)

groups = get_user_groups(uid)
if not groups:
    st.markdown("""
    <div style="text-align:center;padding:2rem 1rem;color:#8E8E93">
      <div style="font-size:2rem;margin-bottom:.75rem">👥</div>
      <div style="font-weight:700;color:#1C1C1E;margin-bottom:.3rem">No groups yet</div>
      <div style="font-size:.9rem">Create a group first, then add expenses.</div>
    </div>""", unsafe_allow_html=True)
    if st.button("Go to Groups"):
        st.switch_page("pages/2_Groups.py")
    st.stop()

group_map   = {g["name"]: g for g in groups}
group_names = list(group_map.keys())

# Pre-fill group if coming from group detail
prefill_id = st.session_state.pop("prefill_group_id", None)
if prefill_id:
    matched = next((g["name"] for g in groups if g["id"] == prefill_id), None)
    if matched:
        st.session_state.selected_group_name = matched

selected_name = st.session_state.get("selected_group_name", group_names[0])
if selected_name not in group_names:
    selected_name = group_names[0]

# ── Form ──────────────────────────────────────────────────────────────────────
st.markdown('<div style="padding:.5rem 1rem 0">', unsafe_allow_html=True)

chosen_group_name = st.selectbox("Group", group_names,
                                  index=group_names.index(selected_name),
                                  key="sel_group")
st.session_state.selected_group_name = chosen_group_name
chosen_group = group_map[chosen_group_name]
gid = chosen_group["id"]
members = chosen_group.get("members", [])

# Resolve member names
names = get_user_names(members)
name_to_uid = {v: k for k, v in names.items()}
member_names = [names[m] for m in members]

description = st.text_input("Description", placeholder="Dinner, petrol, hotel…", key="exp_desc")
amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.2f", key="exp_amount")

paid_by_name = st.selectbox("Paid by", member_names,
                              index=member_names.index(names[uid]) if uid in names else 0,
                              key="exp_paid_by")

split_among_names = st.multiselect("Split among", member_names,
                                    default=member_names,
                                    key="exp_split")

st.markdown("</div>", unsafe_allow_html=True)

# ── Live preview ──────────────────────────────────────────────────────────────
if amount > 0 and split_among_names:
    share = amount / len(split_among_names)
    st.markdown(f"""
    <div class="hk-group" style="margin:.75rem 1rem">
      <div class="hk-row" style="flex-direction:column;align-items:flex-start;gap:.4rem">
        <div style="font-size:.7rem;font-weight:800;color:#8E8E93;
                    letter-spacing:.08em;text-transform:uppercase">Per person</div>
        <div style="font-size:1.6rem;font-weight:900;color:#FF6B2B;
                    font-variant-numeric:tabular-nums">{fmt_amount(share)}</div>
        <div style="font-size:.85rem;color:#8E8E93">{len(split_among_names)} people splitting {fmt_amount(amount)}</div>
      </div>
    </div>""", unsafe_allow_html=True)

# ── Submit ────────────────────────────────────────────────────────────────────
st.markdown('<div style="padding:0 1rem">', unsafe_allow_html=True)
if st.button("Add Expense", key="submit_expense"):
    errors = []
    if not description.strip():
        errors.append("Enter a description.")
    if amount <= 0:
        errors.append("Enter an amount greater than 0.")
    if not split_among_names:
        errors.append("Select at least one person to split among.")

    if errors:
        for e in errors:
            st.warning(e)
    else:
        paid_by_uid    = name_to_uid.get(paid_by_name, uid)
        split_uids     = [name_to_uid[n] for n in split_among_names if n in name_to_uid]

        add_expense(gid, {
            "description":  description.strip(),
            "amount":       amount,
            "paid_by":      paid_by_uid,
            "split_among":  split_uids,
            "created_by":   uid,
            "group_id":     gid,
            "group_name":   chosen_group_name,
        })
        st.success("Expense added!")
        # Clear form
        for key in ["exp_desc", "exp_amount", "exp_split", "exp_paid_by"]:
            st.session_state.pop(key, None)
        # Go back to group detail
        st.session_state.grp_view = "detail"
        st.session_state.grp_id   = gid
        st.switch_page("pages/2_Groups.py")

st.markdown("</div>", unsafe_allow_html=True)
bottom_nav("add")
