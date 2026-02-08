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

# --- HEADER (CENTERED LOGO + CUSTOM SERIF FONT TITLE) ---
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # 1. Logo
    possible_names = ["logo_new.png", "logo_new.jpg", "logo.jpg", "logo.png", "logo"]
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            break
    else:
        st.write("🧀")

    # 2. Custom HTML Title (Matching the Screenshot Font)
    # Font: Serif. Color: Dark Blue/Grey. Style: Uppercase + Spaced.
    st.markdown(
        """
        <style>
        .classic-title {
            font-family: 'Times New Roman', Times, serif; 
            color: #3b4d61; 
            text-align: center;
            font-size: 22px; 
            letter-spacing: 1.5px;
            line-height: 1.4;
            text-transform: uppercase;
            font-weight: 400;
            margin-top: 10px;
            margin-bottom: 20px;
        }
        </style>
        
        <div class="classic-title">
            Hispanic Cheese Makers<br>
            Nuestro Queso
        </div>
        """, 
        unsafe_allow_html=True
    )

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
    # Grab Local PDFs uploaded to GitHub
    local_files = glob.glob("*.pdf")
    for f in local_files:
        try:
            ai_docs.append(genai.upload_file(f))
        except: pass
    return ai_docs

# --- LOAD DATA ---
with st.spinner("Syncing..."):
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
       - If user asks for videos, trends, or visual content:
       - **ALWAYS** direct them to the Knowledge Hub.
       - Reply: "You can watch our trend videos and category insights on our Knowledge Hub: https://hcmakers.com/category-knowledge/"
    
    2. **SPECS & NUTRITION**: 
       - Use the attached PDF Documents to find protein, fat, and pack sizes. Read the tables visually.
    
    3. **CONTACT INFO**: 
       - Plant: 752 N. Kent Road, Kent, IL 61044. 
       - Phone (Sales): 847-258-0375.
    
    4. **NO IMAGES**: Do not display images directly. Use text descriptions.
    
    5. **LANG**: English or Spanish (Detect User Language).
    
    WEBSITE CONTEXT:
    {live_web_text}
    """
    
    payload = [system_prompt] + ai_pdfs + [question]
    
    try:
        return model.generate_content(payload).text
    except:
        return "I am verifying that information. Please ask again."

# --- UI: HISTORY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- UI: INPUT (Bilingual) ---
if prompt := st.chat_input("How can I help you? / ¿Cómo te puedo ayudar?"):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_text = get_answer(prompt)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})