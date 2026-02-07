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
    possible = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LOAD MANUAL LINKS (The Video Fix) ---
@st.cache_resource
def load_manual_text_data():
    video_content = ""
    # Look for video_links.txt in the folder
    if os.path.exists("video_links.txt"):
        with open("video_links.txt", "r", encoding="utf-8") as f:
            video_content = f.read()
    else:
        video_content = "No manual video links uploaded."
        
    return video_content

# --- 2. LOAD LIVE WEBSITE TEXT ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    text_data = ""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            text_data += f"\n--- SOURCE: {url} ---\n{soup.get_text(' ', strip=True)[:4000]}\n"
        except: continue
        
    return text_data

# --- 3. LOAD MANUAL PDFs (Spec Sheets) ---
@st.cache_resource
def load_pdfs():
    pdf_files = glob.glob("*.pdf")
    active_docs = []
    
    if not pdf_files: return []

    for pdf in pdf_files:
        try:
            remote = genai.upload_file(path=pdf, display_name=pdf)
            while remote.state.name == "PROCESSING":
                time.sleep(1)
                remote = genai.get_file(remote.name)
            if remote.state.name == "ACTIVE": active_docs.append(remote)
        except: continue
            
    return active_docs

# --- INITIAL LOAD ---
with st.spinner("Syncing Database (Text + Videos + Docs)..."):
    manual_videos = load_manual_text_data()
    live_web_text = get_website_text()
    ai_pdf_files = load_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    INTELLIGENCE:
    1. **MANUAL VIDEO LIBRARY (Primary):** Use this list below to provide video links.
    2. **LIVE WEB TEXT:** For contact info/company bio.
    3. **ATTACHED PDFs:** For Nutrition/Specs.
    
    RULES:
    1. **VIDEO LINKS:** If asked about a video (Spicy Cheese, Factory, Trends), LOOK in the 'VIDEO LIBRARY' section below. 
       - Output the exact URL found there.
    
    2. **IMAGES:** Do not show images (Text Only).
    
    3. **DATA:** Use PDFs for hard numbers.
    
    4. **LANG:** English or Spanish.
    
    ====== VIDEO LIBRARY ======
    {manual_videos}
    ===========================
    
    ====== WEBSITE CONTEXT ======
    {live_web_text}
    =============================
    """
    
    payload = [system_prompt] + ai_pdf_files + [question]
    
    try:
        return model.generate_content(payload).text
    except:
        return "I am reviewing the file library. Please ask again."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about videos, specs, or products...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Checking Video Library & Docs..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})