import os
import io
import tempfile
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
import markdown
from xhtml2pdf import pisa
from datetime import datetime
from audio_recorder_streamlit import audio_recorder

# Load environment variables
load_dotenv()

# Initialize Groq client
if "GROQ_API_KEY" in os.environ:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
else:
    st.error("GROQ_API_KEY not found in environment variables. Please check your .env file.")
    st.stop()

# Define the standard OT notes questions
QUESTIONS = [
    "Patient Demographics: Please provide Patient Age, Gender, MRN, and Date of Surgery.",
    "Diagnoses: What are the Pre-operative and Post-operative Diagnoses?",
    "Personnel & Anesthesia: Name the Procedure(s) Performed, Surgeon(s), Assistants, and Anesthesia used.",
    "Indications: What were the Indications for Surgery?",
    "Findings & Technique: Summarize the Findings and describe the Surgical Technique/Procedure step-by-step.",
    "Complications & Outcome: Were there any Complications? What is the Estimated Blood Loss (EBL) and Post-operative disposition/care plan?"
]

st.set_page_config(page_title="OT Notes Taker", page_icon="🩺", layout="wide")

st.title("🩺 AI-Powered OT Notes Taker")
st.markdown("Record your responses to the prompts below. The AI will transcribe your audio and format a professional Operative Note PDF.")

# Initialize session state for storing transcribed text
for i in range(len(QUESTIONS)):
    if f"text_{i}" not in st.session_state:
        st.session_state[f"text_{i}"] = ""
        
if "pdf_ready" not in st.session_state:
    st.session_state.pdf_ready = False
if "final_report" not in st.session_state:
    st.session_state.final_report = ""

def transcribe_audio(audio_bytes):
    with st.spinner("Transcribing via Groq Whisper..."):
        try:
            # We need to write audio_bytes to a temporary file because groq expects a file object with a filename
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(audio_bytes)
                temp_filename = temp_audio.name
            
            with open(temp_filename, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(temp_filename, file.read()),
                    model="whisper-large-v3",
                    prompt="Medical terminology context. Operative notes.",
                    response_format="json", # Safest approach to get cleanly parsed JSON object
                    language="en"
                )
            
            os.remove(temp_filename)
            # Depending on SDK version, it parses JSON to an object with .text, or a dict.
            if hasattr(transcription, "text"):
                return transcription.text
            elif isinstance(transcription, dict) and "text" in transcription:
                return transcription["text"]
            else:
                return str(transcription)
        except Exception as e:
            st.error(f"Transcription error: {e}")
            return ""

