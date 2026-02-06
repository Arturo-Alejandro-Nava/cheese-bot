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

# --- 1. SECURE IMAGE RENDERER ---
# This prevents broken images by downloading them on the server first
def render_secure_image(url_or_path, caption):
    if url_or_path.startswith("http"):
        try:
            # Fake browser headers to bypass security
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(url_or_path, headers=headers, timeout=3)
            if r.status_code == 200:
                st.image(r.content, caption=caption, width=500)
            else:
                st.warning(f"Image protected: {url_or_path}")
        except:
            st.write(f"Image Link: {url_or_path}")
    else:
        # It is a local file (PDF screenshot)
        if os.path.exists(url_or_path):
            st.image(url_or_path, caption=caption, width=500)

# --- 2. OMNI-SCRAPER (Text + All Images) ---
@st.cache_resource(ttl=3600) 
def get_comprehensive_data():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory/Plant
        "https://hcmakers.com/contact-us/", # Office/Map
        "https://hcmakers.com/quality/", # Lab/Certifications
        "https://hcmakers.com/about-us/"
    ]
    
    # We maintain two lists: One for text context, one for available images
    site_text = ""
    available_images = []
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Scrape the Website
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # TEXT
            clean_text = soup.get_text(" ", strip=True)[:4000]
            site_text += f"\nPAGE: {url}\nCONTENT: {clean_text}\n"
            
            # IMAGES
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('data-src') or img.get('src') # Check lazy load
                alt = img.get('alt', 'Image')
                
                if src:
                    if src.startswith('/'): src = "https://hcmakers.com" + src
                    # Filter junk
                    if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'blank', 'facebook']): continue
                    # Clean up Alt Text
                    if len(alt) < 3: alt = "Product or Facility Image"
                    
                    available_images.append(f"DESC: {alt} | URL: {src}")
                    
        except: continue

    # 2. Add Specific Hardcoded Images (Just to be safe for VIP items)
    available_images.append("DESC: Cheese Plant Factory Facility Aerial View | URL: https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg")
    available_images.append("DESC: Quality Lab Inside Facility | URL: https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg")
    available_images.append("DESC: Corporate Office Map or Building | URL: https://hcmakers.com/wp-content/uploads/2020/08/stock-photo-business-people.jpg") # Assuming standard stock usage if specific office photo is missing

    return site_text, "\n".join(available_images)

# --- 3. DOCUMENT PREVIEW GENERATOR ---
@st.cache_resource(ttl=3600)
def process_pdf_visuals():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    ai_files = [] # For reading
    doc_images_list = [] # For showing
    
    try:
        r = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        
        for link in links:
            if count >= 6: break
            href = link['href']
            
            # Identify Downloadable Content
            pdf_data = None
            fname = "Doc"
            
            if href.endswith('.pdf'):
                try: 
                    pdf_data = requests.get(href, headers=headers).content
                    fname = link.get_text(strip=True) or href.split('/')[-1]
                except: continue
            elif href.endswith('.zip'):
                # Extract logic (simplified)
                continue 

            if pdf_data:
                # Save locally for AI
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_data)
                
                # Upload to AI
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                
                # Snapshot Page 1 for Visual Display
                try:
                    doc = fitz.open(local_path)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_images_list.append(f"DESC: PDF Document Preview of {fname} | URL: {img_path}")
                except: pass
                
                count += 1
                
        # Wait for AI processing
        valid_ai_files = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE":
                    valid_ai_files.append(f)
                    break
                time.sleep(1)
                f = genai.get_file(f.name)
        return valid_ai_files, "\n".join(doc_images_list)

    except: return [], ""

# --- LOAD ---
with st.spinner("Indexing Site Media & Documents..."):
    site_text, site_images_text = get_comprehensive_data()
    ai_doc_files, doc_previews_text = process_pdf_visuals()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_smart_response(question):
    # SYSTEM PROMPT
    # We tell the AI to output a special tag [IMAGE: XYZ] if it finds a match
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    DATABASE:
    1. WEBSITE TEXT (Below): For facts.
    2. ATTACHED PDFS: Read these for specific numbers/specs.
    3. IMAGE LIBRARY (Below): A list of ALL available images (Web & PDF Previews).
    
    RULES:
    1. **IMAGE RETRIEVAL:** If the user asks to see something (e.g. "Show me the plant", "Image of fresco", "See the office", "Sell sheet"), 
       SCAN the "IMAGE LIBRARY". If you find a matching Description, start your response with:
       `<<<IMG: URL_HERE>>>`
       *(Only pick 1 best image match. If no good match, do not output the tag).*
       
    2. **OFFICE vs PLANT:** 
       - "Plant/Factory" = Manufacturing facility images.
       - "Office" = Corporate location images (Contact/People).
       - Do not mix them up.
       
    3. **DATA:** Use PDFs for nutrition numbers.
    4. **LANGUAGE:** English or Spanish.
    
    IMAGE LIBRARY:
    {site_images_text}
    {doc_previews_text}
    
    WEBSITE CONTEXT:
    {site_text}
    """
    
    payload = [system_prompt] + ai_doc_files + [question]
    
    try:
        response = model.generate_content(payload)
        return response.text
    except: return "Thinking..."

# --- UI RENDER ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        # Special Render: If previous message has an image path saved
        if "image_url" in message:
            render_secure_image(message["image_url"], "Reference Image")
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask question...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # User Msg
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # AI Msg
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            raw_text = get_smart_response(user_input)
            
            # PARSE THE IMAGE TAG
            # Look for <<<IMG: ...>>> pattern
            image_match = re.search(r"<<<IMG: (.*?)>>>", raw_text)
            
            clean_text = re.sub(r"<<<IMG: .*?>>>", "", raw_text).strip()
            
            if image_match:
                img_url = image_match.group(1)
                render_secure_image(img_url, "Result found")
                # Save to history with image
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text, "image_url": img_url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text})
            
            st.markdown(clean_text)