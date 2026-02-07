import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import re
import base64

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
    possible = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. THE BASE64 IMAGE LOADER (Security Bypass) ---
def render_live_image(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/"
        }
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            # Convert bytes to Base64 to bypass browser security blocks
            b64_img = base64.b64encode(r.content).decode()
            html = f'<img src="data:image/png;base64,{b64_img}" style="width:100%; max-width:500px; border-radius:8px;">'
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.markdown(f"[View Image]({url})")
    except:
        st.markdown(f"[View Image]({url})")

# --- 2. PRIORITY IMAGES (Guaranteed Links) ---
PRIORITY_MAP = {
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg"
}

# --- 3. LIVE ASSET HUNTER ---
@st.cache_resource(ttl=3600)
def get_text_and_images():
    # SCRAPE TEXT & EXTRA IMAGES
    web_text = "WEBSITE DATA:\n"
    img_catalog = "ADDITIONAL IMAGES:\n"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]

    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\nPAGE: {u}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            # Find Images
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and "uploads" in src and "logo" not in src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    name = src.split("/")[-1]
                    img_catalog += f"FILE: {name} | URL: {src}\n"
        except: pass
        
    return web_text, img_catalog

@st.cache_resource(ttl=3600)
def get_live_pdfs():
    # PDF DOWNLOADER
    pdf_docs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        for i, link in enumerate(list(set(links))[:4]): 
            try:
                pdf_data = requests.get(link, headers=headers).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(pdf_data)
                pdf_docs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return pdf_docs

# --- LOAD ---
with st.spinner("Initializing System..."):
    # Fix: We split the calls so variables align correctly
    txt_data, extra_imgs = get_text_and_images()
    ai_files = get_live_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_response(question):
    img_keys = "\n".join([f"- KEY: {k} | URL: {v}" for k, v in PRIORITY_MAP.items()])
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS (Prioritized):
    {img_keys}
    
    ADDITIONAL ASSETS:
    {extra_imgs}
    
    RULES:
    1. **NO PYTHON/CODE:** Speak naturally.
    2. **IMAGES:** 
       - Look for the KEY (e.g. 'CHEESE FRIES', 'PLANT') or matching URL in Additional Assets.
       - OUTPUT: `<<<IMG: URL_HERE>>>`.
       - *Note: Fries/Bites/Cotija are all in the Prioritized list.*
       
    3. **DATA:** Use PDFs for specs.
    4. **LANG:** English or Spanish.
    
    WEBSITE CONTEXT:
    {txt_data}
    """
    
    payload = [system_prompt] + ai_files + [question]
    try: return model.generate_content(payload).text
    except: return "Calculating..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_url" in message:
            render_live_image(message["img_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            raw = get_response(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            clean = clean.replace("```python", "").replace("```", "").replace("print", "")
            
            st.markdown(clean)
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_live_image(url)

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_url"] = url
            st.session_state.chat_history.append(msg)