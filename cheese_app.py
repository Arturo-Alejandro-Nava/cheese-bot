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

# --- 1. ROBUST IMAGE RENDERER (The Fix) ---
def render_secure_image(url_or_path, caption):
    # Case A: Local PDF Screenshot
    if not url_or_path.startswith("http"):
        if os.path.exists(url_or_path):
            st.image(url_or_path, caption=caption, width=500)
        return

    # Case B: Website URL (Anti-Blocking Logic)
    try:
        # We assume headers to look like a real person visiting from the main site
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://hcmakers.com/" 
        }
        r = requests.get(url_or_path, headers=headers, timeout=5)
        
        if r.status_code == 200:
            st.image(r.content, caption=caption, width=500)
        else:
            # If blocked, provide a direct link instead of an error box
            st.markdown(f"**Image unavailable in chat.** [Click here to view image]({url_or_path})")
            
    except Exception as e:
        # If any crash occurs, just show the link
        st.markdown(f"**Image source:** [View Original]({url_or_path})")

# --- 2. OMNI-SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_comprehensive_data():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Factory images
        "https://hcmakers.com/contact-us/", 
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/about-us/"
    ]
    
    site_text = ""
    available_images = []
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Scrape URLs
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            clean_text = soup.get_text(" ", strip=True)[:4000]
            site_text += f"\nPAGE: {url}\nCONTENT: {clean_text}\n"
            
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('data-src') or img.get('src') 
                alt = img.get('alt', 'Image')
                
                if src:
                    if src.startswith('/'): src = "https://hcmakers.com" + src
                    # Filter junk
                    if any(x in src.lower() for x in ['logo', 'icon', 'svg', 'blank', 'facebook']): continue
                    if len(alt) < 3: alt = "Product or Facility Image"
                    
                    available_images.append(f"DESC: {alt} | URL: {src}")
        except: continue

    # 2. Hardcoded VIP Images (Only the guaranteed working ones)
    available_images.append("DESC: Cheese Plant Factory Facility Aerial View Building | URL: https://hcmakers.com/wp-content/uploads/2021/01/7777-1.jpg")
    available_images.append("DESC: Quality Lab Inside Facility | URL: https://hcmakers.com/wp-content/uploads/2020/12/Quality_Lab.jpg")
    # I REMOVED the "Stock Photo Office" line because that link is broken.
    
    return site_text, "\n".join(available_images)

# --- 3. DOCUMENT PREVIEWS ---
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
                    fname = link.get_text(strip=True) or href.split('/')[-1]
                except: continue
            elif href.endswith('.zip'):
                continue 

            if pdf_data:
                local_path = f"doc_{count}.pdf"
                with open(local_path, "wb") as f: f.write(pdf_data)
                
                remote = genai.upload_file(path=local_path, display_name=fname)
                ai_files.append(remote)
                
                try:
                    doc = fitz.open(local_path)
                    pix = doc[0].get_pixmap(dpi=150)
                    img_path = f"preview_{count}.png"
                    pix.save(img_path)
                    doc_images_list.append(f"DESC: PDF Document Preview of {fname} | URL: {img_path}")
                except: pass
                
                count += 1
        
        active_files = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE":
                    active_files.append(f)
                    break
                time.sleep(1)
                f = genai.get_file(f.name)
        return active_files, "\n".join(doc_images_list)

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
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    RESOURCES:
    1. **IMAGE LIBRARY (Below)**: List of valid image URLs found on the website.
    2. **WEBSITE TEXT**: Info about the company.
    
    RULES:
    1. **SHOWING IMAGES:** If the user asks for a picture (like "The Plant", "The Office", "Fresco"), SCAN the 'IMAGE LIBRARY'.
       - Output this tag if you find a match: `<<<IMG: URL_HERE>>>`
       - If you can't find a specific image (like 'office'), default to the 'Factory/Plant' image if relevant, or apologize.
       - NEVER invent a URL. Only use ones from the list.
       
    2. **OFFICE REQUESTS:** If they ask for the "Office," and you don't see an office image in the list, SHOW THE PLANT/FACTORY IMAGE and explain: "While I don't have a photo of the administrative office, here is our state-of-the-art facility in Kent, IL."
    
    3. **LANGUAGE:** English or Spanish.
    
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

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if "image_url" in message:
            render_secure_image(message["image_url"], "Reference")
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
            raw_text = get_smart_response(user_input)
            
            image_match = re.search(r"<<<IMG: (.*?)>>>", raw_text)
            clean_text = re.sub(r"<<<IMG: .*?>>>", "", raw_text).strip()
            
            if image_match:
                img_url = image_match.group(1)
                render_secure_image(img_url, "Found Result")
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text, "image_url": img_url})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": clean_text})
            
            st.markdown(clean_text)