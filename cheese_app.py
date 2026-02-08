import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
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

# --- HEADER ---
col1, col2, col3 = st.columns([3, 2, 3])

with col2:
    possible_names = ["logo_new.png", "logo_new.jpg", "logo.jpg", "logo.png", "logo"]
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            break
    else:
        st.write("🧀")

    st.markdown(
        """
        <h5 style='text-align: center; color: #444; font-weight: 600; margin-top: -5px;'>
        Hispanic Cheese Makers<br>Nuestro Queso
        </h5>
        """, 
        unsafe_allow_html=True
    )

st.markdown("---")

# --- 1. DATA LOADING (Cached) ---
@st.cache_resource(ttl=3600) 
def load_all_data():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/category-knowledge/"
    ]
    web_text = ""
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            clean = soup.get_text(' ', strip=True)[:4000]
            web_text += f"\nSOURCE: {url}\nTEXT: {clean}\n"
        except: continue
        
    pdfs = []
    local_files = glob.glob("*.pdf")
    for f in local_files:
        try: pdfs.append(genai.upload_file(f))
        except: pass

    return web_text, pdfs

# --- INITIAL LOAD ---
with st.spinner("Initializing System..."):
    live_web_text, ai_pdfs = load_all_data()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("How can I help you? / ¿Cómo te puedo ayudar?"):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        system_prompt = f"""
        You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
        
        RULES:
        1. **VIDEO/TRENDS LINKS**: 
           - ONLY provide the "Category Knowledge" link (https://hcmakers.com/category-knowledge/) IF the user explicitly asks for **videos**, **market trends**, or **visual insights**.
           - **DO NOT** add this link for standard questions about nutrition, ingredients, or pack sizes.
        
        2. **SPECS**: Use the PDF tables for numbers (Protein, Pack sizes).
        3. **CONTACT**: Plant: Kent, IL (847-258-0375).
        4. **NO IMAGES**: Text descriptions only.
        5. **LANG**: English or Spanish.
        
        WEBSITE CONTEXT:
        {live_web_text}
        """
        
        payload = [system_prompt] + ai_pdfs + [prompt]
        
        try:
            # 1. GET THE RAW STREAM
            stream = model.generate_content(payload, stream=True)
            
            # 2. FILTER: EXTRACT TEXT ONLY (This fixes the error)
            def stream_text_only():
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text

            # 3. WRITE THE CLEAN TEXT
            response_text = st.write_stream(stream_text_only)
            
            # 4. SAVE TO HISTORY
            st.session_state.chat_history.append({"role": "assistant", "content": response_text})
        except:
            st.error("Connection refreshing... please try again.")