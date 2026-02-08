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

# --- HEADER (CENTERED LOGO ICON + TITLE) ---
# We use [3, 2, 3] to squeeze the content into the middle so it looks like a mobile app header
col1, col2, col3 = st.columns([3, 2, 3])

with col2:
    # 1. Search for the logo (New or Old names)
    possible_names = ["logo_new.png", "logo_new.jpg", "logo.jpg", "logo.png"]
    for p in possible_names:
        if os.path.exists(p):
            # width=150 ensures the icon stays small and crisp, not huge
            st.image(p, width=150)
            break
    else:
        st.write("🧀")

    # 2. Centered Title below image
    st.markdown("<h4 style='text-align: center; color: #444; margin-top: -10px;'>Hispanic Cheese Makers-Nuestro Queso</h4>", unsafe_allow_html=True)

st.markdown("---")

# --- 1. LIVE WEBSITE SCRAPER ---
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

# --- 2. PDF LOADER ---
@st.cache_resource(ttl=3600)
def process_live_pdfs():
    ai_docs = []
    # Grab Local PDFs
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
    
    RULES:
    1. **VIDEO REQUESTS**: 
       - If the user asks for videos, spicy cheese trends, or visual content:
       - **ALWAYS** direct them to the Knowledge Hub.
       - Reply: "You can watch our trend videos and category insights on our Knowledge Hub: https://hcmakers.com/category-knowledge/"
    
    2. **SPECS**: Use the attached PDFs (if available) for nutrition/pack numbers.
    3. **CONTACT**: Plant in Kent, IL. Phone 847-258-0375.
    4. **NO IMAGES**: Text descriptions only.
    5. **LANG**: English or Spanish.
    
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

# --- UI: INPUT ---
if prompt := st.chat_input("Ask about our cheeses, specs, or trends..."):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_text = get_answer(prompt)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})