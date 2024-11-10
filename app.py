import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF for extracting text from PDFs
import tempfile
import requests
from random import randint
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import markdown2
import io

# Load environment variables
load_dotenv()

units = {
    "Unit I": [
        "Introduction to Cloud Computing",
        "Definition, Characteristics, Components",
        "Cloud Service provider",
        "Software As a Service (SAAS)",
        "Platform As a Service (PAAS)",
        "Infrastructure as a Service (IAAS)",
        "Load balancing and Resource optimization",
        "Comparison among Cloud computing platforms: Amazon EC2, Google App Engine, Microsoft Azure, Meghraj"
    ],
    "Unit II": [
        "Introduction to Cloud Technologies",
        "Study of Hypervisors",
        "SOAP and REST",
        "Webservices and Mashups",
        "Virtual machine technology",
        "Virtualization applications in enterprises",
        "Pitfalls of virtualization",
        "Multi-entity support",
        "Multi-schema approach",
        "Multi-tenancy using cloud data stores"
    ],
    "Unit III": [
        "Cloud security fundamentals",
        "Vulnerability assessment tool for cloud",
        "Privacy and Security in cloud",
        "Cloud computing security architecture",
        "Issues in cloud computing",
        "Intercloud environments",
        "QoS Issues in Cloud",
        "Streaming in Cloud",
        "Quality of Service (QoS) monitoring",
        "Inter Cloud issues"
    ],
    "Unit IV": [
        "MICEF Computing (Mist, IOT, Cloud, Edge and FOG Computing)",
        "Dew Computing: Concept and Application",
        "Case Study: MiCEF Computing Programs using CloudSim and iFogSim"
    ]
}

