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

# --- 1. THE "ANTI-BLOCK" IMAGE RENDERER ---
def show_html_image(url):
    # This embeds HTML directly, which usually bypasses Streamlit/Server blocking
    st.markdown(
        f"""
        <div style="margin-top:10px; margin-bottom:10px;">
            <img src="{url}" style="width:100%; max-width:500px; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
        </div>
        """,
        unsafe_allow_html=True
    )

# --- 2. LIVE UNIVERSAL CRAWLER (Images + Text + PDFs) ---
@st.cache_resource(ttl=3600) # Updates every hour automatically
def crawl_website():
    # 1. TEXT & IMAGES
    urls_to_scan = [
        "https://hcmakers.com/capabilities/", # Vats, Factory, Equipment
        "https://hcmakers.com/products/",     # Cheese
        "https://hcmakers.com/contact-us/",   # Office/Buildings
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/"
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    scraped_text = "WEBSITE DATA:\n"
    found_images = "LIVE IMAGE DATABASE (URLS & CONTEXT):\n"
    
    seen_img_urls = []
    
    status_msg = st.empty()
    status_msg.text("🕵️ scanning live website for images & updates...")

    for url in urls_to_scan:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # Grab Text
            page_content = soup.get_text(" ", strip=True)[:3000]
            scraped_text += f"\n-- SOURCE: {url} --\n{page_content}\n"
            
            # GRAB ALL IMAGES (Even with weird names)
            imgs = soup.find_all('img')
            for img in imgs:
                # 1. Find URL (Check lazy load slots)
                src = img.get('data-src') or img.get('src') or img.get('data-lazy-src')
                if not src: continue
                
                # 2. Fix Relative Links
                if src.startswith("/"): src = "https://hcmakers.com" + src
                
                # 3. Clean Filter (No icons/logos/socials)
                if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'spacer', 'pixel', 'facebook', 'linkedin']):
                    continue
                if src in seen_img_urls: continue
                
                # 4. Context Capture
                # We grab the 'alt' text OR the parent text to help the AI know what this weird file is
                alt_txt = img.get('alt', 'No Description')
                parent_txt = img.find_parent().get_text().strip()[:50]
                
                found_images += f"- CONTEXT: {alt_txt} | FILE: {src.split('/')[-1]} | FULL_URL: {src}\n"
                seen_img_urls.append(src)
                
        except: continue
        
    # 2. DOCUMENT DOWNLOADER (Live from Zip)
    docs_ready = []
    doc_names = []
    try:
        r_res = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup_res = BeautifulSoup(r_res.content, 'html.parser')
        
        # Hunt for ZIP
        zip_link = next((a['href'] for a in soup_res.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_link:
            status_msg.text("📦 Unzipping live catalog...")
            z_data = requests.get(zip_link, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                count = 0
                for fname in z.namelist():
                    if fname.endswith(".pdf") and count < 6:
                        with open(f"temp_{count}.pdf", "wb") as f: f.write(z.read(fname))
                        docs_ready.append(genai.upload_file(f"temp_{count}.pdf", display_name=fname))
                        doc_names.append(fname)
                        count += 1
    except: pass
    
    status_msg.empty()
    return scraped_text, found_images, docs_ready, doc_names

# --- LOAD DATA ---
with st.spinner("Connecting to Live Server..."):
    web_txt, img_lib, pdf_files, doc_list = crawl_website()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    SOURCE MATERIAL:
    1. **LIVE IMAGE DATABASE (Below):** This is a list of ALL images found on the website right now. 
       - Some filenames are strange (e.g. 'Группа-масок-28'). 
       - YOU MUST MATCH the user's request to the 'CONTEXT' or best guess.
       - 'Closed Vat' might match 'Группа' files found on the 'Capabilities' page. Use context clues.
       - 'Fries' matches 'CheeseFries'.
       
    2. **DOCUMENTS (PDFs):** I have attached these. Use them for specs.
    3. **TEXT:** Website text for facts.
    
    RULES:
    - **IMAGES:** Return the URL of the best matching image using tag: `<<<IMG: URL_HERE>>>`.
    - **FALLBACK:** If the user asks for 'Office', find an image that looks corporate (e.g. 'display.jpg' or 'building').
    - **LANGUAGE:** English/Spanish.
    
    IMAGE DATABASE:
    {img_lib}
    
    WEBSITE CONTEXT:
    {web_txt}
    """
    
    payload = [system_prompt] + pdf_files + [question]
    try: return model.generate_content(payload).text
    except: return "Scanning live assets..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_src" in message:
            show_html_image(message["img_src"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask a question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Searching..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            # Image Tag Parser
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw)
            found_src = None
            
            if img_match:
                found_src = img_match.group(1).strip()
            
            st.markdown(clean)
            if found_src:
                show_html_image(found_src)

            msg = {"role": "assistant", "content": clean}
            if found_src: msg["img_src"] = found_src
            st.session_state.chat_history.append(msg)