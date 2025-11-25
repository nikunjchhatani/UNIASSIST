import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime
import pytz
import speech_recognition as sr
import pyttsx3
from database import init_database, get_course_data, save_chat, get_or_create_user_session
import edge_tts
import asyncio
import os
import threading
import uuid

# Must be the first Streamlit command
st.set_page_config(
    page_title="UniAssist RBU Web Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# Session & Theme Initialization
# -------------------------------
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # (user_msg, bot_msg, timestamp)

if 'current_question' not in st.session_state:
    st.session_state.current_question = ""

if 'chat' not in st.session_state:
    st.session_state.chat = None  # will initialize after model

# Initialize database and get user session
init_database()
user_id = get_or_create_user_session()

# Configure Gemini AI
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Gemini model & chat
model = genai.GenerativeModel('gemini-2.0-flash')
if st.session_state.chat is None:
    st.session_state.chat = model.start_chat(history=[])

# Get course data from database
data = {"courses": get_course_data()}

# AI Context
context = f"""
You are a helpful university admission counselor chatbot. You have information about the following courses:

{json.dumps(data, indent=2)}

Key points to remember:
1. Always be polite and professional
2. Provide accurate information about courses based on the data provided
3. Handle general queries and greetings naturally
4. If asked about information not in the data, politely say you can only provide information about the listed courses
5. Keep responses concise but informative
6. Use appropriate emojis to make responses engaging
7. Format responses using markdown for better readability

Example interactions:
- Greet users warmly
- Answer questions about course duration, fees, and subjects
- Provide guidance on admission process
- Handle small talk naturally
- Stay focused on academic and admission related queries
"""

# -------------------------------
# TTS Initialization
# -------------------------------
engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)
if len(voices) > 1:
    engine.setProperty('voice', voices[1].id)


def get_ai_response(user_input):
    try:
        prompt = f"Context: {context}\n\nUser: {user_input}\n\nResponse:"
        response = st.session_state.chat.send_message(prompt)
        save_chat(user_input, response.text)
        return response.text
    except Exception as e:
        st.error("An error occurred while getting a response from the AI. Please try again.")
        return f"I apologize, but I encountered an error: {str(e)}"


# Speech-to-Text Function
def speech_to_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("🎙 Listening... please speak")
        try:
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Sorry, I couldn't understand. Please try again."
        except sr.RequestError:
            return "Could not request results. Please check your internet connection."


# Text-to-Speech Function
def text_to_speech(text):
    def run_speech():
        local_engine = pyttsx3.init()
        local_engine.setProperty('rate', 150)
        local_engine.setProperty('volume', 1.0)
        voices_local = local_engine.getProperty('voices')
        if len(voices_local) > 1:
            local_engine.setProperty('voice', voices_local[1].id)
        local_engine.say(text)
        local_engine.runAndWait()

    threading.Thread(target=run_speech, daemon=True).start()


def stop_text_to_speech():
    global engine, stop_speech
    stop_speech = True
    if engine is not None:
        engine.stop()


# Example questions
example_questions = [
    "Hi! Can you help me with course information?",
    "What courses do you offer?",
    "Tell me about B.Tech program",
    "What is the fee structure for BCA?",
    "What subjects are taught in B.Sc first semester?",
    "How long is the B.Tech program?",
    "What are the subjects in BCA?",
    "Tell me about admission process",
    "What is the duration of B.Sc?",
    "Can you compare B.Tech and BCA programs?"
]


def set_question(question):
    st.session_state.current_question = question


# -------------------------------
# Modern UI Styling
# -------------------------------

