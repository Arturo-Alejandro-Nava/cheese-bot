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

# --- 1. RENDERER (Force Browser to Load Image) ---
def show_html_image(url):
    st.markdown(
        f"""
        <div style="margin: 10px 0;">
            <img src="{url}" style="width:100%; max-width:500px; border-radius:10px; border: 1px solid #ddd;">
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. PRIORITY ASSET MAP (The "Anti-Error" Fix) ---
# We force the AI to use these specific URLs for main products.
# This prevents it from showing a "Gold Medal" instead of the Cheese.
PRIORITY_IMAGES = {
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "OAXACA BALL": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "QUESADILLA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "PLANT / FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY INSIDE": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg"
}

# --- 3. LIVE SCRAPER (Backup for everything else) ---
@st.cache_resource(ttl=3600)
def crawl_website():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # TEXT
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/capabilities/", "https://hcmakers.com/quality/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/about-us/"]
    web_text = "WEBSITE DATA:\n"
    scraped_images = "ADDITIONAL IMAGES (Backup):\n"
    
    seen = []
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\nPAGE: {url}\n{soup.get_text(' ', strip=True)[:4000]}\n"
            
            for img in soup.find_all('img'):
                src = img.get('data-src') or img.get('src')
                if not src: continue
                if src.startswith("/"): src = "https://hcmakers.com" + src
                if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'facebook', 'twitter']): continue
                
                if src not in seen:
                    fname = src.split("/")[-1]
                    scraped_images += f"FILE: {fname} | URL: {src}\n"
                    seen.append(src)
        except: continue

    # DOCUMENTS (Live Zip/PDF Extraction)
    live_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        zip_url = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        if zip_url:
            z_data = requests.get(zip_url, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                i = 0
                for fn in z.namelist():
                    if fn.lower().endswith(".pdf") and i < 6:
                        with open(f"t_{i}.pdf", "wb") as f: f.write(z.read(fn))
                        live_docs.append(genai.upload_file(f"t_{i}.pdf", display_name=fn))
                        i+=1
    except: pass

    return web_text, scraped_images, live_docs

# --- LOAD ---
with st.spinner("Connecting to Live Data Stream..."):
    web_txt, scrap_img, ai_pdfs = crawl_website()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    # Construct Priority List for Prompt
    priority_list = "PRIORITY IMAGES (ALWAYS CHECK HERE FIRST):\n"
    for k, v in PRIORITY_IMAGES.items():
        priority_list += f"- {k}: {v}\n"
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    IMAGE RULES:
    1. **PRIORITY CHECK:** If user asks for Cotija, Fresco, Plant, or anything in the 'PRIORITY IMAGES' list, you **MUST** use that exact URL. Do not look anywhere else.
       - *Example:* "Here is the Cotija: <<<IMG: {PRIORITY_IMAGES['COTIJA']}>>>"
       
    2. **BACKUP SEARCH:** Only look at the 'ADDITIONAL IMAGES' list if the item is NOT in the priority list.
       - Do **NOT** use images of medals, awards, or icons when the user asks for a Product.
    
    3. **OUTPUT FORMAT:** `<<<IMG: URL_HERE>>>`
    
    DATA RULES:
    - Use the attached PDFs for Nutrition Facts (Protein/Fat/Size).
    
    {priority_list}
    {scrap_img}
    
    WEBSITE CONTEXT:
    {web_txt}
    """
    
    payload = [system_prompt] + ai_pdfs + [question]
    try: return model.generate_content(payload).text
    except: return "Scanning..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_url" in message:
            show_html_image(message["img_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            
            st.markdown(clean)
            
            found_url = None
            if img_match:
                found_url = img_match.group(1).strip()
                show_html_image(found_url)
                
            msg = {"role": "assistant", "content": clean}
            if found_url: msg["img_url"] = found_url
            st.session_state.chat_history.append(msg)