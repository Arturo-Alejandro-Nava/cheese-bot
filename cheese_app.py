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

# --- 1. THE "BASE64" SMUGGLER (THE FIX) ---
def render_live_image(url, caption=""):
    """
    Downloads the image on the server, converts it to Base64 code,
    and displays it. This bypasses 100% of Hotlink Protection.
    """
    if not url: return

    try:
        # 1. Download as "Chrome User"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/"
        }
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            # 2. Convert to Base64 String
            img_b64 = base64.b64encode(r.content).decode()
            
            # 3. Create HTML Data-URI
            html = f'''
            <div style="margin: 10px 0;">
                <img src="data:image/png;base64,{img_b64}" 
                     style="max-width: 100%; border-radius: 8px; border: 1px solid #ccc; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                <div style="color: grey; font-size: 0.8em; margin-top: 5px;">{caption}</div>
            </div>
            '''
            st.markdown(html, unsafe_allow_html=True)
        else:
            # If download fails, show link
            st.markdown(f"**Image Source:** [View Image]({url})")
            
    except Exception as e:
        st.markdown(f"**Image Source:** [View Image]({url})")


# --- 2. UNIVERSAL IMAGE HUNTER (Scraper) ---
@st.cache_resource(ttl=3600) 
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Scrape Website Text
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/", "https://hcmakers.com/quality/"]
    web_text = "WEBSITE DATA:\n"
    img_library = "IMAGE URLS:\n"
    seen = []
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\n-- {u} --\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            for img in soup.find_all('img'):
                src = img.get('src')
                # Try to get high-res from data-src if available
                if img.get('data-src'): src = img.get('data-src')
                
                if src:
                    if src.startswith('/'): src = "https://hcmakers.com" + src
                    # Filter logic
                    clean_name = src.split("/")[-1].lower()
                    if "uploads" in src and "logo" not in clean_name and "icon" not in clean_name:
                         if src not in seen:
                            img_library += f"FILE: {clean_name} | URL: {src}\n"
                            seen.append(src)
        except: continue

    # 2. Manual "Emergency" Image List (Hardcoded high-value items)
    emergency_list = [
        "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg (PLANT_AERIAL)",
        "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg (FACTORY_INSIDE)",
        "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png (CHEESE_FRIES_PKG)",
        "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png (OAXACA_BITES_PKG)",
        "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png (FRESCO_CHEESE)",
        "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_quarter_5lb.png (COTIJA_CHEESE)"
    ]
    for url in emergency_list:
        img_library += f"VIP: {url}\n"
        
    return web_text, img_library

# --- 3. DOC FETCH ---
@st.cache_resource(ttl=3600)
def get_pdf_assets():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        valid = []
        count = 0
        for l in list(set(links)):
            if count > 4: break
            try:
                b = requests.get(l).content
                p = f"t_{count}.pdf"
                with open(p, "wb") as f: f.write(b)
                valid.append(genai.upload_file(p))
                count+=1
            except: continue
        
        # Wait
        active = []
        for v in valid:
             while v.state.name == "PROCESSING": time.sleep(1); v=genai.get_file(v.name)
             active.append(v)
        return active
    except: return []

# --- INIT ---
with st.spinner("Connecting..."):
    txt, imgs, pdfs = get_live_data()
    docs = get_pdf_assets()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_smart_answer(question):
    sys_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS:
    {imgs}
    
    RULES:
    1. **FINDING IMAGES**:
       - Scan the 'IMAGE URLS' list. Match user request (Cotija, Fries, Plant).
       - Look at filenames! `7777-1.jpg` IS THE AERIAL PLANT. `CheeseFries` is Fries. `YBH_cotija` is Cotija.
       - OUTPUT: `<<<IMG: URL_HERE>>>`
       
    2. **PLANT vs OFFICE**:
       - If asked for "Office", reply "Here is our Headquarters location" and use the 'display.jpg' or similar if found, otherwise use Text description.
       - If asked for "Plant/Factory", use '7777-1.jpg' or 'PLANT_138.jpg'.
    
    3. **DATA**: Use Attached PDFs for specs.
    4. **LANG**: English or Spanish.
    
    WEBSITE CONTEXT:
    {txt}
    """
    try: return model.generate_content([sys_prompt] + docs + [question]).text
    except: return "One moment..."

# --- RENDER UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "url" in message:
            render_live_image(message["url"]) # Render historical images

with st.form("chat_form"):
    q = st.text_input("Ask question...")
    sub = st.form_submit_button("Send")

if sub and q:
    with st.chat_message("user"): st.markdown(q)
    st.session_state.chat_history.append({"role": "user", "content": q})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            res = get_smart_answer(q)
            
            # Clean Tag
            clean = re.sub(r"<<<IMG: .*?>>>", "", res).strip()
            img_tag = re.search(r"<<<IMG: (.*?)>>>", res)
            
            st.markdown(clean)
            
            final_url = None
            if img_tag:
                final_url = img_tag.group(1).strip()
                render_live_image(final_url, "Found Result")
            
            msg = {"role": "assistant", "content": clean}
            if final_url: msg["url"] = final_url
            st.session_state.chat_history.append(msg)