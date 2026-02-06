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
from urllib.parse import urljoin, unquote

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
    possible_names = ["logo", "logo.jpg", "logo.png", "logo.jpeg"]
    for name in possible_names:
        if os.path.exists(name):
            st.image(name, width=130)
            break
    else:
        st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

st.markdown("---")

# --- 1. ROBUST IMAGE RENDERER ---
def render_secure_image(url_or_path, caption):
    if not url_or_path.startswith("http"):
        if os.path.exists(url_or_path):
            st.image(url_or_path, caption=caption, width=500)
        return

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }
        r = requests.get(url_or_path, headers=headers, timeout=5)
        if r.status_code == 200:
            st.image(r.content, caption=caption, width=500)
        else:
            st.markdown(f"**Image Found:** [Click to View]({url_or_path})")
    except:
        st.markdown(f"**Image Link:** [View Original]({url_or_path})")

# --- 2. THE INTELLIGENT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_comprehensive_data():
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/", # We will scrape aggressively here
        "https://hcmakers.com/capabilities/", 
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/about-us/"
    ]
    
    site_text = ""
    # Hardcoded Fallbacks (Guaranteed to work if site structure changes)
    available_images = [
        "DESC: Manufacturing Plant / Factory | URL: https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg",
        "DESC: Corporate Office / Headquarters | URL: https://hcmakers.com/wp-content/uploads/2020/08/display.jpg",
        "DESC: Quality Lab | URL: https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg"
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    seen_urls = []

    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # A. TEXT
            clean_text = soup.get_text(" ", strip=True)[:5000]
            site_text += f"\nPAGE: {url}\nCONTENT: {clean_text}\n"
            
            # B. INTELLIGENT IMAGE EXTRACTION
            imgs = soup.find_all('img')
            for img in imgs:
                # Get URL
                src = img.get('data-src') or img.get('src')
                if not src: continue
                
                # Make absolute URL
                src = urljoin("https://hcmakers.com", src)
                
                if src in seen_urls: continue
                
                # Check FILENAME for clues (Crucial for "Bites")
                filename_keywords = src.split('/')[-1].replace('-', ' ').replace('_', ' ').lower()
                
                # Get Alt Text
                alt = img.get('alt', '').strip()
                
                # Combined Clues
                description_clues = f"{alt} {filename_keywords}"
                
                # Filter Logic (Less Strict on Products Page)
                is_product_page = "products" in url
                is_junk = any(x in description_clues for x in ['logo', 'icon', 'svg', 'spacer', 'facebook', 'twitter'])
                
                if not is_junk:
                    # If on product page, assume ANY image might be a product
                    if is_product_page and ('bites' in description_clues or 'pkg' in description_clues or 'fresco' in description_clues or 'queso' in description_clues):
                        available_images.append(f"DESC: {description_clues} | URL: {src}")
                        seen_urls.append(src)
                    
                    # For other pages, keep "Quality" images
                    elif "upload" in src and len(src) > 50:
                        available_images.append(f"DESC: {description_clues} | URL: {src}")
                        seen_urls.append(src)

        except: continue

    return site_text, "\n".join(available_images)

# --- 3. DOCUMENT PROCESSOR ---
@st.cache_resource(ttl=3600)
def process_pdf_visuals():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    doc_images_list = []
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            if count >= 6: break
            href = link['href']
            
            pdf_data = None
            fname = "Doc"
            
            if href.endswith('.pdf'):
                try: 
                    pdf_data = requests.get(href, headers=headers).content
                    fname = href.split('/')[-1]
                except: continue
            elif href.endswith('.zip'):
                continue

            if pdf_data:
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_data)
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                
                # Generate Document Preview
                try:
                    doc = fitz.open(local_path)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_images_list.append(f"DESC: PDF SELL SHEET {fname} | FILE_PATH: {img_path}")
                except: pass
                count += 1
        
        active = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE": active.append(f)
                time.sleep(1)
                f = genai.get_file(f.name)
        return active, "\n".join(doc_images_list)
    except: return [], ""

# --- LOAD DATA ---
with st.spinner("Analyzing Catalog Files & Website Images..."):
    site_text, site_images_text = get_comprehensive_data()
    ai_doc_files, doc_previews_text = process_pdf_visuals()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_smart_response(question):
    
    system_prompt = f"""
    You are the Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSET LIBRARY:
    {site_images_text}
    {doc_previews_text}
    
    RULES:
    1. **IMAGE FINDING:** You must hunt for images in the "ASSET LIBRARY".
       - Read the "DESC" (Description) fields carefully.
       - Use "Fuzzy Matching". If user asks for "Bites" and you see "DESC: oaxaca bites pkg image", USE IT.
       - Look for filenames. 'oaxaca-bites.png' matches "Oaxaca Bites".
       - **Output:** `<<<IMG: URL_OR_FILE_PATH>>>`
    
    2. **PLANT vs OFFICE:**
       - Plant/Factory: Use the Plant aerial image from library.
       - Office: Use the 'Corporate Office / Headquarters' link in the library.
    
    3. **DATA:** Use PDFs for specific nutrition numbers.
    """
    
    payload = [system_prompt] + ai_doc_files + [question]
    
    try:
        response = model.generate_content(payload)
        return response.text
    except: return "Checking visual assets..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "image_url" in message:
            render_secure_image(message["image_url"], "Found")
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Scanning..."):
            raw_text = get_smart_response(user_input)
            
            img_match = re.search(r"<<<IMG: (.*?)>>>", raw_text)
            clean_text = re.sub(r"<<<IMG: .*?>>>", "", raw_text).strip()
            
            if img_match:
                img_url = img_match.group(1)
                render_secure_image(img_url, "Found Result")
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text, "image_url": img_url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text})
            
            st.markdown(clean_text)