import streamlit as st
import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
from pptx import Presentation
from random import randint
from dotenv import load_dotenv  # Import dotenv to load .env file
import fitz  # PyMuPDF for extracting text from PDFs
import json 

# Load environment variables from .env file
load_dotenv()
# Firebase and Google Generative AI Configuration
if not firebase_admin._apps:
    # Load Firebase credentials from Streamlit secrets
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

# Load API key from secrets for Google Generative AI
api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)

model_name = "gemini-1.5-flash"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = []

# Function to extract text from a PDF file
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
    
    
# AI Generation functions
def generate_content(prompt):
    try:
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error generating content: {str(e)}"

# Firebase Authentication functions
def firebase_login(email, password):
    try:
        user = auth.get_user_by_email(email)
        return user
    except:
        return None

def firebase_signup(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        return user
    except Exception as e:
        return str(e)

def generate_notes(topic, pdf_context):
    prompt = f"Generate detailed notes on {topic} using the following context: {pdf_context}"
    return generate_content(prompt)

# Quiz Creation and Evaluation
def generate_quiz(subject):
    quiz_content = generate_content(f"Create a quiz for {subject} with answer choices and an answer key.")
    questions = [
        {
            "question": f"Sample Question {i+1} for {subject}?",
            "choices": ["Option A", "Option B", "Option C", "Option D"],
            "answer": randint(0, 3)  # Randomly set an answer for demonstration
        }
        for i in range(3)
    ]
    return questions

def evaluate_quiz(user_answers, quiz):
    correct = sum(1 for i, answer in enumerate(user_answers) if answer == quiz[i]["answer"])
    return correct, len(quiz)

# Load chat history from Firebase
def load_chat_history(user_id):
    try:
        chat_docs = db.collection("chat_context").document(user_id).get().to_dict()
        return chat_docs.get("context", []) if chat_docs else []
    except Exception as e:
        st.error(f"Error loading chat history: {str(e)}")
        return []

# Save a message to Firebase
def save_message(user_id, role, content):
    try:
        db.collection("chat_context").document(user_id).update({
            "context": firestore.ArrayUnion([{"role": role, "content": content}])
        })
    except Exception as e:
        st.error(f"Error saving message: {str(e)}")

# Streamlit UI
st.set_page_config(layout="wide")

# Sidebar for chat history and profile information (only visible if logged in)
if "user_id" in st.session_state:
    with st.sidebar:
        st.title("Chat History")

        # Display chat history as clickable headers
        chat_context = load_chat_history(st.session_state.user_id)
        
        if chat_context:
            for i, message in enumerate(chat_context):
                # Create a short heading (first 30 characters or so)
                short_heading = f"{message['role']}: {message['content'][:30]}..." if len(message['content']) > 30 else message['content']
                
                # Use an expander to reveal the full message when clicked
                with st.expander(short_heading):
                    st.write(message['content'])
        else:
            st.write("No chat history available.")

        
        user = auth.get_user(st.session_state.user_id)
        st.title("Welcome")
        st.write(f"Email: {user.email}")
        if st.button("Logout"):
            # Clear all session state and reset page
            st.session_state.clear()
            st.rerun()    # This triggers a rerun by setting query params
            st.stop()  # Prevents further code execution after refresh

# Main UI Area
st.title("AI Teacher Chatbot Interface")
st.write("An AI-powered teacher that generates notes, answers questions, and creates quizzes.")

# Authentication Page: Login or Signup
if "user_id" not in st.session_state:
    st.subheader("Welcome! Please Login or Sign Up")
    auth_choice = st.selectbox("Choose an action", ["Login", "Sign Up"])

    if auth_choice == "Login":
        st.subheader("Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = firebase_login(email, password)
            if user:
                st.session_state.user_id = user.uid
                st.session_state.chat_history = load_chat_history(user.uid)
                st.success("Logged in successfully!")
                st.rerun()    # This triggers a rerun by setting query params
                st.stop()  # Prevents further code execution after refresh
            else:
                st.error("Login failed. Check your credentials.")

    elif auth_choice == "Sign Up":
        st.subheader("Sign Up")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Sign Up"):
            signup_result = firebase_signup(email, password)
            if isinstance(signup_result, str):
                st.error(f"Sign Up failed: {signup_result}")
            else:
                st.success("Account created successfully! Please log in.")

# Chatbot Interface for Authenticated Users
if "user_id" in st.session_state:
    # Main options for interacting with the chatbot
    option = st.selectbox("Choose an option:", ["Generate Notes", "Ask Doubt", "Take Quiz"])

    if option == "Generate Notes":
        topic = st.text_input("Enter the topic for notes generation:")

        # Load PDF file automatically for context
        pdf_path = "./req/Master_Intro. to cloud computing 1.pdf"  # Path to your reference PDF file
        pdf_context = extract_pdf_text(pdf_path)

        if st.button("Generate Notes"):
            notes = generate_notes(topic, pdf_context)
            st.write(notes)
            st.session_state.chat_history.append({"role": "AI", "content": notes})

    elif option == "Ask Doubt":
        question = st.text_input("Enter your question:")
        if st.button("Get Answer"):
            answer = generate_content(f"Answer this question: {question}")
            st.write(answer)
            st.session_state.chat_history.append({"role": "AI", "content": answer})

    elif option == "Take Quiz":
        subject = st.text_input("Enter the subject for the quiz:")
        
        # Generate quiz only if "Generate Quiz" button is clicked
        if st.button("Generate Quiz"):
            st.session_state.quiz = generate_quiz(subject)
            st.session_state.user_answers = [None] * len(st.session_state.quiz)  # Initialize answers

        # Display quiz questions if they are in session state
        if st.session_state.quiz:
            for i, q in enumerate(st.session_state.quiz):
                st.write(f"Q{i+1}: {q['question']}")
                
                # Maintain the state of each radio selection
                if st.session_state.user_answers[i] is None:
                    st.session_state.user_answers[i] = st.radio(
                        f"Choose an answer for Question {i+1}:",
                        options=q["choices"],
                        key=f"q{i}"
                    )
                else:
                    st.session_state.user_answers[i] = st.radio(
                        f"Choose an answer for Question {i+1}:",
                        options=q["choices"],
                        index=q["choices"].index(st.session_state.user_answers[i]),
                        key=f"q{i}"
                    )

        # Submit Quiz button to evaluate answers
        if st.button("Submit Quiz") and st.session_state.quiz:
            correct, total = evaluate_quiz(st.session_state.user_answers, st.session_state.quiz)
            st.write(f"You scored {correct} out of {total}!")
            st.session_state.chat_history.append({"role": "AI", "content": f"Quiz score: {correct}/{total}"})
