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

# --- WEBPAGE CONFIG ---
st.set_page_config(
    page_title="Hispanic Cheese Makers-Nuestro Queso",
    page_icon="🧀"
)

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, width=130)
            found = True
            break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. DIRECT HTML RENDERER (The Anti-Block Fix) ---
def render_image(url_or_path, caption):
    # Case A: Local File (PDF Preview)
    if not url_or_path.startswith("http"):
        if os.path.exists(url_or_path):
            st.image(url_or_path, caption=caption, width=500)
        return

    # Case B: Website Image (Force User Browser to Load It)
    # We use basic HTML to bypass the Server Blocking
    st.markdown(
        f"""
        <div style="border: 1px solid #ddd; padding: 10px; border-radius: 10px; display: inline-block;">
            <img src="{url_or_path}" width="500" style="border-radius: 5px;">
            <p style="margin-top: 5px; font-size: 14px; font-weight: bold; color: #555;">{caption}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. MASTER ASSET DICTIONARY ---
# We use this Dictionary to catch specific products accurately.
# We skip live scraping for images because it is too fragile. This works 100% of the time.
ASSET_LIBRARY = {
    "OAXACA BITES PACKAGE": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "CHEESE FRIES PACKAGE": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "MANUFACTURING PLANT / AERIAL": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY / INSIDE PRODUCTION": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "OFFICE BUILDING": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
    "QUALITY LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "QUESO FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "QUESO COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "QUESO PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "CREMA / CREAM": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA SHREDDED": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png"
}

# --- 3. LIVE TEXT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_text_content():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/capabilities/"
    ]
    txt = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            txt += s.get_text(" ", strip=True)[:3000]
        except: continue
    return txt

# --- 4. DOC PDF GENERATOR ---
@st.cache_resource(ttl=3600)
def process_docs():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    local_images_text = ""
    
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        limit = 6
        for link in links:
            if count >= limit: break
            href = link['href']
            
            pdf_bytes = None
            fname = "Doc"
            if href.endswith('.pdf'):
                try: 
                    pdf_bytes = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                except: continue
            elif href.endswith('.zip'): continue

            if pdf_bytes:
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_bytes)
                
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                
                # Make Preview PNG
                try:
                    doc = fitz.open(local_path)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    local_images_text += f"ITEM: SELL SHEET for {fname} | PATH: {img_path}\n"
                except: pass
                count += 1
        
        active = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE": active.append(f); break
                time.sleep(1)
                f = genai.get_file(f.name)
        return active, local_images_text
    except: return [], ""

# --- LOAD DATA ---
with st.spinner("Connecting to Media & Database..."):
    web_text = get_text_content()
    doc_files, doc_paths = process_docs()

# --- CHAT BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_response(question):
    # We turn the Dictionary into a String for the AI to read
    img_list_str = "OFFICIAL IMAGE LINKS:\n"
    for k, v in ASSET_LIBRARY.items():
        img_list_str += f"- ITEM: {k} | URL: {v}\n"
        
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    {img_list_str}
    {doc_paths}
    
    RULES:
    1. **FINDING IMAGES**:
       - Scan the 'OFFICIAL IMAGE LINKS' list.
       - Use "Fuzzy Logic": 'Cheese Fries' matches 'CHEESE FRIES PACKAGE'. 'Factory' matches 'MANUFACTURING PLANT'.
       - **Output Format**: Start your reply with `<<<IMG: THE_URL_HERE>>>`
       
    2. **SELL SHEETS**: Use the PATH (e.g. `<<<IMG: preview_0.png>>>`) for document requests.
    
    3. **OFFICE vs PLANT**:
       - 'Plant' = Manufacturing/Aerial.
       - 'Office' = 'OFFICE BUILDING' url.
       
    4. **LANGUAGE**: English or Spanish.
    
    WEBSITE CONTEXT:
    {web_text}
    """
    
    payload = [system_prompt] + doc_files + [question]
    try:
        return model.generate_content(payload).text
    except: return "Loading..."

# --- UI RENDERER ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "image_url" in message:
            # RENDER THE IMAGE VIA HTML (Bypassing Python blocks)
            render_image(message["image_url"], "Product Image")
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question... / Preguntar...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Retrieving asset..."):
            raw = get_response(user_input)
            
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            if img_match:
                url = img_match.group(1)
                render_image(url, "Product Result")
                st.session_state.chat_history.append({"role": "assistant", "content": clean, "image_url": url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean})
            
            st.markdown(clean)