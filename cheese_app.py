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
st.set_page_config(page_title="Hispanic Cheese Makers", page_icon="🧀")

# --- HEADER (CENTERED LOGO & SMALLER TITLE) ---
# We use columns to squish the content into the center
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # 1. Logo
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            break
    else:
        st.write("🧀")

    # 2. Centered, Smaller Title
    st.markdown("<h3 style='text-align: center; color: #333;'>Hispanic Cheese Makers-Nuestro Queso</h3>", unsafe_allow_html=True)

st.markdown("---")

# --- 1. LOAD MANUAL LINKS (THE VIDEO LIBRARY) ---
@st.cache_resource
def load_video_library():
    content = "NO MANUAL VIDEOS FOUND."
    if os.path.exists("video_links.txt"):
        with open("video_links.txt", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    return content

# --- 2. LOAD LIVE WEBSITE TEXT ---
@st.cache_resource(ttl=3600) 
def get_live_web_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    data = ""
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean = soup.get_text(' ', strip=True)[:4000]
            data += f"\nSOURCE PAGE: {url}\nTEXT: {clean}\n"
        except: continue
    return data

# --- 3. PDF LOADER ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    ai_docs = []
    # Grab Local PDFs First
    local_files = glob.glob("*.pdf")
    for f in local_files:
        try:
            ai_docs.append(genai.upload_file(f))
        except: pass
    return ai_docs

# --- LOAD DATA ---
with st.spinner("Syncing Video Library & Documents..."):
    video_lib_text = load_video_library()
    live_web_text = get_live_web_text()
    ai_pdfs = process_live_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    # SYSTEM BRAIN
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    --- IMPORTANT RESOURCE: VIDEO LINKS ---
    The following list contains YouTube Links for our products.
    YOU MUST USE THESE LINKS if the user asks for a video.
    
    {video_lib_text}
    ---------------------------------------
    
    --- WEBSITE KNOWLEDGE ---
    {live_web_text}
    ---------------------------------------
    
    RULES:
    1. **PROVIDE LINKS:** If asked about a video (Spicy Cheese, Factory, etc.), look at the "VIDEO LINKS" list above. Copy the URL exactly.
       - Example: "Here is the video on Spicy Cheese: https://..."
       - You ARE authorized to share links found in that list.
       
    2. **SPECS:** Use the attached PDFs (if any) for nutrition/pack size numbers.
    
    3. **NO IMAGES:** Do not try to show images. Text and Links only.
    
    4. **LANG:** English or Spanish (Detect User Language).
    """
    
    payload = [system_prompt] + ai_pdfs + [question]
    
    try:
        return model.generate_content(payload).text
    except:
        return "I am scanning the library. Please ask again."

# --- UI: HISTORY (Shows Previous Messages) ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- UI: INPUT (This pins it to the bottom!) ---
# 'st.chat_input' handles the visual location automatically.
if prompt := st.chat_input("Ask about our cheeses, videos, or specs..."):
    
    # 1. Show User Message immediately
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # 2. Get and Show Bot Message
    with st.chat_message("assistant"):
        with st.spinner("Checking Video Library..."):
            response_text = get_answer(prompt)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})