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

# --- HEADER (Centered Logo) ---
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            break
    else:
        st.write("🧀")
    
    st.markdown("<h3 style='text-align: center; color: #333;'>Hispanic Cheese Makers-Nuestro Queso</h3>", unsafe_allow_html=True)

st.markdown("---")

# --- 1. LIVE WEBSITE SCRAPER (Text) ---
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

# --- 2. PDF LOADER (Specs) ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    ai_docs = []
    # Reads local PDF files you uploaded to GitHub
    local_files = glob.glob("*.pdf")
    for f in local_files:
        try:
            ai_docs.append(genai.upload_file(f))
        except: pass
    return ai_docs

# --- LOAD DATA ---
with st.spinner("Syncing Knowledge Base..."):
    live_web_text = get_live_web_text()
    ai_pdfs = process_live_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    RULES FOR RESPONSES:
    
    1. **VIDEO REQUESTS**: 
       - If the user asks to see a video, or asks about media/trends/spicy cheese video, **DO NOT** give a YouTube link.
       - **ALWAYS** direct them to our Category Knowledge Hub page.
       - Response Example: "You can watch all our latest videos and trend reports on our Knowledge Hub here: https://hcmakers.com/category-knowledge/"
    
    2. **SPECS & NUTRITION**: 
       - Use the attached PDF Documents to find protein, fat, and pack sizes. Read the tables visually.
    
    3. **CONTACT INFO**: 
       - Plant: 752 N. Kent Road, Kent, IL 61044. 
       - Phone (Sales): 847-258-0375.
    
    4. **NO IMAGES**: Do not display images directly. Use text descriptions.
    
    5. **LANG:** English or Spanish (Detect User Language).
    
    WEBSITE CONTEXT:
    {live_web_text}
    """
    
    payload = [system_prompt] + ai_pdfs + [question]
    
    try:
        return model.generate_content(payload).text
    except:
        return "I am verifying the information. Please ask again."

# --- UI: HISTORY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- UI: INPUT (Pinned Bottom) ---
if prompt := st.chat_input("Ask about our cheeses, specs, or videos..."):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_text = get_answer(prompt)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})