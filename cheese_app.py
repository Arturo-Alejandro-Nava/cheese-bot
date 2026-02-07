import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import fitz  # PyMuPDF
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
            st.image(p, width=130)
            found = True
            break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. PROXY IMAGE RENDERER (The Anti-Block Fix) ---
def render_proxy_image(url, caption="Image"):
    """
    Downloads the image on the server (Python) acting as a real user,
    then feeds the bytes to Streamlit. This Bypasses Hotlink Protection.
    """
    try:
        # Headers mimicking a real Chrome Browser to trick the website
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://hcmakers.com/",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        # Download the RAW BYTES
        r = requests.get(url, headers=headers, timeout=5, stream=True)
        
        if r.status_code == 200:
            # Display the bytes directly. The website thinks a human downloaded it.
            st.image(r.content, caption=caption, width=500)
        else:
            st.warning(f"Image Locked by Source. [Click here to view]({url})")
            
    except Exception as e:
        # Fallback text link
        st.markdown(f"**View Image:** [Click Here]({url})")

# --- 2. MASTER ASSET LIBRARY ---
# I manually verified these links. The Proxy Method needs EXACT links.
ASSET_MAP = {
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_quarter_5lb.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Cryovac_5lb.png"
}

# --- 3. SCRAPERS & DOCS ---
@st.cache_resource(ttl=3600) 
def get_knowledge_base():
    # WEB TEXT
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/"]
    web_text = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            web_text += s.get_text(" ", strip=True)[:3000]
        except: continue

    # PDFS
    ai_files = []
    doc_text = "\nPDF FILES FOR VISUAL PREVIEW (Internal Names):\n"
    
    # We grab 3 documents live
    try:
        r = requests.get("https://hcmakers.com/resources/", headers={"User-Agent": "Mozilla/5.0"})
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True)]
        
        count = 0
        for link in links:
            if count > 4: break
            if link.endswith(".pdf"):
                try:
                    pdf_bytes = requests.get(link).content
                    path = f"doc_{count}.pdf"
                    with open(path, "wb") as f: f.write(pdf_bytes)
                    remote = genai.upload_file(path=path)
                    ai_files.append(remote)
                    
                    # Generate Preview Image
                    doc = fitz.open(path)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_text += f"- Sell Sheet {count}: saved as {img_path}\n"
                    
                    count += 1
                except: continue
                
        # Wait for AI files
        ready = []
        for f in ai_files:
            while f.state.name == "PROCESSING": time.sleep(1); f=genai.get_file(f.name)
            ready.append(f)
        
        return web_text, doc_text, ready
    except: return web_text, "", []

# --- INITIAL LOAD ---
with st.spinner("Downloading Assets..."):
    web_txt, doc_map, ai_files = get_knowledge_base()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # Construct Image List for Brain
    img_prompt = "IMAGE LIBRARY (You MUST use these keys):\n"
    for key in ASSET_MAP.keys():
        img_prompt += f"- {key}\n"

    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSETS:
    {img_prompt}
    
    DOCUMENTS:
    {doc_map}
    
    RULES:
    1. **IMAGES**: If asked for an image (Fries, Bites, Plant, Office), find the matching Key in 'IMAGE LIBRARY'.
       - OUTPUT: `<<<IMG: KEY_NAME>>>` (e.g. `<<<IMG: CHEESE FRIES>>>`)
       - Do not put the URL. Put the KEY NAME.
    
    2. **SELL SHEETS**: If asked for document visual, output: `<<<IMG: preview_X.png>>>`
    
    3. **DATA**: Use PDFs for numbers.
    """
    payload = [system_prompt] + ai_files + [question]
    try: return model.generate_content(payload).text
    except: return "Thinking..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "image_url" in message:
            # Special Check: Is it a Web URL or Local File?
            target = message["image_url"]
            if target.startswith("http"):
                render_proxy_image(target, "Reference")
            else:
                st.image(target, width=500)
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            raw = get_answer(user_input)
            
            # Extract Image Key
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            saved_img_path = None
            
            if img_match:
                key_or_path = img_match.group(1).strip()
                
                # Check if it's a Preset Key
                if key_or_path in ASSET_MAP:
                    real_url = ASSET_MAP[key_or_path]
                    render_proxy_image(real_url, key_or_path)
                    saved_img_path = real_url
                # Check if it's a Local PDF Preview
                elif "preview_" in key_or_path:
                    st.image(key_or_path, width=500)
                    saved_img_path = key_or_path
                else:
                    st.write("") # Fail silent
            
            st.markdown(clean)
            
            msg_data = {"role": "assistant", "content": clean}
            if saved_img_path: msg_data["image_url"] = saved_img_path
            
            st.session_state.chat_history.append(msg_data)