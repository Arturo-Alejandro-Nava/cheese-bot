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

# --- 1. THE BROWSER-BASED IMAGE RENDERER (The Fix) ---
def render_image(url):
    """
    Forces the USER'S browser to load the image via HTML.
    This bypasses the 403 Server Blocks because the request comes from a human, not the bot.
    """
    if not url: return

    # Standard HTML <img> tag with styling
    # This keeps the image request client-side
    st.markdown(
        f"""
        <div style="text-align: center; margin: 10px 0;">
            <img src="{url}" alt="Product Image" style="max-width: 500px; width: 100%; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. PRIORITY IMAGES (Guaranteed Links) ---
# Verified URLs that work in browsers
PRIORITY_MAP = {
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA SHRED": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    # Using generic display image for Office to ensure something loads
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg"
}

# --- 3. LIVE KNOWLEDGE BASE ---
@st.cache_resource(ttl=3600)
def get_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Text Scraper
    web_text = "WEBSITE DATA:\n"
    img_catalog = "ADDITIONAL IMAGES:\n"
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\nPAGE: {u}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            # Auto-find other product images
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and "uploads" in src and "logo" not in src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    name = src.split("/")[-1]
                    img_catalog += f"FILE: {name} | URL: {src}\n"
        except: pass

    # 2. PDF Fetcher
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        for i, link in enumerate(list(set(links))[:4]): 
            try:
                pdf_data = requests.get(link).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(pdf_data)
                pdf_docs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return web_text, img_catalog, pdf_docs

with st.spinner("Connecting to Live Data..."):
    txt_data, extra_imgs, ai_files = get_data()

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
    1. **NO PYTHON/CODE:** Do not write code blocks. Just natural text.
    2. **IMAGES:** 
       - Look for the KEY (e.g. 'OAXACA BITES') or matching URL in Additional Assets.
       - OUTPUT: `<<<IMG: URL_HERE>>>`.
       - Always verify the item matches the request (don't show awards for cheese).
       
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
        # If there's an image attached to the message state, show it via HTML
        if "img_url" in message:
            render_image(message["img_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about our products... / Pregunta sobre nuestros productos...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            raw = get_response(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            # Clean possible markdown clutter
            clean = clean.replace("```python", "").replace("```", "").replace("print(", "").replace(")", "")
            
            st.markdown(clean)
            
            # Logic: If URL found, display using HTML
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_image(url)

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_url"] = url
            st.session_state.chat_history.append(msg)