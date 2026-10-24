import streamlit as st
from blog_backend import app
from datetime import datetime
import re

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="AI Blog Generator",
    page_icon="✍️",
    layout="wide"
)

# -----------------------------
# CUSTOM CSS
# -----------------------------
st.markdown("""
<style>

.main {
    background-color: #0E1117;
}

.title {
    font-size: 45px;
    font-weight: bold;
    color: white;
    text-align: center;
    margin-bottom: 10px;
}

.subtitle {
    text-align: center;
    color: #AAAAAA;
    margin-bottom: 30px;
}

.stButton>button {
    width: 100%;
    background-color: #FF4B4B;
    color: white;
    font-size: 18px;
    border-radius: 10px;
    height: 50px;
}

.blog-box {
    padding: 20px;
    border-radius: 10px;
    background-color: #1E1E1E;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# HEADER
# -----------------------------
st.markdown('<div class="title">📝 AI Blog Generator</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="subtitle">Generate technical blogs using LangGraph + Gemini AI</div>',
    unsafe_allow_html=True
)

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.header("⚙️ Blog Settings")

    topic = st.text_area(
        "Enter Blog Topic",
        placeholder="Example: Cloud Computing, Generative AI, Kubernetes..."
    )

    generate_btn = st.button("🚀 Generate Blog")

# -----------------------------
# HELPER FUNCTION
# -----------------------------
def clean_filename(text):
    text = re.sub(r'[^a-zA-Z0-9 ]', '', text)
    text = text.replace(" ", "_")
    return text.lower()

# -----------------------------
# MAIN GENERATION
# -----------------------------
if generate_btn:

    if topic.strip() == "":
        st.warning("Please enter a blog topic.")
        st.stop()

    with st.spinner("Generating Blog... Please wait ⏳"):

        try:

            # Graph Input
            inputs = {
                "topic": topic,
                "sections": []
            }

            # Invoke backend graph
            result = app.invoke(inputs)

            # Final blog markdown
            final_blog = result["final"]

            st.success("✅ Blog Generated Successfully!")

            st.markdown("## 📄 Generated Blog")

            # Display blog
            st.markdown(
                f'<div class="blog-box">{final_blog}</div>',
                unsafe_allow_html=True
            )

            # -----------------------------
            # DOWNLOAD BUTTON
            # -----------------------------
            filename = clean_filename(topic)

            st.download_button(
                label="⬇️ Download Blog",
                data=final_blog,
                file_name=f"{filename}.md",
                mime="text/markdown"
            )

        except Exception as e:
            st.error(f"Error: {str(e)}")

# -----------------------------
# DEFAULT SCREEN
# -----------------------------
else:

    st.info("👈 Enter topic from sidebar and click Generate Blog")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Blogs Generated", "100+")

    with col2:
        st.metric("AI Model", "Gemini 3.8")

    with col3:
        st.metric("Framework", "LangGraph")