# Firebase Initialization
if not firebase_admin._apps:
    firebase_credentials = {
        "type": st.secrets["firebase_credentials"]["type"],
        "project_id": st.secrets["firebase_credentials"]["project_id"],
        "private_key_id": st.secrets["firebase_credentials"]["private_key_id"],
        "private_key": st.secrets["firebase_credentials"]["private_key"],
        "client_email": st.secrets["firebase_credentials"]["client_email"],
        "client_id": st.secrets["firebase_credentials"]["client_id"],
        "auth_uri": st.secrets["firebase_credentials"]["auth_uri"],
        "token_uri": st.secrets["firebase_credentials"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["firebase_credentials"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["firebase_credentials"]["client_x509_cert_url"]
    }
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Google Generative AI Configuration
api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)
model_name = "gemini-1.5-flash"

# Session States
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = []

# PDF Text Extraction
def extract_pdf_text(pdf_path):
    try:
        text_content = ""
        with fitz.open(pdf_path) as pdf:
            for page_num in range(pdf.page_count):
                page = pdf[page_num]
                text_content += page.get_text() + "\n"
        return text_content
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

# AI Content Generation
def generate_content(prompt):
    try:
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"

# Firebase Login
def firebase_login(email, password):
    try:
        api_key = st.secrets["FIREBASE_WEB_API_KEY"]
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        response = requests.post(url, json=payload)
        data = response.json()

        if response.status_code == 200:
            user_id = data['localId']
            st.session_state.user_id = user_id
            return user_id
        else:
            return None
    except Exception as e:
        st.error(f"Error during login: {str(e)}")
        return None

# Firebase Signup
def firebase_signup(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        return user
    except Exception as e:
        return str(e)

# Notes Generation
def generate_notes(topic, pdf_context):
    prompt = f"Generate detailed notes on {topic} using the following context: {pdf_context}"
    return generate_content(prompt)

def generate_content_with_file(prompt, pdf_path):
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        sample_pdf = genai.upload_file(pdf_path)
        response = model.generate_content([prompt, sample_pdf])
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"

# Generate a quiz without exposing answers to the user
def generate_quiz(subject):
    # Generate the quiz content with questions and choices only
    quiz_content = generate_content(f"Create a quiz for {subject} with answer choices and an answer key.")
    questions = [
        {
            "question": f"Sample Question {i+1} for {subject}?",
            "choices": ["Option A", "Option B", "Option C", "Option D"],
            "answer": randint(0, 3)  # Internally store the correct answer
        }
        for i in range(3)  # Sample size, or adapt based on quiz content generation
    ]
    return questions

# Extract text answers from the uploaded image using Gemini API
def extract_answers_from_image(image_path):
    try:
        # Upload the image to Gemini and extract text
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        uploaded_image = genai.upload_file(image_path)
        response = model.generate_content("Extract answers in format 'Q1: A, Q2: B...' from the uploaded quiz image.", [uploaded_image])

        # Parse answers
        answer_text = response.text if response else ""
        extracted_answers = [line.split(": ")[1].strip() for line in answer_text.splitlines() if ":" in line]
        return extracted_answers
    except Exception as e:
        st.error(f"Error extracting answers: {str(e)}")
        return []

# Evaluate extracted answers against the stored answers
def evaluate_extracted_answers(extracted_answers, quiz):
    correct = sum(1 for i, answer in enumerate(extracted_answers) if answer == quiz[i]["choices"][quiz[i]["answer"]][0])  # Check first character matches answer choice
    return correct, len(quiz)

# Load and Save Chat History
def load_chat_history(user_id):
    try:
        chat_doc = db.collection("chat_context").document(user_id).get().to_dict()
        return chat_doc.get("context", []) if chat_doc else []
    except Exception as e:
        st.error(f"Error loading chat history: {str(e)}")
        return []

def save_message(user_id, role, content):
    try:
        db.collection("chat_context").document(user_id).set({
            "context": firestore.ArrayUnion([{"role": role, "content": content}])
        }, merge=True)
    except Exception as e:
        st.error(f"Error saving message: {str(e)}")

# Function to convert markdown notes to PDF
def markdown_to_pdf(notes_text):
    html_content = markdown2.markdown(notes_text)
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph(line, styles["BodyText"]) for line in html_content.splitlines() if line.strip()]
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# Streamlit Interface
st.set_page_config(layout="wide")
st.title("AI Teacher Chatbot Interface")
st.write("An AI-powered teacher that generates notes, answers questions, and creates quizzes.")

# Authentication Interface
if "user_id" not in st.session_state:
    st.subheader("Welcome! Please Login or Sign Up")
    auth_choice = st.selectbox("Choose an action", ["Login", "Sign Up"])

    if auth_choice == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user_id = firebase_login(email, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.chat_history = load_chat_history(user_id)
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Login failed. Check your credentials.")

    elif auth_choice == "Sign Up":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Sign Up"):
            signup_result = firebase_signup(email, password)
            if isinstance(signup_result, str):
                st.error(f"Sign Up failed: {signup_result}")
            else:
                st.success("Account created successfully! Please log in.")

# Sidebar and User Authentication
if "user_id" in st.session_state:
    with st.sidebar:
        st.title("Chat History")
        chat_context = load_chat_history(st.session_state.user_id)
        
        if chat_context:
            st.session_state.chat_history = chat_context
        for i, message in enumerate(st.session_state.chat_history):
            short_heading = f"{message['role']}: {message['content'][:30]}..."
            with st.expander(short_heading):
                st.write(message['content'])

        user = auth.get_user(st.session_state.user_id)
        
        if st.button("Clear History"):
            try:
                db.collection("chat_context").document(st.session_state.user_id).set({"context": []})
                st.session_state.chat_history = []
                st.success("Chat history cleared.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error clearing history: {str(e)}")

        if st.button("Logout"):
            del st.session_state["user_id"]
            del st.session_state["chat_history"]
            st.success("Logged out.")
            st.experimental_rerun()

    st.write("Choose an option below:")
    option = st.selectbox("Choose an option:", ["Generate Notes", "Ask Doubt", "Take Quiz"])

    # Generate Notes
    if option == "Generate Notes":
        selected_unit = st.selectbox("Select Unit", list(units.keys()))
        topics = units[selected_unit]
        selected_topic = st.selectbox("Select Topic", topics)
        comments = st.text_area("Additional instructions (optional):")
        pdf_file = st.file_uploader("Upload PDF for context (optional)")

        if st.button("Generate Notes"):
            prompt = f"Generate notes on {selected_topic}. {comments}"
            if pdf_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(pdf_file.getbuffer())
                    pdf_content = extract_pdf_text(temp_file.name)
                    prompt += f" Context from PDF: {pdf_content}"
            notes = generate_content(prompt)
            st.markdown(notes, unsafe_allow_html=True)
            pdf_data = markdown_to_pdf(notes)
            st.download_button("Download as PDF", pdf_data, file_name="notes.pdf", mime="application/pdf")

    # Ask Doubt
    elif option == "Ask Doubt":
        question = st.text_input("Enter your question:")
        if st.button("Get Answer"):
            answer = generate_content(f"Answer this question: {question}")
            st.write(answer)
            save_message(st.session_state.user_id, "User", question)
            save_message(st.session_state.user_id, "AI", answer)

    # Take Quiz
    elif option == "Take Quiz":
        selected_unit = st.selectbox("Select Unit", list(units.keys()))
        topics = units[selected_unit]
        selected_topic = st.selectbox("Select Topic", topics)

        # Generate quiz and display questions
        if st.button("Generate Quiz"):
            st.session_state.quiz = generate_quiz(selected_topic)

        if st.session_state.quiz:
            # Display each question without answers
            for i, q in enumerate(st.session_state.quiz):
                st.write(f"Q{i+1}: {q['question']}")
                for choice in q["choices"]:
                    st.write(f"- {choice}")

            # Image upload for answers
            uploaded_image = st.file_uploader("Upload an image with your answers (e.g., 'Q1: A, Q2: C'):")

            # Process the uploaded image for answers
            if uploaded_image and st.button("Submit Quiz"):
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(uploaded_image.read())
                    temp_file_path = temp_file.name
                extracted_answers = extract_answers_from_image(temp_file_path)

                if extracted_answers:
                    # Evaluate extracted answers
                    correct, total = evaluate_extracted_answers(extracted_answers, st.session_state.quiz)
                    st.write(f"Your Score: {correct} out of {total}")
                else:
                    st.error("Could not extract answers from the image. Please ensure the format is correct.")