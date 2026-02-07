import streamlit as st
import google.generativeai as genai
import os
import requests
from bs4 import BeautifulSoup
import time
import io
import fitz  # PyMuPDF
import re
import glob

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    possible = ["logo.jpg", "logo.png", "logo.jpeg"]
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); break
    else: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. LOCAL IMAGE DISPLAY ---
def show_local_image(filename):
    if os.path.exists(filename):
        st.image(filename, width=500)
    else:
        # Fallback if specific file missing, check directory
        st.warning(f"File not found: {filename}")

# --- 2. ASSET MAPPING (THE LOGIC FIX) ---
# We explicitly map the filenames you downloaded to their Real World meaning.
# This prevents the AI from showing the office when you ask for the plant.
FILE_MAP = """
CRITICAL VISUAL ASSET DICTIONARY (Use ONLY these filenames):
- IMAGE: AERIAL PLANT / FACTORY / BUILDING OUTSIDE -> Filename: '7777-1.jpg'
- IMAGE: FACTORY INSIDE / PRODUCTION LINE -> Filename: 'PLANT_138.jpg'
- IMAGE: CORPORATE OFFICE / HEADQUARTERS -> Filename: 'display.jpg'
- IMAGE: LAB / QUALITY ASSURANCE -> Filename: 'Quality-Lab.jpg'
- IMAGE: CHEESE FRIES PACKAGE -> Filename: 'CheeseFries-web.png'
- IMAGE: OAXACA BITES PACKAGE -> Filename: 'OaxacaBites-web.png'
- IMAGE: FRESCO CHEESE -> Filename: 'Fresco-Natural-10oz.png'
- IMAGE: COTIJA CHEESE -> Filename: 'cotija-wedge-10oz-cp.png'
- IMAGE: OAXACA CHEESE -> Filename: 'OAXACA-BALL-5lb-v3.png'
"""

# --- 3. LIVE KNOWLEDGE SCRAPER ---
@st.cache_resource(ttl=3600)
def get_knowledge_base():
    # 1. Text Scraper
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]
    web_text = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            web_text += s.get_text(" ", strip=True)[:3000] + "\n"
        except: pass

    # 2. PDF Downloader
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        for i, link in enumerate(list(set(links))[:5]):
            try:
                data = requests.get(link).content
                path = f"doc_{i}.pdf"
                with open(path, "wb") as f: f.write(data)
                pdf_docs.append(genai.upload_file(path))
            except: continue
        
        # Wait
        ready = []
        for p in pdf_docs:
            while p.state.name == "PROCESSING": time.sleep(1); p = genai.get_file(p.name)
            ready.append(p)
    except: ready = []

    return web_text, ready

# --- LOAD ---
with st.spinner("Calibrating Asset Library..."):
    web_data, pdf_files = get_knowledge_base()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    contact_info = "PHONE: 847-258-0375 (Sandy), 847-502-0934 (Arturo Nava). ADDRESS: 752 N. Kent Road, Kent IL."
    
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers".
    
    VISUAL RULES (CRITICAL):
    1. **MAPPING:** Use the 'VISUAL ASSET DICTIONARY' below.
       - If asked for "Plant" or "Factory", you MUST use `7777-1.jpg`. (Do NOT use display.jpg, that is the office).
       - If asked for "Office", use `display.jpg`.
       - If asked for "Bites", use `OaxacaBites-web.png`.
    2. **OUTPUT:** Reply with the exact tag: `<<<IMG: filename.jpg>>>`.
    3. **DATA:** Use PDFs for nutrition.
    4. **LANG:** English/Spanish.
    
    {FILE_MAP}
    
    WEBSITE CONTEXT:
    {web_data}
    {contact_info}
    """
    payload = [system_prompt] + pdf_files + [question]
    try: return model.generate_content(payload).text
    except: return "Retrieving..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "img_path" in message:
            show_local_image(message["img_path"])
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Checking Files..."):
            raw = get_answer(user_input)
            
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            img_file = None
            if match:
                img_file = match.group(1).strip()
                show_local_image(img_file)
            
            st.markdown(clean)
            
            msg = {"role": "assistant", "content": clean}
            if img_file: msg["img_path"] = img_file
            st.session_state.chat_history.append(msg)