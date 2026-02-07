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
    # Logic to find logo
    possible_names = ["logo.jpg", "logo.png", "logo.jpeg", "logo"]
    found = False
    for p in possible_names:
        if os.path.exists(p):
            st.image(p, width=130); found=True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. THE ANTI-BLOCK IMAGE RENDERER ---
# This bypasses the security blocking by using HTML injection
def render_live_image(url):
    if not url: return
    
    # We strip URL parameters to make it cleaner
    clean_url = url.split('?')[0]
    
    # This HTML tag acts like a regular browser visiting the site directly.
    # 'referrerpolicy' is the secret weapon against 403 Forbidden errors.
    html = f"""
    <div style="margin: 10px 0; text-align: left;">
        <img src="{clean_url}" 
             referrerpolicy="no-referrer"
             style="max-width: 500px; width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- 2. LIVE UNIVERSAL CRAWLER ---
@st.cache_resource(ttl=3600)
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # We explicitly define the target pages
    target_pages = {
        "CONTACT_PAGE (Look for Office/HQ here)": "https://hcmakers.com/contact-us/",
        "CAPABILITIES (Look for Plant/Factory here)": "https://hcmakers.com/capabilities/",
        "PRODUCTS (Look for Cheese/Packages here)": "https://hcmakers.com/products/",
        "QUALITY": "https://hcmakers.com/quality/",
        "HOME": "https://hcmakers.com/"
    }

    website_context = "WEBSITE DATA:\n"
    image_catalog = "DETECTED LIVE IMAGES:\n"
    
    seen_urls = []

    # 1. SPECIAL "GUARANTEED" LIST (In case scraping fails)
    # These are verified live links.
    vip_images = [
        "https://hcmakers.com/wp-content/uploads/2020/08/display.jpg (OFFICE / BUILDING)",
        "https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg (PLANT AERIAL)",
        "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg (FACTORY INSIDE)",
        "https://hcmakers.com/wp-content/uploads/2021/01/CheeseFries-web.png (CHEESE FRIES)",
        "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_wedge_10oz_cp.png (COTIJA)"
    ]
    for vip in vip_images:
        image_catalog += f"VIP ASSET: {vip}\n"

    # 2. RUN THE SCRAPER
    for label, url in target_pages.items():
        try:
            r = requests.get(url, headers=headers)
            content = r.content.decode("utf-8", errors="ignore")
            
            # A. Get Text
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text(" ", strip=True)[:3000]
            website_context += f"\nSOURCE: {label}\nTEXT: {text}\n"
            
            # B. Get Images using Regex (Catches hidden ones too)
            # Looks for any http...jpg/png string
            raw_img_urls = re.findall(r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|webp)', content)
            
            for img_url in raw_img_urls:
                if img_url in seen_urls: continue
                
                # Filter bad results
                clean_url = img_url.split('?')[0]
                lower = clean_url.lower()
                
                if any(x in lower for x in ['logo', 'icon', 'svg', 'spacer', 'blank', 'facebook', 'twitter']):
                    continue
                if "uploads" not in lower: 
                    continue # Strict filter for content images only
                
                seen_urls.append(clean_url)
                
                # Clean Filename for AI Understanding
                fname = clean_url.split('/')[-1]
                
                image_catalog += f"FOUND ON {label}: {clean_url} (File: {fname})\n"
                
        except: continue
        
    # 3. PDFS
    pdf_docs = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            if link['href'].endswith('.pdf') and count < 5:
                try:
                    pdf_data = requests.get(link['href']).content
                    with open(f"doc_{count}.pdf", "wb") as f: f.write(pdf_data)
                    pdf_docs.append(genai.upload_file(f"doc_{count}.pdf"))
                    count += 1
                except: continue
    except: pass

    return website_context, image_catalog, pdf_docs

# --- LOAD ---
with st.spinner("Live Scraping hcmakers.com (Images, Text, Docs)..."):
    txt_data, img_db, ai_files = get_live_data()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    system_prompt = f"""
    You are the Sales AI for Nuestro Queso.
    
    INTELLIGENCE:
    1. **LIVE IMAGE DB (Below):** A list of all images currently found on the website.
       - Each image has a "FOUND ON [Page Name]" label.
       - Use this context! If user asks for "Office", look for images found on "CONTACT_PAGE" or with filename "display".
       - If user asks for "Plant", look for images on "CAPABILITIES".
    2. **DOCS:** Attached PDFs.
    3. **TEXT:** General knowledge.
    
    RULES:
    1. **DISPLAYING IMAGES:** Return the URL tag: `<<<IMG: URL_HERE>>>`.
       - DO NOT invent URLs. Only use the exact strings from the DB.
    
    2. **OFFICE vs PLANT:**
       - Office = The Headquarters. Often found on Contact Page. (Likely 'display.jpg').
       - Plant = Factory. (Likely '7777-1' or 'PLANT').
    
    3. **LANGUAGE:** English or Spanish.
    
    LIVE IMAGE DATABASE:
    {img_db}
    
    WEBSITE CONTEXT:
    {txt_data}
    """
    
    payload = [system_prompt] + ai_files + [question]
    try: return model.generate_content(payload).text
    except: return "Loading..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "img_url" in message:
            render_live_image(message["img_url"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about products, see the office, see the plant...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Checking live site..."):
            raw = get_answer(user_input)
            
            clean = re.sub(r"<<<IMG: .*?>>>", "", raw).strip()
            
            st.markdown(clean)
            
            url = None
            match = re.search(r"<<<IMG: (.*?)>>>", raw)
            if match:
                url = match.group(1).strip()
                render_live_image(url)

            msg = {"role": "assistant", "content": clean}
            if url: msg["img_url"] = url
            st.session_state.chat_history.append(msg)