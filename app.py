import os
import asyncio
import tempfile
import subprocess
import streamlit as st
import edge_tts

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
    .script-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 8px;
        font-size: 1.1rem;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>⚡ FINTECH PULSE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>High-RPM Viral Short Video Monetization Engine</p>", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.header("⚙️ Channel Settings")
selected_voice = st.sidebar.selectbox(
    "Voice Actor",
    ["en-US-ChristopherNeural", "en-US-EricNeural", "en-US-JennyNeural"],
    index=0
)
cta_text = st.sidebar.text_input("Call to Action (Watermark)", "LINK IN BIO TO START")

# ==============================================================================
# 2. HELPER FUNCTIONS: CRASH-PROOF RENDERER
# ==============================================================================
async def generate_speech(text: str, voice: str, output_file: str):
    """Generates voiceover using Microsoft's Free Edge-TTS engine."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def compile_viral_short(audio_path: str, output_path: str):
    """Renders 1080x1920 vertical background canvas with synchronized audio track cleanly."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0x0d1117:s=1080x1920:r=24",
        "-i", audio_path,
        "-shortest",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True)

# ==============================================================================
# 3. MAIN APPLICATION CONTROLLER
# ==============================================================================
script_input = st.text_area(
    "💡 Enter Viral Hook Script:", 
    "Stop scrolling if you want to automate your wealth in 2026. These three fintech tools manage your money on autopilot so you don't have to lift a finger."
)

if st.button("🚀 Render Monetization Short"):
    if not script_input.strip():
        st.error("Please enter a script.")
    else:
        status = st.status("⚡ Compiling Viral Short Package...", expanded=True)
        
        try:
            status.write("🎙️ Synthesizing high-retention voiceover...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                audio_path = tmp_audio.name
            asyncio.run(generate_speech(script_input, selected_voice, audio_path))

            status.write("🎬 Assembling high-definition vertical video package...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                video_path = tmp_video.name
                
            compile_viral_short(audio_path, video_path)
            
            status.update(label="✅ Viral Short Ready!", state="complete")

            st.subheader("📺 Short Preview")
            st.video(video_path)
            
            st.markdown(f"""
            <div class="script-box">
                <b>⚡ Active Script Caption:</b><br>{script_input}<br><br>
                <span style="color: #00F0FF; font-weight: bold;">🎯 Watermark / CTA:</span> {cta_text}
            </div>
            """, unsafe_allow_html=True)
            
            with open(video_path, "rb") as file:
                st.download_button(
                    label="📥 Download Ready Short (.mp4)",
                    data=file,
                    file_name="fintech_pulse_monetization_short.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            status.update(label="❌ Error generating video", state="error")
            st.error(f"Error details: {e}")