# Base light theme CSS
light_css = """
<style>
/* Overall App */
.stApp {
    background: radial-gradient(circle at top left, #e0f2fe 0, #f9fafb 40%, #e5e7eb 100%);
    color: #111827;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* Top Title Area */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 0 0.5rem 0;
}
.app-header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.app-logo {
    width: 42px;
    height: 42px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #2563eb, #38bdf8);
    color: #ffffff;
    font-size: 1.4rem;
    font-weight: 700;
}
.app-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #0f172a;
}
.app-subtitle {
    font-size: 0.9rem;
    color: #6b7280;
}

/* Generic Buttons */
.stButton>button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: #ffffff;
    border-radius: 999px;
    padding: 0.45rem 1.4rem;
    border: none;
    font-size: 0.95rem;
    font-weight: 500;
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.25);
    transition: all 0.18s ease-in-out;
}
.stButton>button:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 28px rgba(37, 99, 235, 0.35);
}

/* Chat Container */
.chat-wrapper {
    max-width: 900px;
    margin: 0 auto;
    padding: 0.5rem 0 1rem 0;
}
.chat-area {
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(10px);
    border-radius: 18px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 12px 30px rgba(15,23,42,0.12);
    max-height: 65vh;
    overflow-y: auto;
    opacity:
}

/* Chat Messages */
.chat-message {
    margin-bottom: 0.9rem;
    display: flex;
    flex-direction: column;
}
.chat-row {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
}
.chat-avatar {
    width: 32px;
    height: 32px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
}
.chat-bubble {
    padding: 0.75rem 1rem;
    border-radius: 16px;
    font-size: 0.95rem;
    line-height: 1.5;
    max-width: 80%;
}
.user-message .chat-row {
    justify-content: flex-end;
}
.user-message .chat-bubble {
    background: linear-gradient(135deg, #2563eb, #38bdf8);
    color: #f9fafb;
    border-bottom-right-radius: 4px;
}
.user-message .chat-avatar {
    background: #1d4ed8;
    color: #dbeafe;
}
.bot-message .chat-row {
    justify-content: flex-start;
}
.bot-message .chat-bubble {
    background: #f3f4f6;
    color: #111827;
    border-bottom-left-radius: 4px;
}
.bot-message .chat-avatar {
    background: #111827;
    color: #e5e7eb;
}
.timestamp {
    color: #9ca3af;
    font-size: 0.75rem;
    margin-top: 0.15rem;
}

/* Input Area */
.input-bar {
    max-width: 900px;
    margin: 0.75rem auto 0.25rem auto;
    padding: 0.7rem 1rem 0.9rem 1rem;
    background: rgba(255,255,255,0.8);
    backdrop-filter: blur(10px);
    border-radius: 999px;
    box-shadow: 0 10px 25px rgba(15,23,42,0.20);
}
.stTextInput>div>div>input {
    border-radius: 999px;
    border: 1px solid #d1d5db;
    padding: 0.5rem 0.9rem;
    background-color: #f9fafb;
    color: #111827;
}

/* Sidebar */
.sidebar-section {
    background-color: #ffffff;
    padding: 1rem;
    border-radius: 12px;
    margin-bottom: 1rem;
    box-shadow: 0 6px 14px rgba(15,23,42,0.10);
}
.sidebar-header {
    color: #111827;
    font-size: 1.05rem;
    font-weight: 700;
    margin-bottom: 0.75rem;
    padding-bottom: auto;
    border-bottom: auto;
}
.sidebar-link {
    display: block;
    padding: 0.45rem 0.4rem;
    color: #4b5563;
    text-decoration: none;
    border-radius: 8px;
    transition: all 0.2s;
    font-size: 0.9rem;
}
.sidebar-link:hover {
    background-color: #eff6ff;
    color: #1d4ed8;
}

/* Example Questions as compact pills in sidebar */
.example-question-btn button {
    background: #f9fafb !important;
    color: #111827 !important;
    border-radius: 999px !important;
    padding: 0.25rem 0.7rem !important;
    font-size: 0.85rem !important;
    border: 1px solid #e5e7eb !important;
    box-shadow: none !important;
}
.example-question-btn button:hover {
    background: #eff6ff !important;
    border-color: #bfdbfe !important;
}

/* Footer */
.footer-text {
    text-align: center;
    color: #9ca3af;
    padding: 0.75rem 0 0.25rem 0;
    font-size: 0.85rem;
}
</style>
"""

# Dark theme CSS
dark_css = """
<style>
.stApp {
    background: radial-gradient(circle at top left, #020617 0, #020617 40%, #020617 100%);
    color: #e5e7eb;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.app-title {
    color: #e5e7eb;
}
.app-subtitle {
    color: #9ca3af;
}

.chat-area {
    background: rgba(15,23,42,0.95);
    border-radius: 18px;
    box-shadow: 0 16px 40px rgba(0,0,0,0.65);
}

.chat-bubble {
    color: #e5e7eb;
}
.bot-message .chat-bubble {
    background: #111827;
}
.user-message .chat-bubble {
    background: linear-gradient(135deg, #2563eb, #4f46e5);
}
.chat-avatar {
    color: #e5e7eb;
}
.user-message .chat-avatar {
    background: #1d4ed8;
}
.bot-message .chat-avatar {
    background: #020617;
}

.timestamp {
    color: #6b7280;
}

/* Input Area */
.input-bar {
    background: rgba(15,23,42,0.95);
}
.stTextInput>div>div>input {
    background-color: #020617;
    color: #f9fafb;
    border: 1px solid #374151;
}
.stTextInput>div>div>input::placeholder {
    color: #6b7280;
}

/* Sidebar */
.sidebar-section {
    background-color: #020617;
    box-shadow: 0 12px 30px rgba(0,0,0,0.7);
}
.sidebar-header {
    color: #e5e7eb;
    border-bottom-color: #1f2933;
}
.sidebar-link {
    color: #9ca3af;
}
.sidebar-link:hover {
    background-color: #111827;
    color: #e5e7eb;
}

/* Example questions */
.example-question-btn button {
    background: #020617 !important;
    color: #e5e7eb !important;
    border-color: #1f2937 !important;
}
.example-question-btn button:hover {
    background: #111827 !important;
}

/* Footer */
.footer-text {
    color: #6b7280;
}
</style>
"""

