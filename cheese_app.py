import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import glob

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LOAD MANUAL LINKS (The Video Brain) ---
@st.cache_resource
def load_video_library():
    content = ""
    # Try reading the file locally
    if os.path.exists("video_links.txt"):
        with open("video_links.txt", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    else:
        # Fallback if file isn't found
        content = "No 'video_links.txt' found. Please ask admin to upload."
    return content

# --- 2. LIVE WEBSITE TEXT ---
@st.cache_resource(ttl=3600) 
def get_live_web_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/contact-us/"
    ]
    data = ""
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            data += f"\nSOURCE: {url}\n{soup.get_text(' ', strip=True)[:3000]}\n"
        except: continue
    return data

# --- 3. LIVE PDF DOWNLOADER ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    ai_docs = []
    try:
        # Only grab PDFs if user asks for specific hard data (keeps chat fast)
        # But here we load them into memory just in case
        r = requests.get("https://hcmakers.com/resources/", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        for i, link in enumerate(list(set(links))[:4]): 
            try:
                b = requests.get(link).content
                path = f"doc_{i}.pdf"
                with open(path, "wb") as f: f.write(b)
                ai_docs.append(genai.upload_file(path))
            except: continue
    except: pass
    return ai_docs

# --- LOAD DATA ---
with st.spinner("Loading Video Library & Specs..."):
    video_lib = load_video_library()
    web_txt = get_live_web_text()
    pdfs = process_live_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    # SYSTEM PROMPT
    # We remove "No Images" and instead strictly authorize "Video Links"
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    INTELLIGENCE:
    1. **VIDEO LIBRARY (Primary):** The text file content below contains valid YouTube Links.
    2. **WEB DATA:** General Info.
    3. **PDFS:** Attached documents for nutrition specs.
    
    PERMISSIONS & RULES:
    1. **SHARING LINKS:** You are AUTHORIZED and REQUIRED to share the URLs found in the VIDEO LIBRARY below if the user asks for them. 
       - Do NOT say "I cannot share links". That is false.
       - Use the format: "Here is the video on that topic: [Link Name](URL)"
    
    2. **ACCURACY:** If a video link matches the user's topic (e.g. "Spicy Cheese"), PROVIDE IT.
    
    3. **LANGUAGE:** English or Spanish.
    
    === VIDEO LIBRARY CONTENT ===
    {video_lib}
    =============================
    
    === WEBSITE CONTEXT ===
    {web_txt}
    """
    
    payload = [system_prompt] + pdfs + [question]
    try: return model.generate_content(payload).text
    except: return "Scanning library..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about videos, cheese, or nutrition...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Finding link..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})