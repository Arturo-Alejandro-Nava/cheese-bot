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

# --- 1. THE "SMUGGLER" IMAGE RENDERER (The Anti-Block Fix) ---
def render_image_b64(url):
    """
    Downloads image on server (Python), converts to Base64 text string,
    and displays via HTML. Bypasses 100% of website security blocks.
    """
    if not url: return

    try:
        # We spoof a real browser User Agent so they don't block Python
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/"
        }
        
        # Download Raw Data
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            # Convert to Base64 String
            b64_string = base64.b64encode(r.content).decode()
            
            # Inject HTML with Data URI
            html = f"""
            <div style="margin: 10px 0;">
                <img src="data:image/jpeg;base64,{b64_string}" 
                     style="max-width: 500px; width: 100%; border-radius: 8px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1);">
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
        else:
            # Last Resort if file is gone
            st.markdown(f"[Click to View Image Externally]({url})")
            
    except:
        st.markdown(f"[Click to View Image Externally]({url})")

# --- 2. LIVE CRAWLER (The Hunter) ---
@st.cache_resource(ttl=3600)
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # TEXT SCRAPING
    web_text = "WEBSITE DATA:\n"
    # IMAGE CATALOGING
    image_catalog = "AVAILABLE LIVE IMAGES (URLs):\n"
    
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Plant photos
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",   # Office/Map
        "https://hcmakers.com/about-us/"
    ]
    
    seen_images = []
    
    status = st.empty()
    status.text("Scanning live website for assets...")

    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # Text
            clean_text = soup.get_text(" ", strip=True)[:4000]
            web_text += f"\nPAGE: {u}\nCONTENT: {clean_text}\n"
            
            # Images
            imgs = soup.find_all('img')
            for img in imgs:
                # Handle Lazy Loading (data-src)
                src = img.get('data-src') or img.get('src')
                alt = img.get('alt', 'Image')
                
                if src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    
                    # Filtering Logic
                    is_junk = any(x in src.lower() for x in ['logo', 'icon', 'svg', 'spacer', 'blank', 'pixel', 'facebook'])
                    is_useful = "uploads" in src
                    
                    if is_useful and not is_junk and src not in seen_images:
                        # Extract nice filename for AI context
                        filename = src.split("/")[-1]
                        image_catalog += f"DESC: {alt} ({filename}) | URL: {src}\n"
                        seen_images.append(src)
        except: continue
        
    # DOCUMENTS
    doc_pdfs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        for i, l in enumerate(list(set(links))[:5]):
            try:
                b = requests.get(l, headers=headers).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(b)
                doc_pdfs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    status.empty()
    return web_text, image_catalog, doc_pdfs

# --- INIT ---
with st.spinner("Syncing Live Data..."):
    txt_data, img_lib, ai_docs = get_live_data()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS AVAILABLE (Live Scraped URLs):
    {img_lib}
    
    RULES:
    1. **FINDING IMAGES**:
       - Scan the 'ASSETS AVAILABLE' list.
       - Use "Fuzzy Logic":
         - User: "Cotija" -> Look for `cotija` in DESC or URL. (e.g., `YBH_cotija_wedge...png`)
         - User: "Plant" or "Factory" -> Look for `7777` or `PLANT`.
         - User: "Office" -> Look for `display` or `building` from Contact page.
         - User: "Bites" -> Look for `OaxacaBites`.
       - **OUTPUT FORMAT:** Start response with `<<<IMG: FULL_URL_HERE>>>`
    
    2. **DATA**: Use Attached PDFs for specs.
    3. **LANG**: English or Spanish.
    
    WEBSITE CONTEXT:
    {txt_data}
    """
    
    payload = [system_prompt] + ai_docs + [question]
    try: return model.generate_content(payload).text
    except: return "Retrieving..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_src" in message:
            render_image_b64(message["img_src"])

with st.form("chat_form"):
    user_input = st.text_input("Ask about products or request an image...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"): st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                
            st.markdown(clean)
            if url: render_image_b64(url) # Using Smuggler Function

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_src"] = url
            st.session_state.chat_history.append(msg)