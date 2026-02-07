import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import glob
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
            st.image(p, width=130); found = True; break
    if not found: st.write("🧀")

with col2:
    st.title("Hispanic Cheese Makers-Nuestro Queso")
st.markdown("---")

# --- 1. LIVE DATA SCRAPER (Text + VIDEOS) ---
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
    found_videos = []
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            content = r.content
            soup = BeautifulSoup(content, 'html.parser')
            
            # A. EXTRACT TEXT
            text = soup.get_text(" ", strip=True)[:4000]
            
            # B. EXTRACT VIDEO LINKS (IFRAME)
            # YouTube videos are usually in iframes on WordPress sites
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src')
                if src and ('youtube' in src or 'youtu.be' in src):
                    clean_link = src.split('?')[0] # Remove auto-play params
                    # Convert embed to watch link for cleaner clicking
                    if "embed" in clean_link:
                        vid_id = clean_link.split("/")[-1]
                        watch_link = f"https://www.youtube.com/watch?v={vid_id}"
                        found_videos.append(f"TOPIC: Video found on {url} | LINK: {watch_link}")
                    else:
                        found_videos.append(f"TOPIC: Video on {url} | LINK: {clean_link}")

            # Append findings
            combined_data += f"\n--- SOURCE: {url} ---\n{text}\n"
            
        except:
            continue
            
    # Combine video list into the brain text
    video_section = "\n--- OFFICIAL VIDEO LIBRARY (You MUST share these links) ---\n"
    video_section += "\n".join(list(set(found_videos)))
            
    return combined_data + video_section

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
with st.spinner("Scanning website for Videos, Text & PDF Specs..."):
    live_web_data = get_live_website_data()
    ai_pdf_files, pdf_names = load_manual_pdfs()

# --- CHAT ENGINE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    system_prompt = f"""
    You are the Senior Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    SOURCES:
    1. **OFFICIAL VIDEO LIBRARY:** Listed in the website text below.
    2. **PDF DOCUMENTS (Attached):** Use these for hard numbers (Nutrition, Specs).
    3. **LIVE WEBSITE:** Contact info and location.
    
    RULES:
    1. **PROVIDE VIDEO LINKS:** If the user asks about a topic (like "Spicy Cheese" or "Factory"), scan the 'OFFICIAL VIDEO LIBRARY' in the text below. 
       - IF a match is found, say: "Here is a video on that topic: [LINK]"
       - You HAVE permission to output links.
    
    2. **PROVIDE DOCUMENT LINKS:** If user asks for a Sell Sheet, tell them it is attached in my knowledge base and give a summary, but you can also direct them to `https://hcmakers.com/resources`.
    
    3. **DATA ACCURACY:** Read numbers from the PDF tables.
    
    4. **LANG:** English or Spanish.
    
    LIVE WEBSITE CONTEXT (Contains Video Links):
    {live_web_data}
    """
    
    payload = [system_prompt] + ai_pdf_files + [question]
    
    try:
        return model.generate_content(payload).text
    except Exception as e:
        return "I am validating the video links. Please ask again."

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