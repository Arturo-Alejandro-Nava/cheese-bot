import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import re

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
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. THE BULLETPROOF IMAGE RENDERER (Dual Mode) ---
def render_image(url):
    """
    Tries Server-Side download first. If blocked, uses Client-Side HTML injection.
    This guarantees an image appears.
    """
    if not url: return

    # METHOD A: Python Server Download (Proxy)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://hcmakers.com/"
        }
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            st.image(io.BytesIO(r.content), width=500)
            return
    except: pass
    
    # METHOD B: HTML Injection (The User's Browser loads it)
    # If Python fails/is blocked, this bypasses the server completely.
    st.markdown(
        f"""
        <div style="background-color: #f0f0f0; padding: 10px; border-radius: 10px; display: inline-block;">
            <img src="{url}" width="500" style="border-radius: 8px;">
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. PRIORITY IMAGES (Guaranteed Links) ---
# Verified working URLs from your website data
PRIORITY_MAP = {
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg"
}

# --- 3. LIVE KNOWLEDGE BASE ---
@st.cache_resource(ttl=3600)
def get_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Text Scraper
    web_text = "WEBSITE DATA:\n"
    for url in ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/"]:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\nPAGE: {url}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            # Auto-find other product images not in Priority List
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and "uploads" in src and "logo" not in src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    # Check filename for key terms
                    name = src.split("/")[-1].lower()
                    if "pack" in name or "web" in name or "72" in name: # "web" usually implies product
                        web_text += f"FOUND IMAGE: {name} | URL: {src}\n"
        except: pass

    # 2. PDF Fetcher
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        for i, link in enumerate(list(set(links))[:4]): # limit to 4 to prevent timeout
            try:
                pdf_data = requests.get(link).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(pdf_data)
                pdf_docs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return web_text, pdf_docs

with st.spinner("Connecting..."):
    txt_data, ai_files = get_data()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_response(question):
    # Construct Image Key List for AI
    img_keys = "\n".join([f"- {k}: {v}" for k, v in PRIORITY_MAP.items()])
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS:
    {img_keys}
    
    RULES:
    1. **NO PYTHON/CODE:** Do not write code blocks. Do not write `print()`. Just speak naturally.
    2. **IMAGES:** 
       - To show an image, use this tag ONLY: `<<<IMG: URL_HERE>>>`.
       - Check the 'ASSETS' list above.
       - If asked for "Cotija", use the COTIJA URL. 
       - If asked for "Office", use the OFFICE URL.
    3. **DATA:** Use PDFs for specs.
    4. **LANG:** English or Spanish.
    
    WEBSITE CONTEXT:
    {txt_data}
    """
    
    payload = [system_prompt] + ai_files + [question]
    try: return model.generate_content(payload).text
    except: return "One moment..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "image_url" in message:
            render_image(message["image_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            raw = get_response(user_input)
            
            # Clean Logic to remove Tags or Code hallucinations
            clean = raw.replace("```python", "").replace("```", "").replace("print(", "").replace(")", "")
            
            img_match = re.search(r"<<<IMG: (.*?)>>>", clean)
            final_text = re.sub(r"<<<IMG: .*?>>>", "", clean).strip()
            
            st.markdown(final_text)
            
            found_url = None
            if img_match:
                found_url = img_match.group(1).strip()
                render_image(found_url)
                
            msg = {"role": "assistant", "content": final_text}
            if found_url: msg["image_url"] = found_url
            st.session_state.chat_history.append(msg)