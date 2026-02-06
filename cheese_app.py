import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import fitz  # PyMuPDF (PDF-to-Image)

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

# --- HEADER (Logo + Title) ---
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

# --- 1. THE "OMNI-SCRAPER" (Text + ALL Images + Video Links) ---
@st.cache_resource(ttl=3600)
def get_comprehensive_website_data():
    # Pages to scan for images and text
    target_urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/",
        "https://hcmakers.com/capabilities/", # Factory images here
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/category-knowledge/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/about-us/"
    ]
    
    knowledge_base = ""
    # We create a massive list of every image URL found
    image_library = "\n--- 📸 WEBSITE IMAGE REPOSITORY ---\n"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    seen_images = []

    for url in target_urls:
        try:
            resp = requests.get(url, headers=headers)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 1. TEXT SCRAPING
            # Extract cleaned text
            page_text = soup.get_text(separator=' ', strip=True)
            knowledge_base += f"\nSOURCE PAGE: {url}\nTEXT: {page_text[:5000]}\n"
            
            # 2. IMAGE HUNTING
            images = soup.find_all('img', src=True)
            for img in images:
                src = img['src']
                alt = img.get('alt', 'No Description')
                
                # Fix relative URLs
                if src.startswith('/'): 
                    src = "https://hcmakers.com" + src
                
                # FILTER: Remove icons, spacers, pixels, and logos
                if any(x in src.lower() for x in ['.svg', 'icon', 'arrow', 'spacer', 'logo', 'facebook', 'linkedin']):
                    continue
                
                # Check for duplication
                if src not in seen_images:
                    image_library += f"IMAGE DESCRIPTION: {alt} | URL: {src}\n"
                    seen_images.append(src)

            # 3. YOUTUBE HUNTING
            iframes = soup.find_all('iframe', src=True)
            for iframe in iframes:
                if 'youtube' in iframe['src']:
                    image_library += f"VIDEO LINK: {iframe['src']}\n"

        except Exception as e:
            continue
            
    return knowledge_base, image_library

# --- 2. DEEP DOC & PREVIEW GENERATOR ---
@st.cache_resource(ttl=3600)
def process_live_documents():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    ai_files = [] # For the AI brain
    doc_previews = "\n--- 📄 DOCUMENT PREVIEWS (SELL SHEET IMAGES) ---\n"
    
    try:
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        limit = 8 # Read up to 8 documents
        
        for link in links:
            if count >= limit: break
            href = link['href']
            
            # Find Content
            pdf_bytes = None
            filename_label = "Document"
            
            try:
                # Direct PDF Link
                if href.endswith('.pdf'):
                    pdf_bytes = requests.get(href, headers=headers).content
                    filename_label = href.split("/")[-1]
                
                # Zipped PDF
                elif href.endswith('.zip'):
                    z_data = requests.get(href, headers=headers).content
                    with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                        for f in z.namelist():
                            if f.endswith('.pdf'):
                                pdf_bytes = z.read(f)
                                filename_label = f
                                break
            except: continue

            # If we found a PDF, process it
            if pdf_bytes:
                # A. Save locally for AI
                local_name = f"doc_{count}.pdf"
                with open(local_name, "wb") as f: f.write(pdf_bytes)
                
                # B. Upload to AI Brain
                remote = genai.upload_file(path=local_name, display_name=filename_label)
                ai_files.append(remote)
                
                # C. Generate Image Snapshot (Page 1)
                try:
                    doc = fitz.open(local_name)
                    page = doc.load_page(0) # Page 1
                    pix = page.get_pixmap(dpi=150)
                    img_filename = f"preview_{count}.png"
                    pix.save(img_filename)
                    
                    # Register this image for the AI
                    doc_previews += f"DOCUMENT NAME: {filename_label} | IMAGE_FILENAME: {img_filename}\n"
                except: pass
                
                count += 1
        
        # Wait for Files
        ready_files = []
        for f in ai_files:
            while f.state.name == "PROCESSING":
                time.sleep(1)
                f = genai.get_file(f.name)
            if f.state.name == "ACTIVE":
                ready_files.append(f)
                
        return ready_files, doc_previews

    except: return [], ""

# --- INITIAL LOAD ---
with st.spinner("Scraping Website Media & Downloading Sell Sheets..."):
    # This might take ~20 seconds but creates a massive library
    site_text, site_images = get_comprehensive_website_data()
    doc_files, doc_images = process_live_documents()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    
    # THE "MEDIA MANAGER" BRAIN
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    RESOURCES:
    1. **IMAGE REPOSITORY (Below)**: Contains links to images of products, the plant/facility, and logos.
    2. **DOCUMENT PREVIEWS (Below)**: Contains PNG images of the first page of our Sell Sheets (Nutrition/Specs).
    3. **PDF ATTACHMENTS**: Use these to read exact data/numbers.
    4. **WEBSITE TEXT**: Use for context.
    
    VISUAL RULES:
    1. **SHOWING WEBSITE IMAGES**: If the user asks to see the **plant**, **facility**, **factory**, **a specific cheese**, or **packaging**:
       - Scan the "IMAGE REPOSITORY" for the best match.
       - Use this format: `![Description](URL)`
       - *Example:* "Here is an image of our facility: \n ![Plant](https://...)"
    
    2. **SHOWING DOCUMENT IMAGES**: If the user asks to see a **sell sheet**, **specs**, or **document**:
       - Use the `IMAGE_FILENAME` from the "DOCUMENT PREVIEWS" list.
       - Use this format: `![Sell Sheet](preview_0.png)`
    
    3. **NO HALLUCINATIONS**: Do NOT invent URLs. If no image matches, reply with text only.
    
    4. **VIDEOS**: Provide YouTube links if relevant (spicy cheese trends).
    
    {site_images}
    
    {doc_images}
    
    {site_text}
    """
    
    content_payload = [system_prompt] + doc_files + [question]
    
    try:
        response = model.generate_content(content_payload)
        return response.text
    except Exception as e:
        return "Calibrating visual assets. Please try asking again."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about cheese, nutrition, or ask for images/sell sheets...")
    submit = st.form_submit_button("Ask Agent")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Finding visuals..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})