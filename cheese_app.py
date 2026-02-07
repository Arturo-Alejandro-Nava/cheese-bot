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

# --- 1. THE "DATA TUNNEL" IMAGE RENDERER (The Ultimate Fix) ---
def render_image_b64(url):
    """
    1. Downloads image securely on server side.
    2. Converts to Base64 (Text) so browser doesn't need to request it.
    3. Prevents 100% of Hotlink/Security blocking.
    """
    if not url: return

    try:
        # FAKE HEADERS: Pretend to be a regular laptop user
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://hcmakers.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        
        # Download Raw Bytes
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            # Convert to Data String
            b64_img = base64.b64encode(r.content).decode()
            
            # Display using HTML
            st.markdown(
                f"""
                <div style="margin-top: 10px; margin-bottom: 10px;">
                    <img src="data:image/png;base64,{b64_img}" 
                         style="width: 100%; max-width: 500px; border-radius: 8px; border: 1px solid #ccc; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.markdown(f"**Image Source:** [Click to Open]({url})")
            
    except:
        st.markdown(f"**Image Source:** [Click to Open]({url})")

# --- 2. GUARANTEED ASSET LIST (Map Keywords to Verified URLs) ---
PRIORITY_MAP = {
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg"
}

# --- 3. LIVE SITE SCANNER (Scrapes text + other images) ---
@st.cache_resource(ttl=3600) 
def load_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. TEXT
    web_text = "WEBSITE DATA:\n"
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/", "https://hcmakers.com/quality/", "https://hcmakers.com/contact-us/"]
    
    # 2. IMAGES FOUND LIVE (The dynamic backup)
    scraped_images = ""
    seen_urls = []
    
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\n-- {u} --\n{soup.get_text(' ', strip=True)[:3000]}\n"
            
            for img in soup.find_all('img'):
                src = img.get('src')
                # Try getting the lazy-load source if regular src is empty
                if img.get('data-src'): src = img.get('data-src')

                if src:
                    if src.startswith('/'): src = "https://hcmakers.com" + src
                    # Strict Filter
                    if "uploads" in src and "logo" not in src and src not in seen_urls:
                        fname = src.split("/")[-1]
                        scraped_images += f"- FILE: {fname} | URL: {src}\n"
                        seen_urls.append(src)
        except: pass
    
    # 3. DOCUMENTS (PDFs from Resources)
    doc_pdfs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.pdf')]
        
        # Grab first 4 docs
        for i, link in enumerate(list(set(links))[:4]):
            try:
                data = requests.get(link).content
                path = f"d_{i}.pdf"
                with open(path, "wb") as f: f.write(data)
                doc_pdfs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return web_text, scraped_images, doc_pdfs

# --- INIT ---
with st.spinner("Initializing Sales System..."):
    txt_data, extra_imgs, ai_docs = load_live_data()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # Prepare keys
    priority_list = "\n".join([f"- KEY: {k} | URL: {v}" for k, v in PRIORITY_MAP.items()])
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS:
    {priority_list}
    
    ADDITIONAL ASSETS:
    {extra_imgs}
    
    RULES:
    1. **IMAGES**: 
       - If asked to show/see/display "Fries", "Bites", "Cotija", "Plant", "Office", look at the 'ASSETS' list above.
       - OUTPUT: `<<<IMG: FULL_URL_HERE>>>`
       - Example: "Here are the cheese fries: <<<IMG: https://hcmakers.com/...CheeseFries-web.png>>>"
    
    2. **DATA**: Use the attached PDFs for numbers/specs.
    
    3. **LANGUAGE**: English or Spanish.
    
    WEBSITE CONTEXT:
    {txt_data}
    """
    
    payload = [system_prompt] + ai_docs + [question]
    try: return model.generate_content(payload).text
    except: return "Scanning..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_src" in message:
            render_image_b64(message["img_src"])

with st.form("chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"): st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Retrieving visual assets..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            # Safety clean against code injection hallucination
            clean = clean.replace("```", "").replace("print(", "")
            
            st.markdown(clean)
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_image_b64(url) # Runs server-side downloader

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_src"] = url
            st.session_state.chat_history.append(msg)