def generate_ot_report_pdf(report_text):
    md_html = markdown.markdown(report_text)
    current_date = datetime.now().strftime("%B %d, %Y")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @frame header_frame {{
                -pdf-frame-content: header_content;
                left: 50pt; width: 495pt; top: 30pt; height: 30pt;
            }}
            @frame footer_frame {{
                -pdf-frame-content: footer_content;
                left: 50pt; width: 495pt; top: 780pt; height: 30pt;
            }}
        }}
        
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 11pt;
            color: #2c3e50;
            line-height: 1.5;
        }}
        
        strong, b {{ color: #000000; }}
        
        h1, h2, h3, h4 {{
            color: #2980b9;
            margin-top: 15px;
            margin-bottom: 5px;
        }}
        
        h1 {{ font-size: 16pt; border-bottom: 2px solid #2980b9; padding-bottom: 3px; }}
        h2 {{ font-size: 13pt; margin-top: 20px; }}
        h3 {{ font-size: 12pt; }}
        
        ul {{ margin-bottom: 10px; margin-left: 0; padding-left: 20px; }}
        li {{ margin-bottom: 4px; }}
        
        #header_content {{
            text-align: right;
            font-size: 8pt;
            color: #7f8c8d;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 3px;
        }}
        
        #footer_content {{
            text-align: center;
            font-size: 9pt;
            color: #7f8c8d;
            border-top: 1px solid #bdc3c7;
            padding-top: 5px;
        }}
        
        .title-box {{
            background-color: #ecf0f1;
            border-left: 6px solid #2980b9;
            padding: 12px;
            margin-bottom: 20px;
        }}
        .title-box h1 {{
            margin: 0;
            border: none;
            color: #2c3e50;
            text-transform: uppercase;
        }}
    </style>
    </head>
    <body>
        <div id="header_content">
            Generated on {current_date} &bull; Confidential Medical Record
        </div>
        
        <div id="footer_content">
            Page <pdf:pagenumber> of <pdf:pagecount>
        </div>
        
        <div class="title-box">
            <h1>Operative Report</h1>
        </div>
        
        {md_html}
    </body>
    </html>
    """
    
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf.close()
    
    with open(temp_pdf.name, "w+b") as dest:
        pisa.CreatePDF(html_content, dest=dest)
        
    return temp_pdf.name


st.sidebar.header("OT Notes Progress")
st.sidebar.info("Fill out all sections and click 'Generate Final Report' at the bottom.")

# Iterate through questions
for i, q in enumerate(QUESTIONS):
    with st.expander(f"Step {i+1}: {q}", expanded=True):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("🎙️ **Record your answer:**")
            audio_bytes = audio_recorder(key=f"recorder_{i}")
            
            if audio_bytes:
                st.audio(audio_bytes, format="audio/wav")
                if st.button("Transcribe Audio", key=f"transcribe_{i}"):
                    text_result = transcribe_audio(audio_bytes)
                    if text_result:
                        st.session_state[f"text_{i}"] = text_result
                        st.rerun()
                        
        with col2:
            st.write("📝 **Text Response:**")
            # Text area automatically syncs with st.session_state[key]
            st.text_area(
                "Edit transcription below:", 
                height=150, 
                key=f"text_{i}",
                label_visibility="collapsed"
            )

st.divider()

if st.button("🚀 Generate Final OT Report", use_container_width=True, type="primary"):
    # Gather all answers
    context_parts = []
    for i, q in enumerate(QUESTIONS):
        ans = st.session_state.get(f"text_{i}", "").strip()
        if ans:
            context_parts.append(f"Q: {q}\nA: {ans}")
        else:
            context_parts.append(f"Q: {q}\nA: [Not Provided]")
    
    full_context = "\n\n".join(context_parts)
    
    prompt = f"""
    You are an expert Medical Scribe and Surgeon's assistant.
    I will provide you with a series of spoken responses from a doctor regarding a recent surgery.
    
    Your task is to generate a formal, well-structured Operative Note based ONLY on the provided answers.
    Use standard medical terminology.
    
    CRITICAL FORMATTING INSTRUCTIONS:
    - Format short variables as strict Key-Value pairs using bullet points (`- **Key**: Value`). 
      For example, PATIENT DEMOGRAPHICS should look like:
         - **Patient Age**: 52 years
         - **Gender**: Male
         - **MRN**: 12345678
         - **Date of Surgery**: 15 March 2026
    - Use this key-value formatting for PRE/POST OP DIAGNOSES, PROCEDURE(S), SURGEON(S), ANESTHESIA, and ESTIMATED BLOOD LOSS where appropriate.
    - For narrative sections (INDICATIONS, FINDINGS, DETAILED PROCEDURE), use professional numbered or bulleted lists where it improves readability, or properly spaced paragraphs.
    
    Format the output clearly using the following standard OT Note sections (as H2 Headers):
    ## PATIENT DEMOGRAPHICS
    ## PRE-OPERATIVE DIAGNOSIS
    ## POST-OPERATIVE DIAGNOSIS
    ## PROCEDURE(S) PERFORMED
    ## SURGEON(S) & ANESTHESIA
    ## INDICATIONS FOR SURGERY
    ## FINDINGS
    ## DETAILED PROCEDURE / TECHNIQUE
    ## ESTIMATED BLOOD LOSS
    ## COMPLICATIONS
    ## POST-OPERATIVE DISPOSITION / PLAN
    
    Make it look extremely professional. Do not add any conversational filler text, just output the exact report markdown.
    
    Given context:
    {full_context}
    """
    
    with st.spinner("Generating Professional OT Report via Groq Llama 3.3..."):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert medical report formatter."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            final_text = response.choices[0].message.content
            st.session_state.final_report = final_text
            st.session_state.pdf_ready = True
            
        except Exception as e:
            st.error(f"Failed to generate report: {e}")

if st.session_state.pdf_ready:
    st.success("Report Generated Successfully!")
    
    try:
        pdf_path = generate_ot_report_pdf(st.session_state.final_report)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            
        st.download_button(
            label="📥 Download Generated PDF Report",
            data=pdf_bytes,
            file_name="Operative_Note.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Failed to create PDF. Error: {e}")
    
    st.markdown("### Preview of the Output:")
    st.text_area("Final Report Preview", value=st.session_state.final_report, height=400)
