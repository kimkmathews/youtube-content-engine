import os
import sys
import uuid
import streamlit as st
from dotenv import load_dotenv

# Ensure the root directory is in the path to import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

# Initialization logic
def init_session():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        # Initial greeting message
        st.session_state.messages = [
            {"role": "assistant", "content": "👋 Welcome to the YouTube Content Engine! I can autonomously extract, summarize, and rewrite YouTube videos into blogs, social media posts, and chapters. \n\nTo get started, provide a YouTube URL and your instructions."}
        ]
        
    if "runtime" not in st.session_state:
        try:
            st.session_state.runtime = DeepAgentsRuntime()
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
    if not os.getenv("GEMINI_API_KEY"):
        st.error("🔴 GEMINI_API_KEY not found in .env")
    else:
        st.success("🟢 API Key Loaded")
        
    st.markdown("### Workspaces")
    st.info("Files generated during this session are stored locally in the `/workspace` folder to optimize token usage.")

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
        with st.spinner("Agent is thinking..."):
            try:
                # Invoke the runtime with the user's prompt
                response = st.session_state.runtime.invoke(
                    st.session_state.session_id, 
                    prompt
                )
                st.markdown(response)
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                error_msg = f"**Error executing agent pipeline:**\n\n```python\n{str(e)}\n```"
                st.error("Pipeline Failure")
                st.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
