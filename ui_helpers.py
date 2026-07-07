import streamlit as st


def format_delta(value, unit):
    if value is None:
        return None

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} {unit} in 30d"


def render_explainable_item(item):
    st.markdown(f"### {item['icon']} {item['title']}")
    st.write(item["text"])

    if "action" in item:
        st.info(f"Action: {item['action']}")

    with st.expander("💡 Why?"):
        st.write(item["explanation"])

    with st.expander("📚 Evidence"):
        for evidence in item.get("evidence", []):
            st.write(f"- {evidence}")