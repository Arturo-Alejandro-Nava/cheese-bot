import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import os
import time
import zipfile
import io

# --- CONFIGURATION ---
API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- WEBPAGE CONFIG ---
st.set_page_config(page_title="Hispanic Cheese Makers-Nuestro Queso", page_icon="🧀")

# --- HEADER ---
if os.path.exists("logo.jpg"):
    st.image("logo.jpg", width=500)
else:
    st.title("Hispanic Cheese Makers-Nuestro Queso")

# --- 1. LIVE TEXT SCRAPER ---
@st.cache_resource(ttl=3600) 
def get_website_text():
    urls = [
        "https://hcmakers.com/",
        "https://hcmakers.com/products/",
        "https://hcmakers.com/quality/",
        "https://hcmakers.com/contact-us/",
        "https://hcmakers.com/resources/",
        "https://hcmakers.com/capabilities/"
    ]
    combined_text = "WEBSITE TEXT CONTENT:\n"
    for url in urls:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
                combined_text += f"\n--- SOURCE: {url} ---\n{text}\n"
        except:
            continue
    return combined_text

# --- 2. DEEP DOCUMENT HUNTER (PDF + ZIP) ---
@st.cache_resource(ttl=3600)
def process_live_assets():
    target_url = "https://hcmakers.com/resources/"
    pdf_objects = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        resp = requests.get(target_url, headers=headers)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Find ALL links (PDFs and ZIPs)
        links = soup.find_all('a', href=True)
        
        # We limit the bot to process only the most relevant 5 files to avoid timeout
        count = 0
        
        for link in links:
            href = link['href']
            if count >= 6: break # Stop after 6 files to keep it fast
            
            # CASE A: It's a direct PDF
            if href.endswith('.pdf'):
                try:
                    pdf_data = requests.get(href, headers=headers).content
                    temp_name = f"web_doc_{count}.pdf"
                    with open(temp_name, "wb") as f:
                        f.write(pdf_data)
                    
                    remote_file = genai.upload_file(path=temp_name, display_name=f"PDF_Doc_{count}")
                    # Wait for processing
                    while remote_file.state.name == "PROCESSING":
                        time.sleep(1)
                        remote_file = genai.get_file(remote_file.name)
                        
                    pdf_objects.append(remote_file)
                    count += 1
                except:
                    continue

            # CASE B: It's a ZIP file (The "Download All" button)
            elif href.endswith('.zip'):
                try:
                    zip_resp = requests.get(href, headers=headers)
                    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
                        # Look inside the zip for PDFs
                        for filename in z.namelist():
                            if filename.endswith(".pdf") and count < 6:
                                # Extract specific PDF from Zip
                                with z.open(filename) as source, open(f"unzipped_{count}.pdf", "wb") as target:
                                    target.write(source.read())
                                
                                # Upload the extracted PDF to Gemini
                                remote_file = genai.upload_file(path=f"unzipped_{count}.pdf", display_name=filename)
                                while remote_file.state.name == "PROCESSING":
                                    time.sleep(1)
                                    remote_file = genai.get_file(remote_file.name)
                                    
                                pdf_objects.append(remote_file)
                                count += 1
                except:
                    continue
                    
    except Exception as e:
        print(f"Error fetching docs: {e}")
        
    return pdf_objects

# --- INITIAL LOAD ---
# This spinner will run for about 10-15 seconds as it downloads/unzips files
with st.spinner("Downloading Catalogs, Unzipping Sell Sheets, and Analyzing..."):
    web_text = get_website_text()
    live_assets = process_live_assets()

# --- CHAT LOGIC ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_gemini_response(question):
    system_prompt = f"""
    You are the official Product AI for "Hispanic Cheese Makers-Nuestro Queso".
    
    KNOWLEDGE BASE:
    1. VISUAL DOCUMENTS (Attached): I have automatically downloaded and unzipped the official Sell Sheets and Catalogs. 
       - Look at these images for **Nutritional Facts Tables**, Pack Sizes, and specific melting attributes.
    2. WEBSITE TEXT (Below): Use this for general contact and about info.
    
    RULES:
    1. **CHECK THE TABLES:** If asked about Protein, Fat, or Calories, look at the Nutrition Fact Tables in the PDF attachments.
    2. **ACCURACY:** Do not guess numbers. Read them from the file.
    3. **LANGUAGE:** English or Spanish (User preference).
    4. **NO HALLUCINATIONS:** Only use info from these files or the text below.
    
    WEBSITE CONTEXT:
    {web_text}
    """
    
    content_package = [system_prompt] + live_assets + [question]
    
    try:
        response = model.generate_content(content_package)
        return response.text
    except Exception as e:
        return "I am processing the heavy visual data. Ask me again in 5 seconds."

# --- DISPLAY ---
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Ask about nutrition, specs, or products...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Reading Sell Sheets..."):
            response_text = get_gemini_response(user_input)
            st.markdown(response_text)
    
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})