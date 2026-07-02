import streamlit as st
from utils.ui import apply_styles, require_login
from services.firebase import db

st.set_page_config(page_title="Expenses — HisaabKitaab", page_icon="💸", layout="centered")
apply_styles()
require_login()

uid = st.session_state.user_id
st.title("💸 Add Expense")

groups = db.collection("groups").where("members", "array_contains", uid).stream()
groups = [{"id": g.id, **g.to_dict()} for g in groups]

if not groups:
    st.info("Create a group first.")
    st.page_link("pages/1_Groups.py", label="Go to Groups")
    st.stop()

group_map = {g["name"]: g for g in groups}
selected_group = group_map[st.selectbox("Group", list(group_map.keys()))]

st.markdown("---")
description = st.text_input("What was it for?", placeholder="e.g. Dinner, Petrol, Rent")
amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.2f")
paid_by = st.selectbox("Paid by", selected_group["members"])
split_among = st.multiselect("Split among", selected_group["members"], default=selected_group["members"])

if st.button("Add Expense", use_container_width=True):
    if description.strip() and amount > 0 and split_among:
        db.collection("groups").document(selected_group["id"]).collection("expenses").add({
            "description": description.strip(),
            "amount": amount,
            "paid_by": paid_by,
            "split_among": split_among,
            "created_by": uid,
        })
        st.success(f"Added ₹{amount:.2f} for '{description}'!")
    else:
        st.error("Fill all fields and select at least one person to split with.")
