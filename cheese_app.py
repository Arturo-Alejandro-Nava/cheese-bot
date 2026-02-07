import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io

# --- CONFIGURATION ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("No API Key found. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

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

# --- 1. HARDCODED "FACT SHEET" (The Fix) ---
# We force-feed these numbers to the AI so it never guesses wrong.
NUTRITION_FACTS = """
OFFICIAL NUTRITION SPECS (USE THESE EXACT NUMBERS):

1. **OAXACA CHEESE:**
   - Calories: 80 calories per 1oz serving. (A 10oz ball = 800 calories total).
   - Protein: 7g per serving.
   - Fat: 6g per serving.
   - Attributes: Excellent Melting. Award Winning.

2. **QUESO FRESCO:**
   - Calories: 80-90 calories per serving (check pdf).
   - Protein: 5g per 1oz serving.
   - Fat: 6g per serving.
   - Attributes: Soft, Crumbly, Non-melting.

3. **QUESO PANELA:**
   - Protein: 6g per 1oz serving.
   - Calories: 80 per serving.
   - Attributes: Grilling Cheese (Non-melting).

4. **COTIJA:**
   - Sodium: High (Salty/Dry).
   - Usage: Grating/Topping.

5. **CONTACT INFO:**
   - Sales Phone: 847-258-0375
   - Marketing (Arturo Nava): 847-502-0934
"""

# --- 2. LIVE SCRAPER (Context) ---
@st.cache_resource(ttl=3600)
def get_live_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # TEXT
    urls = ["https://hcmakers.com/", "https://hcmakers.com/products/", "https://hcmakers.com/contact-us/", "https://hcmakers.com/capabilities/"]
    web_text = "WEBSITE DATA:\n"
    for url in urls:
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.content, 'html.parser')
            web_text += f"\n--- SOURCE: {url} ---\n{soup.get_text(' ', strip=True)[:3000]}\n"
        except: continue
        
    # PDF DOCS
    pdf_files = []
    file_list = []
    try:
        r = requests.get("https://hcmakers.com/resources/", headers=headers)
        soup = BeautifulSoup(r.content, 'html.parser')
        zip_link = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')), None)
        
        if zip_link:
            z_data = requests.get(zip_link, headers=headers).content
            with zipfile.ZipFile(io.BytesIO(z_data)) as z:
                i = 0
                for fname in z.namelist():
                    if fname.lower().endswith(".pdf") and i < 8:
                        with open(f"temp_{i}.pdf", "wb") as f: f.write(z.read(fname))
                        pdf_files.append(genai.upload_file(f"temp_{i}.pdf", display_name=fname))
                        file_list.append(fname)
                        i += 1
    except: pass
    
    return web_text, pdf_files, file_list

# --- LOAD ---
with st.spinner("Connecting to Live Data..."):
    website_knowledge, live_docs, doc_names = get_live_data()

# --- BRAIN ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_answer(question):
    
    doc_str = "\n".join(doc_names)
    
    system_prompt = f"""
    You are the Sales AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    CRITICAL INSTRUCTIONS:
    1. **CHECK THE 'NUTRITION SPECS' LIST FIRST**:
       - If the user asks for Calories, Protein, or Fat, look at the "OFFICIAL NUTRITION SPECS" list below FIRST.
       - Override anything you think you know with these numbers. 
       - *Example:* If Spec list says 80 calories for Oaxaca, output 80. Do not guess 100.
       
    2. **IMAGES:** Polite refusal. "I am a text-based assistant provided for spec verification. Please check the products page for visuals."
    
    3. **CONTACTS:** Use the list provided in Specs.
    
    4. **LANG:** English/Spanish.
    
    OFFICIAL NUTRITION SPECS:
    {NUTRITION_FACTS}
    
    WEBSITE CONTEXT:
    {website_knowledge}
    """
    
    payload = [system_prompt] + live_docs + [question]
    try:
        # File processing wait
        for f in live_docs:
             while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
        return model.generate_content(payload).text
    except:
        return "Checking database..."

# --- UI ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form(key="chat_form"):
    user_input = st.text_input("Ask about nutrition, specs, or sales... / Pregunta...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing Specs..."):
            response_text = get_answer(user_input)
            st.markdown(response_text)
            
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})