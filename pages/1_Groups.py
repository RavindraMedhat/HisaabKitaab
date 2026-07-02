import streamlit as st
from utils.ui import apply_styles, require_login
from services.firebase import db

st.set_page_config(page_title="Groups — HisaabKitaab", page_icon="👥", layout="centered")
apply_styles()
require_login()

uid = st.session_state.user_id
st.title("👥 My Groups")

with st.expander("➕ Create New Group"):
    group_name = st.text_input("Group Name")
    if st.button("Create Group", use_container_width=True):
        if group_name.strip():
            db.collection("groups").add({
                "name": group_name.strip(),
                "created_by": uid,
                "members": [uid],
            })
            st.success(f'Group "{group_name}" created!')
            st.rerun()
        else:
            st.error("Enter a group name.")

st.markdown("---")
groups = db.collection("groups").where("members", "array_contains", uid).stream()
groups = [{"id": g.id, **g.to_dict()} for g in groups]

if not groups:
    st.info("No groups yet. Create one above!")
else:
    for group in groups:
        st.markdown(f"### {group['name']}")
        st.caption(f"Members: {len(group['members'])}")
        st.divider()
