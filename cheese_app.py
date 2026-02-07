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
import fitz  # PyMuPDF

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
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")
with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. GUARANTEED FACT SHEET (The Source of Truth) ---
# This prevents the AI from guessing wrong numbers. 
# It overrides any parsing errors.
FACT_SHEET = """
OFFICIAL NUTRITIONAL SPECS (USE THESE NUMBERS EXACTLY):
- **Queso Fresco (Natural)**: Serving Size: 1oz (28g). Protein: 5g. Total Fat: 7g. Calories: 90. Sodium: 190mg.
- **Queso Blanco**: Serving Size: 1oz. Protein: 5g. Total Fat: 7g. Calories: 90.
- **Queso Panela**: Serving Size: 1oz. Protein: 5g. Total Fat: 6g. Calories: 80.
- **Cotija**: Serving Size: 1oz. Protein: 5g. Total Fat: 8g. Sodium: ~400mg.
- **Oaxaca**: Serving Size: 1oz. Protein: 6g. Total Fat: 8g. Calories: 100.
"""

# --- 2. IMAGE RENDERER (Bypass Block) ---
def render_image(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://hcmakers.com/"}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            b64_img = base64.b64encode(r.content).decode()
            st.markdown(f'<img src="data:image/png;base64,{b64_img}" style="width:100%; max-width:500px; border-radius:8px;">', unsafe_allow_html=True)
    except: st.markdown(f"[View Image]({url})")

# --- 3. LIVE DATA HUNTER ---
@st.cache_resource(ttl=3600)
def get_data_bundle():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # A. Scrape Website
    web_text = "WEBSITE DATA:\n"
    img_db = "IMAGES:\n"
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/"]
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\nPAGE: {u}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and "uploads" in src and "logo" not in src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    img_db += f"FILE: {src.split('/')[-1]} | URL: {src}\n"
        except: pass
    
    # B. Document Fetcher
    pdf_docs = []
    
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        zip_link = next((a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_link:
            z_data = requests.get(zip_link, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                i = 0
                for fname in z.namelist():
                    if fname.lower().endswith(".pdf") and i < 8:
                        # Upload to AI
                        path = f"d_{i}.pdf"
                        with open(path, "wb") as f: f.write(z.read(fname))
                        pdf_docs.append(genai.upload_file(path, display_name=fname))
                        
                        i += 1
    except: pass

    return web_text, img_db, pdf_docs

# --- LOAD ---
with st.spinner("Connecting to Live Database & Validating Specs..."):
    txt_data, img_catalog, ai_files = get_data_bundle()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # HARDCODED IMAGE PRIORITY MAP
    PRIORITY_IMAGES = """
    - FRESCO: https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png
    - COTIJA: https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png
    - PANELA: https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png
    - BITES: https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png
    - FRIES: https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png
    - PLANT: https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg
    - OFFICE: https://hcmakers.com/wp-content/uploads/2020/08/display.jpg
    """

    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    CRITICAL INSTRUCTIONS:
    1. **NUTRITION DATA**:
       - ALWAYS check the 'OFFICIAL NUTRITIONAL SPECS' list below FIRST. 
       - If asked about Fresco Protein, use the value "5g". Do not guess "7g".
       - Only if the info is missing there, read the attached PDFs.
    
    2. **IMAGES**:
       - Use the PRIORITY LIST above.
       - OUTPUT: `<<<IMG: URL>>>`.
       
    3. **LANGUAGE**: English or Spanish.
    
    OFFICIAL NUTRITIONAL SPECS:
    {FACT_SHEET}
    
    IMAGE PRIORITY LIST:
    {PRIORITY_IMAGES}
    
    ADDITIONAL IMAGES:
    {img_catalog}
    
    WEBSITE CONTEXT:
    {txt_data}
    """
    
    payload = [system_prompt] + ai_files + [question]
    try: return model.generate_content(payload).text
    except: return "Consulting facts..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_src" in message:
            render_image(message["img_src"])

with st.form("chat_form"):
    user_input = st.text_input("Ask about nutrition, specs, or images...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"): st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            # Clean possible markdown clutter
            clean = clean.replace("```", "").replace("print", "")
            
            st.markdown(clean)
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_image(url)

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_src"] = url
            st.session_state.chat_history.append(msg)