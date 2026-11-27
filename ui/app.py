import glob
import os
import sys
import uuid
import streamlit as st
from dotenv import load_dotenv

# Ensure the root directory is in the path to import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import Config
from src.core.runtime import DeepAgentsRuntime

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="YouTube Content Engine",
    page_icon="▶️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# One runtime (compiled graph + sqlite connections) per server process, shared by all tabs.
@st.cache_resource
def get_runtime() -> DeepAgentsRuntime:
    return DeepAgentsRuntime()


# Initialization logic
def init_session():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        # Initial greeting message
        st.session_state.messages = [
            {"role": "assistant", "content": "👋 Welcome to the YouTube Content Engine! I can autonomously extract, summarize, and rewrite YouTube videos into blogs, social media posts, and chapters. \n\nTo get started, provide a YouTube URL and your instructions."}
        ]
        
    try:
        st.session_state.runtime = get_runtime()
    except Exception as e:
        st.error(f"Failed to initialize AI Engine: {e}")
        st.stop()

init_session()

# Sidebar
with st.sidebar:
    st.markdown("### ▶️ Control Panel")
    st.markdown("---")
    
    st.markdown(f"**Session ID:**\n`{st.session_state.session_id}`")
    
    if st.button("🔄 Reset Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = [
            {"role": "assistant", "content": "Session reset. How can I help you?"}
        ]
        st.rerun()

    st.markdown("---")
    st.markdown("### System Status")
    if not Config.OPENROUTER_API_KEY:
        st.error("🔴 OPENROUTER_API_KEY not found in .env")
    else:
        st.success(f"🟢 OpenRouter key loaded · `{Config.ORCHESTRATOR_MODEL}`")

    st.markdown("### Generated files")
    session_dir = os.path.join(Config.WORKSPACE_ROOT, st.session_state.session_id)
    files = sorted(glob.glob(os.path.join(session_dir, "*", "*.md")))
    if not files:
        st.caption("Nothing generated in this session yet.")
    for path in files:
        with open(path, encoding="utf-8") as f:
            st.download_button(
                os.path.basename(path), f.read(), file_name=os.path.basename(path),
                mime="text/markdown", use_container_width=True, key=path,
            )

# Main Chat Interface
st.markdown('<div class="title-text">YouTube <span class="accent">Content Engine</span></div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Autonomous multi-agent orchestration for video content generation.</div>', unsafe_allow_html=True)

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Enter your request here... (e.g. 'Analyze this URL and create a blog post')"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        status = st.status("Agent is thinking...", expanded=False)
        try:
            response = ""
            for kind, text in st.session_state.runtime.stream(st.session_state.session_id, prompt):
                if kind == "progress":
                    status.update(label=text)
                    status.write(text)
                elif kind == "tool":
                    status.write(f"Calling `{text}`")
                else:
                    response = text
            status.update(label="Done", state="complete")
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            status.update(label="Failed", state="error")
            error_msg = f"**Error executing agent pipeline:**\n\n```python\n{str(e)}\n```"
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
    st.rerun()  # re-render history and refresh the sidebar's file list
