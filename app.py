import streamlit as st
import google.generativeai as genai
import requests, os, re, datetime, tempfile, fitz, docx, copy
from ppt_generator import create_ppt
from doc_generator import create_doc

# ---------------- CONFIG ----------------
# ⚠️ Hardcoded API keys (do not push to public repos with real keys!)
GEMINI_API_KEY = "AIzaSyBtah4ZmuiVkSrJABE8wIjiEgunGXAbT3Q"
STABILITY_API_KEY = "sk-Z0tLgOIfS3pQlu4SbJEw5PdYAMl8ll02Dgx7yrifCAsPD20k"

genai.configure(api_key=GEMINI_API_KEY)
TEXT_MODEL = genai.GenerativeModel("gemini-1.5-flash")

STABILITY_API_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"

# ---------------- HELPERS ----------------
def call_gemini(prompt: str) -> str:
    response = TEXT_MODEL.generate_content(prompt)
    return response.text.strip()

def generate_image_stability(prompt: str) -> bytes:
    headers = {"Authorization": f"Bearer {STABILITY_API_KEY}", "Accept": "image/*"}
    data = {"prompt": prompt, "output_format": "png"}
    resp = requests.post(STABILITY_API_URL, headers=headers, files={"none": ''}, data=data)
    if resp.status_code != 200:
        raise Exception(f"Stability error: {resp.text}")
    return resp.content

def parse_points(points_text: str):
    points = []
    current_title, current_content = None, []
    lines = [re.sub(r"[#*>`]", "", ln).rstrip() for ln in points_text.splitlines()]
    for line in lines:
        if not line or "Would you like" in line:
            continue
        m = re.match(r"^\s*(Slide|Section)\s*(\d+)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            if current_title:
                points.append({"title": current_title, "description": "\n".join(current_content)})
            current_title, current_content = m.group(3).strip(), []
            continue
        if line.strip().startswith("-"):
            text = line.lstrip("-").strip()
            if text:
                current_content.append(f"• {text}")
        elif line.strip().startswith(("•", "*")) or line.startswith("  "):
            text = line.lstrip("•*").strip()
            if text:
                current_content.append(f"- {text}")
        else:
            if line.strip():
                current_content.append(line.strip())
    if current_title:
        points.append({"title": current_title, "description": "\n".join(current_content)})
    return points

def extract_text(path: str, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        text_parts = []
        doc = fitz.open(path)
        try:
            for page in doc:
                text_parts.append(page.get_text("text"))
        finally:
            doc.close()
        return "\n".join(text_parts)
    if name.endswith(".docx"):
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    if name.endswith(".txt"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

def split_text(text: str, chunk_size: int = 8000, overlap: int = 300):
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def summarize_long_text(full_text: str) -> str:
    chunks = split_text(full_text)
    if len(chunks) <= 1:
        return call_gemini(f"Summarize the following text in detail:\n\n{full_text}")
    partial_summaries = []
    for idx, ch in enumerate(chunks, start=1):
        mapped = call_gemini(f"Summarize this part of a longer document:\n\n{ch}")
        partial_summaries.append(f"Chunk {idx}:\n{mapped.strip()}")
    combined = "\n\n".join(partial_summaries)
    return call_gemini(f"Combine these summaries into one clean, well-structured summary:\n\n{combined}")

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)

# ---------------- STREAMLIT APP ----------------
st.set_page_config(page_title="Chatbot", layout="wide")
st.title("Chatbot")

# Init state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "generated_files" not in st.session_state:
    st.session_state.generated_files = []
if "generated_images" not in st.session_state:
    st.session_state.generated_images = []
if "summary_text" not in st.session_state:
    st.session_state.summary_text = None

# ---------------- CHAT ----------------
for role, content in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(content)

if prompt := st.chat_input("Type a message, ask for a PPT, DOC, or Image ..."):
    st.session_state.messages.append(("user", prompt))
    text = prompt.lower()
    try:
        if "ppt" in text or "presentation" in text or "slides" in text:
            outline_text = call_gemini(f"Create a PowerPoint outline with 5 slides about: {prompt}")
            title = call_gemini(f"Create a short, presentation-style title for: {prompt}")
            slides = parse_points(outline_text)
            st.session_state.outline = {"title": title, "slides": slides}
            st.session_state.messages.append(("assistant", "✅ PPT outline generated! Preview below."))

        elif "doc" in text or "document" in text or "report" in text:
            outline_text = call_gemini(f"Create a document outline with 5 sections about: {prompt}")
            title = call_gemini(f"Create a short, report-style title for: {prompt}")
            sections = parse_points(outline_text)
            st.session_state.outline = {"title": title, "sections": sections}
            st.session_state.messages.append(("assistant", "✅ DOC outline generated! Preview below."))

        elif "image" in text or "picture" in text or "photo" in text:
            img_bytes = generate_image_stability(prompt)
            filename = f"image_{len(st.session_state.generated_images)+1}.png"
            st.session_state.generated_images.append({"filename": filename, "content": img_bytes})
            st.image(img_bytes, caption=filename, use_container_width=True)
            st.session_state.messages.append(("assistant", "✅ Image generated!"))

        else:
            reply = call_gemini(prompt)
            st.session_state.messages.append(("assistant", reply))

    except Exception as e:
        st.session_state.messages.append(("assistant", f"⚠️ Error: {e}"))
    st.rerun()

# ---------------- OUTLINE PREVIEW ----------------
if "outline" in st.session_state:
    outline = st.session_state.outline
    mode = "ppt" if "slides" in outline else "doc"
    items = outline.get("slides", []) if mode == "ppt" else outline.get("sections", [])

    st.subheader(f"📝 Preview Outline: {outline['title']}")
    for idx, item in enumerate(items, start=1):
        with st.expander(f"{'Slide' if mode=='ppt' else 'Section'} {idx}: {item['title']}"):
            st.markdown(item["description"].replace("\n", "\n\n"))

    if st.button(f"✅ Generate {mode.upper()}"):
        filename = f"{sanitize_filename(outline['title'])}.{ 'pptx' if mode=='ppt' else 'docx'}"
        filepath = os.path.join("generated_files", filename)
        os.makedirs("generated_files", exist_ok=True)

        if mode == "ppt":
            create_ppt(outline["title"], items, filename=filepath)
        else:
            create_doc(outline["title"], items, filename=filepath)

        with open(filepath, "rb") as f:
            data = f.read()
        st.download_button(
            f"⬇️ Download {mode.upper()}",
            data=data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                 if mode=="ppt" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )


