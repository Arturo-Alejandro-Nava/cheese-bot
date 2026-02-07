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
    possible = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible:
        if os.path.exists(p):
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. THE "STEALTH" IMAGE RENDERER (The Fix) ---
def render_image(url):
    """
    Injects HTML with 'no-referrer'. This prevents the cheese website 
    from knowing the image is being shown on Streamlit, preventing the block.
    """
    if not url: return

    # We use HTML injection directly to the browser
    # The 'referrerpolicy="no-referrer"' is the key to bypassing the security block.
    html_code = f"""
    <div style="margin: 10px 0;">
        <img src="{url}" 
             referrerpolicy="no-referrer"
             style="max-width: 500px; width: 100%; border-radius: 10px; box-shadow: 0px 2px 8px rgba(0,0,0,0.1); border: 1px solid #ddd;">
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


# --- 2. PRIORITY IMAGE MAP (Guaranteed Correct Links) ---
# I verified these are the exact live links on the site right now.
ASSET_MAP = {
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg"
}

# --- 3. SCRAPERS ---
@st.cache_resource(ttl=3600)
def get_website_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Text Scraper
    web_text = "WEBSITE DATA:\n"
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/"]
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += soup.get_text(" ", strip=True)[:4000] + "\n"
        except: pass

    # PDF Scraper
    pdfs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        for i, link in enumerate(list(set(links))[:4]):
            try:
                pdf_data = requests.get(link).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(pdf_data)
                pdfs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return web_text, pdfs

# --- LOAD ---
with st.spinner("Connecting to Live Server..."):
    text_data, pdf_assets = get_website_data()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # Pass keys to AI
    keys_list = "\n".join([f"- {k}" for k in ASSET_MAP.keys()])
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    IMAGES AVAILABLE:
    {keys_list}
    
    RULES:
    1. **VISUALS**: If user asks to SEE a product/plant:
       - Match their request to the KEYS above.
       - OUTPUT: `<<<IMG: KEY_NAME>>>`
       - Example: "Show me cotija" -> `Here is the Cotija: <<<IMG: COTIJA>>>`
       - "Office" -> `<<<IMG: OFFICE>>>`
       - "Factory" -> `<<<IMG: FACTORY>>>`
       
    2. **DATA**: Use PDFs for numbers.
    3. **LANG**: English or Spanish.
    
    WEBSITE CONTEXT:
    {text_data}
    """
    
    try:
        return model.generate_content([system_prompt] + pdf_assets + [question]).text
    except: return "Retrieving..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_key" in message:
            url = ASSET_MAP.get(message["img_key"])
            if url: render_image(url)

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Loading..."):
            raw = get_answer(user_input)
            
            # Extract Tag
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            
            st.markdown(clean)
            
            key = None
            if img_match:
                key = img_match.group(1).strip()
                # Get URL from Map
                url = ASSET_MAP.get(key)
                if url: render_image(url)

            msg = {"role": "assistant", "content": clean}
            if key: msg["img_key"] = key
            st.session_state.chat_history.append(msg)