# Apply CSS based on dark mode
st.markdown(light_css, unsafe_allow_html=True)
if st.session_state.dark_mode:
    st.markdown(dark_css, unsafe_allow_html=True)

# -------------------------------
# Layout: Sidebar
# -------------------------------
with st.sidebar:
    st.image("./Resources/rbu.jpeg", use_container_width=True)

    st.markdown("""
        <div class="sidebar-section">
            <div class="sidebar-header">🤖 Welcome!</div>
            <p>I'm your UniAssist RBU Web Assistant. Ask me anything about courses, admissions, and academic programs.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="sidebar-section">
            <div><b><b><b> Quick Questions</b></b></b></div>
    """, unsafe_allow_html=True)

    for question in example_questions:
        # Wrap with class for styling
        with st.container():
            st.markdown("<div class='example-question-btn'>", unsafe_allow_html=True)
            if st.button(f"{question}", key=f"btn_{question}", use_container_width=True):
                set_question(question)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
        <div class="sidebar-section">
            <div class="sidebar-header">🔗 Quick Links</div>
            <a href="https://rbunagpur.in/" class="sidebar-link">📚 University Website</a>
            <a href="https://rbunagpur.in/Admissions/" class="sidebar-link">🎓 Admission Portal</a>
            <a href="https://rbunagpur.in/contactus.aspx" class="sidebar-link">👤 Contact Us</a>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="sidebar-section">
            <div class="sidebar-header">📞 Contact Support</div>
            <p>📞 Helpline: 9156288990 / 9607980531</p>
            <p>📧 Email: admissions@rbunagpur.in</p>
        </div>
    """, unsafe_allow_html=True)

    # Dark mode toggle
    st.markdown("---")
    st.session_state.dark_mode = st.toggle("🌙 Dark mode", value=st.session_state.dark_mode)

# -------------------------------
# Layout: Main Header
# -------------------------------
st.markdown(
    """
    <div class="app-header">
        <div class="app-header-left">
            <div class="app-logo">🎓</div>
            <div>
                <div class="app-title">UniAssist RBU Web Assistant</div>
                <div class="app-subtitle">Ask about programs, fees, subjects, and admissions anytime.</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown("---")

# -------------------------------
# Chat Display
# -------------------------------
chat_container = st.container()

with chat_container:
    st.markdown("<div class='chat-wrapper'>", unsafe_allow_html=True)

    if not st.session_state.chat_history:
        # Friendly starter message
        st.markdown(
            """
            <div class="chat-message bot-message">
                <div class="chat-row">
                    <div class="chat-avatar">🤖</div>
                    <div class="chat-bubble">
                        Hello! 👋 I'm your virtual assistant for RBU.<br><br>
                        You can ask me about:
                        <ul>
                            <li>Available courses and programs</li>
                            <li>Fee structure and duration</li>
                            <li>Subjects in each semester</li>
                            <li>Admission process and eligibility</li>
                        </ul>
                        Try clicking one of the example questions on the left to get started!
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    for message_data in st.session_state.chat_history:
        if len(message_data) == 3:
            user, bot, timestamp = message_data
        else:
            user, bot = message_data
            timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M')

        # User message bubble
        st.markdown(
            f"""
            <div class="chat-message user-message">
                <div class="chat-row">
                    <div class="chat-bubble">
                        <strong>You</strong><br>{user}
                    </div>
                    <div class="chat-avatar">🧑</div>
                </div>
                <div class="timestamp" style="text-align:right;">{timestamp}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Bot message bubble
        st.markdown(f"""
<div class="chat-message bot-message">
    <strong>Assistant:</strong><br>
    {bot}
    <div class="timestamp" style="text-align:right;>{timestamp}</div>
</div>
""", unsafe_allow_html=True)


        # Play AI response button
        #play_key = f"play_{uuid.uuid4()}"
        if st.button("🔊 Play Response", key=f"play_{timestamp}"):
            text_to_speech(bot)

    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------------
# Input Bar
# -------------------------------
st.markdown("---")

with st.container():
    input_col1, input_col2, input_col3 = st.columns([6, 1, 1])

    with input_col1:
        user_input = st.text_input(
            "Ask your question here...",
            value=st.session_state.current_question,
            key="input",
            placeholder="e.g., What courses do you offer?",
            label_visibility="collapsed"
        )
    with input_col2:
        send_button = st.button("Send 📤", use_container_width=True)
    with input_col3:
        voice_button = st.button("🎤 Speak", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# Voice input
if voice_button:
    user_input = speech_to_text()
    st.session_state.current_question = user_input
    st.rerun()

# Send text input
if send_button and user_input:
    ai_response = get_ai_response(user_input)
    current_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S.%f')
    st.session_state.chat_history.append((user_input, ai_response, current_time))
    st.session_state.current_question = ""
    st.rerun()

# -------------------------------
# Footer
# -------------------------------
st.markdown(
    """
    <div class="footer-text">
        © 2025 UniAssist Co. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True
)