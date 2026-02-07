import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import glob

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
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LIVE WEBSITE SCRAPER (TEXT + VIDEOS) ---
@st.cache_resource(ttl=3600) 
def get_live_website_data():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/",
        "https://hcmakers.com/quality/", 
        "https://hcmakers.com/contact-us/",   
        "https://hcmakers.com/about-us/",
        "https://hcmakers.com/category-knowledge/" # Many videos here
    ]
    
    combined_data = "LIVE WEBSITE CONTENT:\n"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # A. EXTRACT TEXT
            text = soup.get_text(" ", strip=True)[:4000]
            
            # B. EXTRACT VIDEO LINKS (YouTube)
            video_links = []
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src')
                if src and ('youtube' in src or 'youtu.be' in src):
                    video_links.append(f"VIDEO FOUND: {src}")
            
            # Append findings
            combined_data += f"\n--- SOURCE: {url} ---\n"
            if video_links:
                combined_data += "VIDEOS ON PAGE:\n" + "\n".join(video_links) + "\n"
            combined_data += f"TEXT CONTENT:\n{text}\n"
            
        except:
            continue
            
    return combined_data

# --- 2. LOCAL PDF LOADER (Specs/Nutrition) ---
@st.cache_resource
def load_manual_pdfs():
    pdf_files = glob.glob("*.pdf")
    active_docs = []
    filenames = []

    if not pdf_files:
        return [], "No PDFs uploaded."

    for pdf in pdf_files:
        try:
            remote_file = genai.upload_file(path=pdf, display_name=pdf)
            while remote_file.state.name == "PROCESSING":
                time.sleep(1)
                remote_file = genai.get_file(remote_file.name)
            
            if remote_file.state.name == "ACTIVE":
                active_docs.append(remote_file)
                filenames.append(pdf)
        except: continue
            
    return active_docs, ", ".join(filenames)

# --- INITIAL LOAD ---
with st.spinner("Syncing Live Website Videos & Loading PDF Specs..."):
    live_web_data = get_live_website_data()
    ai_pdf_files, pdf_names = load_manual_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    SOURCES:
    1. **PDF DOCUMENTS (Attached):** Use these for hard numbers (Nutrition, Specs).
    2. **LIVE WEBSITE (Below):** Use this for general info and VIDEO LINKS.
    
    RULES:
    1. **PROVIDE VIDEO LINKS:** If the user asks about a topic (like "Spicy Cheese" or "Capabilities"), and there is a `VIDEO FOUND` link in the website text below, provide the URL.
       - Example: "You can see our spicy cheese trend report here: [YouTube Link]"
       - Make the link clickable.
    
    2. **NO IMAGES:** Do not show images directly. Text/Links only.
    
    3. **DATA ACCURACY:** Read numbers from the PDF tables.
    
    4. **LANG:** English or Spanish.
    
    LIVE WEBSITE DATA:
    {live_web_data}
    """
    
    payload = [system_prompt] + ai_pdf_files + [question]
    
    try:
        return model.generate_content(payload).text
    except Exception as e:
        return "I am reviewing the data. Please ask again."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about products, nutrition, or videos...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Consulting Website & Documents..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})