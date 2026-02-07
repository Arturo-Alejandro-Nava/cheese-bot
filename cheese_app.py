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

# --- 1. HTML INJECTION RENDERER (The Anti-Block) ---
def render_image(url):
    """
    Forces the browser to load the image directly from the source,
    stripping the 'Referer' to bypass security blocks.
    """
    if not url: return
    
    html = f"""
    <div style="margin: 10px 0;">
        <img src="{url}" 
             referrerpolicy="no-referrer"
             style="max-width: 500px; width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- 2. LIVE UNIVERSAL CRAWLER (The Aggressive Scraper) ---
@st.cache_resource(ttl=3600) 
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"}
    
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory images
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/quality/"
    ]
    
    web_text = "WEBSITE DATA:\n"
    img_list = "FOUND IMAGES (LIVE):\n"
    seen = []
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            content_str = r.text
            
            # A. Extract Text
            soup = BeautifulSoup(content_str, 'html.parser')
            web_text += f"\nPAGE: {u}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            # B. Extract ALL Images (Regex Method)
            # Finds http....png/jpg inside CSS, Scripts, and HTML
            raw_links = re.findall(r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|webp)', content_str)
            
            for src in raw_links:
                if '\\' in src: src = src.replace('\\', '') # Fix JS encoded links
                if src in seen: continue
                
                # Filter Junk
                lower = src.lower()
                if any(x in lower for x in ['logo', 'icon', 'svg', 'spacer', 'blank', 'facebook']): continue
                if "uploads" not in lower: continue
                
                # C. Filename Cleaning (Crucial for AI Understanding)
                # Helps AI match "YBH_Mexicana" to "Crema Mexicana"
                fname = src.split("/")[-1]
                decoded_name = fname.replace("YBH", "").replace("_", " ").replace("-", " ").replace("web", "")
                
                img_list += f"- NAME: {decoded_name} | FULL_URL: {src}\n"
                seen.append(src)
                
        except: continue

    # DOCUMENTS
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = re.findall(r'href=[\'"]?([^\'" >]+)', r.text)
        pdf_links = [l for l in links if l.endswith(".pdf")]
        
        for i, link in enumerate(list(set(pdf_links))[:5]):
            try:
                if not link.startswith("http"): link = "https://hcmakers.com" + link
                pdf_data = requests.get(link).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(pdf_data)
                pdf_docs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return web_text, img_list, pdf_docs

# --- LOAD ---
with st.spinner("Scraping live site for Crema & Cheese images..."):
    text_data, img_catalog, ai_files = get_live_data()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_response(question):
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSET LIBRARY (Scraped from Live Website):
    {img_catalog}
    
    RULES FOR IMAGES:
    1. **FIND THE BEST MATCH:** Look at the 'NAME' field in the list above. 
       - "Crema Mexicana" -> Look for names with 'Mexicana', 'Tub', or 'Cream'.
       - "Cotija" -> Look for 'Cotija', 'Wedge', or 'Quarter'.
       - "Office" -> Look for 'Display', 'Building'.
       
    2. **OUTPUT:** Return the EXACT URL tag: `<<<IMG: https://...>>>`.
    
    3. **BE PROACTIVE:** If the user asks for "Crema Mexicana", DO NOT SAY "I don't have it." Search the list for `Mexicana_Tub` or similar. It IS there.
    
    4. **LANG:** English/Spanish.
    
    WEBSITE CONTEXT:
    {text_data}
    """
    
    payload = [system_prompt] + ai_files + [question]
    try: return model.generate_content(payload).text
    except: return "Scanning..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_url" in message:
            render_image(message["img_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Locating..."):
            raw = get_response(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            # Safety clean
            clean = clean.replace("```python", "").replace("```", "")
            
            st.markdown(clean)
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_image(url)

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_url"] = url
            st.session_state.chat_history.append(msg)