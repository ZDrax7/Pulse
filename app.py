import os
import asyncio
import tempfile
import requests
import streamlit as st
import edge_tts
import replicate

# ==============================================================================
# 1. STREAMLIT APP CONFIGURATION & BRANDING
# ==============================================================================
st.set_page_config(
    page_title="Fintech Pulse Studio",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
    }
    .main-title {
        color: #00F0FF;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
        font-size: 2rem;
        text-shadow: 0px 0px 12px rgba(0, 240, 255, 0.4);
        margin-bottom: 0px;
    }
    .sub-title {
        color: #8b949e;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #00F0FF 0%, #0088FF 100%);
        color: #000000 !important;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        width: 100%;
        box-shadow: 0 4px 14px rgba(0, 240, 255, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>⚡ FINTECH PULSE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>AI Visual Viral Short Video Generator</p>", unsafe_allow_html=True)

# Sidebar Configuration for AI Keys
st.sidebar.header("⚙️ Cloud API Setup")
replicate_api_key = st.sidebar.text_input("Replicate API Key (for AI Video Generation)", type="password")
selected_voice = st.sidebar.selectbox(
    "Voice Actor",
    ["en-US-ChristopherNeural", "en-US-EricNeural", "en-US-JennyNeural"],
    index=0
)

# ==============================================================================
# 2. HELPER FUNCTIONS: AI VIDEO & AUDIO SYNTHESIS
# ==============================================================================
async def generate_speech(text: str, voice: str, output_file: str):
    """Generates audio file using Microsoft's Free Edge-TTS engine."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def generate_ai_visual_video(topic: str, api_key: str) -> str:
    """Calls an AI video model on Replicate to create a viral visual background video."""
    os.environ["REPLICATE_API_TOKEN"] = api_key
    
    # Prompt optimized for high-retention viral aesthetic
    prompt = f"Vertical 9:16 cinematic stock footage background visualizing: {topic}, futuristic tech aesthetic, glowing neon cyan lights, high-end wealth dashboard, 4k resolution, smooth motion."
    
    # Using a fast, high-quality video generation model via Replicate
    output = replicate.run(
        "minimax/video-01",
        input={
            "prompt": prompt,
            "prompt_optimizer": True
        }
    )
    
    # Download the generated video file from the cloud URL
    video_url = str(output)
    response = requests.get(video_url)
    
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp_file.write(response.content)
    tmp_file.close()
    return tmp_file.name

# ==============================================================================
# 3. MAIN APPLICATION CONTROLLER
# ==============================================================================
topic_input = st.text_input(
    "💡 Enter Video Topic / Concept:", 
    "Top 3 AI financial tracking tools automating wealth in 2026"
)

if st.button("🚀 Generate AI Visual Short"):
    if not replicate_api_key:
        st.error("Please provide your Replicate API key in the sidebar to generate AI visuals.")
    elif not topic_input.strip():
        st.error("Please enter a video topic.")
    else:
        status = st.status("⚡ Generating AI Visual Video...", expanded=True)
        
        try:
            # Step 1: Generate AI Visual Background
            status.write("🧠 AI is visualizing and rendering cinematic background scenes...")
            ai_video_path = generate_ai_visual_video(topic_input, replicate_api_key)

            # Step 2: Generate Voiceover
            status.write("🎙️ Synthesizing high-retention voiceover track...")
            script_text = f"Stop scrolling. Here is everything you need to know about {topic_input}. Link in bio to start."
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                audio_path = tmp_audio.name
            
            asyncio.run(generate_speech(script_text, selected_voice, audio_path))
            
            status.update(label="✅ AI Viral Video Ready!", state="complete")

            st.subheader("📺 AI Visual Preview")
            st.video(ai_video_path)
            
            with open(ai_video_path, "rb") as file:
                st.download_button(
                    label="📥 Download Viral AI Short (.mp4)",
                    data=file,
                    file_name="fintech_pulse_viral_ai.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            status.update(label="❌ Error generating AI video", state="error")
            st.error(f"Error details: {e}")
