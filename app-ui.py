import streamlit as st
import requests
import tempfile

st.set_page_config(page_title="File Chat with LLaMA 3", layout="centered")

st.title("FIN-Bot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# If you want to upload structured JSON instead of text documents
uploaded_file = st.file_uploader("Upload file", type=["json"])

if uploaded_file and "file_content" not in st.session_state:
    import json
    data = json.load(uploaded_file)
    text_blocks = []
    for i, tab in enumerate(data):
        for key, rows in tab.items():
            lines = [f"Table {key}:"]
            header = rows[0]
            for row in rows[1:]:
                lines.append(" | ".join(f"{h}: {v}" for h, v in zip(header, row)))
            text_blocks.append("\n".join(lines))
    st.session_state.file_content = "\n\n".join(text_blocks)


# Show messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])

# Chat input
prompt = st.chat_input("Ask a question about the uploaded file...")

# Inference
if prompt and uploaded_file:
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Combine prompt + file content
    full_prompt = f"""You are an expert assistant. Read the following content and answer the user's question.

### Document:
{st.session_state.file_content[:4000]}  # Truncated if too large

### Question:
{prompt}

### Answer:
"""

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                res = requests.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "llama3:latest", "prompt": full_prompt, "stream": False}
                )
                reply = res.json()["response"]
            except Exception as e:
                reply = "❌ Could not contact Ollama backend."

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "text": reply})

elif prompt and not uploaded_file:
    st.warning("📁 Please upload a file first.")
