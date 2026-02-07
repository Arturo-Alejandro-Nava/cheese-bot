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

# --- 1. RENDERER (Anti-Block) ---
def render_image(url):
    if not url: return
    # Use HTML injection to force the browser to load it
    st.markdown(
        f"""
        <div style="margin: 10px 0;">
            <img src="{url}" referrerpolicy="no-referrer" 
                 style="width: 100%; max-width: 500px; border-radius: 8px; border: 1px solid #ccc; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. THE MASTER URL LIST (The "Once and For All" Fix) ---
# I have mapped the specific filenames for EVERY product so the bot can't miss them.
ASSET_MAP = {
    # SNACKS & SIDES
    "CHEESE FRIES": "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png",
    "OAXACA BITES": "https://hcmakers.com/wp-content/uploads/2021/01/OaxacaBites-web.png",
    
    # CHEESES (Frescos)
    "FRESCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png",
    "BLANCO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Blanco_Square_10oz_cp.png",
    "PANELA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    "PANELA ROUND": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Panela_Bar_8oz_v2.png",
    
    # CHEESES (Melting/Aged)
    "OAXACA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png",
    "COTIJA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png",
    "QUESADILLA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Quesadilla-Shred_2lb.png",
    "MANCHEGO": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Manchego_6oz.png",
    
    # CREAMS (Cremas)
    # The file name is 'Mexicana_Tub' but we map it to 'CREMA' queries
    "CREMA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "CREMA MEXICANA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Mexicana_Tub_16oz.png",
    "CREMA SALVADORENA": "https://hcmakers.com/wp-content/uploads/2020/12/YBH_CremaSal_14oz_bag.png",
    
    # FACILITIES
    "PLANT": "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg",
    "FACTORY": "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
    "LAB": "https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg",
    "OFFICE": "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg"
}

# --- 3. LIVE SCRAPER (Backup) ---
@st.cache_resource(ttl=3600) 
def get_website_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    web_text = "WEBSITE DATA:\n"
    scraped_urls = {}
    
    # 1. Text Scraper
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]
    for u in urls:
        try:
            r = requests.get(u, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += soup.get_text(" ", strip=True)[:4000] + "\n"
            
            # Scrape Images while we are here (Dynamic backup)
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and "uploads" in src and "logo" not in src:
                    if src.startswith("/"): src = "https://hcmakers.com" + src
                    name = src.split("/")[-1].lower()
                    scraped_urls[name] = src
        except: pass

    # 2. PDF Fetcher
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        links = [a['href'] for a in BeautifulSoup(r.content, 'html.parser').find_all('a', href=True) if a['href'].endswith('.pdf')]
        for i, link in enumerate(list(set(links))[:4]): 
            try:
                b = requests.get(link, headers=headers).content
                path = f"doc_{i}.pdf"
                with open(path, "wb") as f: f.write(b)
                pdf_docs.append(genai.upload_file(path))
            except: continue
    except: pass
    
    return web_text, scraped_urls, pdf_docs

# --- LOAD ---
with st.spinner("Connecting to Live Data..."):
    txt_data, scraped_img_dict, ai_files = get_website_data()

# --- SEARCH LOGIC (Python Logic, not AI Hallucination) ---
def find_image_url(query):
    query = query.lower()
    
    # 1. Check Hardcoded Priority Map
    for key, url in ASSET_MAP.items():
        if key.lower() in query:
            return url
            
    # 2. Check "Partial Matches" in Priority Map
    # e.g. "Mexicana" matches "CREMA MEXICANA"
    for key, url in ASSET_MAP.items():
        words = key.lower().split()
        if all(word in query for word in words):
             return url

    # 3. Check Scraped Live Images (Backup)
    # Search for filename keywords (e.g. "tub" inside "mexicana_tub.png")
    query_parts = query.replace("image", "").replace("picture", "").replace("of", "").split()
    for name, url in scraped_img_dict.items():
        if any(part in name for part in query_parts if len(part) > 3):
            return url

    return None

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    asset_list_str = "\n".join([f"- {k}" for k in ASSET_MAP.keys()])
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    ASSET KEYS (Images Available):
    {asset_list_str}
    
    RULES:
    1. **IMAGES**: If user asks for an image, look at the ASSET KEYS.
       - OUTPUT: `<<<IMG: KEY_NAME>>>`
       - Example: "Show me Crema" -> `<<<IMG: CREMA>>>`
       - Example: "Show Office" -> `<<<IMG: OFFICE>>>`
       - **If you are unsure, just guess the best Keyword.** My python code will handle the fuzzy matching.
    
    2. **DATA**: Use Attached PDFs for specs.
    3. **LANG**: English or Spanish.
    
    WEBSITE CONTEXT:
    {txt_data}
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
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Finding image..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            st.markdown(clean)
            
            # --- FINAL FALLBACK LOGIC ---
            # Even if AI fails to give a tag, we search for the image using Python
            # This makes "Crema Mexicana" work even if AI messes up.
            img_tag = re.search(r"<<<IMG: (.*?)>>>", raw)
            found_url = None
            
            if img_tag:
                key = img_tag.group(1).strip()
                # Lookup in map
                found_url = ASSET_MAP.get(key.upper()) or find_image_url(key)
            else:
                # If user asked for "Show me", trigger python search anyway
                if "show" in user_input.lower() or "image" in user_input.lower() or "picture" in user_input.lower():
                    found_url = find_image_url(user_input)

            if found_url:
                render_image(found_url)
                msg = {"role": "assistant", "content": clean, "img_url": found_url}
            else:
                msg = {"role": "assistant", "content": clean}

            st.session_state.chat_history.append(msg)