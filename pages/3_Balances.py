import streamlit as st
from utils.ui import apply_styles, require_login
from services.firebase import db
from services.calculator import simplify_debts

st.set_page_config(page_title="Balances — HisaabKitaab", page_icon="📊", layout="centered")
apply_styles()
require_login()

uid = st.session_state.user_id
st.title("📊 Balances")

groups = db.collection("groups").where("members", "array_contains", uid).stream()
groups = [{"id": g.id, **g.to_dict()} for g in groups]

if not groups:
    st.info("No groups found.")
    st.stop()

group_map = {g["name"]: g for g in groups}
selected_group = group_map[st.selectbox("Group", list(group_map.keys()))]

expenses_ref = db.collection("groups").document(selected_group["id"]).collection("expenses").stream()
expenses = [e.to_dict() for e in expenses_ref]

if not expenses:
    st.info("No expenses in this group yet.")
    st.stop()

st.markdown("---")
st.subheader("Expenses")
total = sum(e["amount"] for e in expenses)
for e in expenses:
    st.markdown(f"**{e['description']}** — ₹{e['amount']:.2f}")
    st.caption(f"Paid by {e['paid_by']} · Split among {len(e['split_among'])} people")

st.markdown(f"**Total: ₹{total:.2f}**")

st.markdown("---")
st.subheader("Settle Up")
transactions = simplify_debts(expenses)

if not transactions:
    st.success("✅ All settled up!")
else:
    for t in transactions:
        st.markdown(
            f"<div style='background:#f0f4ff;padding:0.8rem;border-radius:0.5rem;margin-bottom:0.5rem'>"
            f"<b>{t['from']}</b> owes <b>{t['to']}</b><br>"
            f"<span style='font-size:1.3rem;color:#1a73e8'>₹{t['amount']:.2f}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
