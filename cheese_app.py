import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io
import fitz  # PyMuPDF

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found.")
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

# --- 1. BYPASS IMAGE LOADER (The Fix) ---
# We force-download the image so the browser doesn't get blocked by security
def show_secure_image(url, caption):
    try:
        # User Agent makes us look like a real browser (not a bot)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            st.image(resp.content, caption=caption, width=600)
        else:
            st.error(f"Image blocked by website security (Status {resp.status_code})")
    except:
        st.write(f"Image available at: {url}")

# --- 2. LIVE ASSETS ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/", 
        "https://hcmakers.com/products/", 
        "https://hcmakers.com/capabilities/", # Plant info here
        "https://hcmakers.com/contact-us/"
    ]
    txt = "WEBSITE DATA:\n"
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"})
            s = BeautifulSoup(r.content, 'html.parser')
            txt += s.get_text(" ", strip=True)[:3000]
        except: continue
    return txt

@st.cache_resource(ttl=3600)
def process_documents():
    target_url = "https://hcmakers.com/resources/"
    headers = {"User-Agent": "Mozilla/5.0"}
    ai_files = []
    
    try:
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        
        for link in links:
            if count >= 6: break
            href = link['href']
            pdf_bytes = None
            
            try:
                if href.endswith('.pdf'):
                    pdf_bytes = requests.get(href, headers=headers).content
                    name = href.split("/")[-1]
                elif href.endswith('.zip'):
                    z = requests.get(href, headers=headers).content
                    with zipfile.ZipFile(io.BytesIO(z)) as zf:
                        for f in zf.namelist():
                            if f.endswith('.pdf'):
                                pdf_bytes = zf.read(f)
                                name = f
                                break
            except: continue

            if pdf_bytes:
                local_name = f"doc_{count}.pdf"
                with open(local_name, "wb") as f: f.write(pdf_bytes)
                remote = genai.upload_file(path=local_name, display_name=f"Doc_{count}")
                ai_files.append(remote)
                count += 1
                
        # Wait loop
        active = []
        for f in ai_files:
            for _ in range(10):
                if f.state.name == "ACTIVE":
                    active.append(f)
                    break
                time.sleep(1)
                f = genai.get_file(f.name)
        return active
    except: return []

# --- LOAD DATA ---
with st.spinner("Connecting to secure database..."):
    web_text = get_website_text()
    live_docs = process_documents()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    # SYSTEM PROMPT
    system_prompt = f"""
    You are the Senior Product Specialist for "Hispanic Cheese Makers-Nuestro Queso".
    
    ASSETS:
    1. ATTACHED DOCS: Sell sheets with specs.
    2. WEBSITE TEXT: Below.
    
    RULES:
    1. **NO BROKEN IMAGES:** Do NOT output Markdown images `![alt](url)` because the website security blocks them.
    2. **INSTEAD:** Describe the product vividly using text.
    3. **DATA:** Use the PDFs for specific numbers (Nutrition, Pack Sizes).
    4. **LANGUAGE:** English or Spanish.
    
    WEBSITE CONTEXT:
    {web_text}
    """
    payload = [system_prompt] + live_docs + [question]
    try:
        response = model.generate_content(payload)
        return response.text
    except: return "Loading..."

# --- UI DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about nutrition, cheese types, or the facility...")
    submit = st.form_submit_button("Ask Agent")

if submit and user_input:
    # 1. SHOW USER INPUT
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # 2. CHECK FOR IMAGE KEYWORDS (The Python Force-Display)
    # We intercept the request before the AI answers to check if you want an image
    q_lower = user_input.lower()
    
    # === IMAGE BYPASS LOGIC ===
    display_image_url = None
    display_caption = ""
    
    if "plant" in q_lower or "factory" in q_lower or "facility" in q_lower or "building" in q_lower:
        display_image_url = "https://hcmakers.com/wp-content/uploads/2021/01/PLANT_138.jpg"
        display_caption = "State-of-the-Art SQF Level 3 Facility in Kent, IL"
        
    elif "fresco" in q_lower:
        display_image_url = "https://hcmakers.com/wp-content/uploads/2020/12/YBH_Fresco_Natural_10oz.png"
        display_caption = "Queso Fresco (Award Winning)"
        
    elif "oaxaca" in q_lower:
        display_image_url = "https://hcmakers.com/wp-content/uploads/2020/12/YBH_OAXACA_BALL_5lb_v3.png"
        display_caption = "Oaxaca Melting Cheese"
        
    elif "cotija" in q_lower:
        display_image_url = "https://hcmakers.com/wp-content/uploads/2020/12/YBH_cotija_quarter_5lb.png"
        display_caption = "Cotija (Aged)"

    # 3. GENERATE AI TEXT RESPONSE
    with st.chat_message("assistant"):
        
        # A. Show the image FIRST if we found one match
        if display_image_url:
            show_secure_image(display_image_url, display_caption)
            # Add to history invisible to AI but visible to user
            st.session_state.chat_history.append({"role": "assistant", "content": f"**[Displaying Image: {display_caption}]**"})
        
        # B. Show the text answer
        with st.spinner("Analyzing data..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})