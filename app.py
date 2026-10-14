import os
import asyncio
import tempfile
import streamlit as st
import edge_tts
from moviepy.editor import (
    TextClip,
    ColorClip,
    CompositeVideoClip,
    AudioFileClip
)

# ==============================================================================
# 1. STREAMLIT APP CONFIGURATION & BRANDING
# ==============================================================================
st.set_page_config(
    page_title="Fintech Pulse Studio",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Mobile-Optimized Neon/Dark CSS Theme
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

# App Header
st.markdown("<h1 class='main-title'>⚡ FINTECH PULSE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Free Automated High-RPM Short Video Engine</p>", unsafe_allow_html=True)

# Sidebar Configuration (No API Key Required!)
st.sidebar.header("⚙️ Pipeline Setup")
selected_voice = st.sidebar.selectbox(
    "Voice Actor",
    ["en-US-ChristopherNeural", "en-US-EricNeural", "en-US-JennyNeural"],
    index=0
)
bg_color_hex = st.sidebar.color_picker("Background Color", "#0d1117")

# ==============================================================================
# 2. HELPER FUNCTIONS: TTS & VIDEO GENERATION
# ==============================================================================
async def generate_speech(text: str, voice: str, output_file: str):
    """Generates audio file using Microsoft's Free Edge-TTS engine."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def create_short_video(script_text: str, audio_path: str, output_path: str, bg_hex: str):
    """Renders a 1080x1920 vertical video with animated dynamic captions."""
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    # Background Canvas (1080x1920 Vertical format)
    bg_clip = ColorClip(size=(1080, 1920), color=[13, 17, 23], duration=duration)
    
    # Text Overlays
    words = script_text.split()
    chunk_size = 4
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    
    text_clips = []
    chunk_duration = duration / len(chunks) if chunks else duration
    
    for idx, chunk in enumerate(chunks):
        start_t = idx * chunk_duration
        
        txt_clip = (TextClip(
                        chunk.upper(), 
                        fontsize=65, 
                        color='#00F0FF', 
                        font='Arial-Bold',
                        method='caption',
                        size=(900, None)
                    )
                    .set_position(('center', 'center'))
                    .set_start(start_t)
                    .set_duration(chunk_duration))
        text_clips.append(txt_clip)

    # Channel Watermark Branding
    watermark = (TextClip(
                    "⚡ FINTECH PULSE", 
                    fontsize=35, 
                    color='#ffffff', 
                    font='Arial-Bold'
                )
                .set_position(('center', 250))
                .set_duration(duration))

    # Composite & Render Output
    final_clip = CompositeVideoClip([bg_clip, watermark] + text_clips)
    final_clip = final_clip.set_audio(audio_clip)
    
    final_clip.write_videofile(
        output_path, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac',
        preset='ultrafast',
        threads=4
    )
    
    audio_clip.close()
    final_clip.close()

# ==============================================================================
# 3. MAIN APPLICATION CONTROLLER (KEYLESS & FREE)
# ==============================================================================
script_input = st.text_area(
    "💡 Enter or Paste Your Video Script:", 
    "Stop scrolling if you want to automate your wealth in 2026. These three fintech tools manage your money on autopilot so you don't have to lift a finger. Link in bio to start."
)

if st.button("🚀 Render Short Video"):
    if not script_input.strip():
        st.error("Please enter a script to render.")
    else:
        status = st.status("⚡ Generating Free Video...", expanded=True)
        
        try:
            # Step 1: Voiceover Synthesis (Free Edge-TTS)
            status.write("🎙️ Synthesizing voiceover track...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                audio_path = tmp_audio.name
            
            asyncio.run(generate_speech(script_input, selected_voice, audio_path))

            # Step 2: Video Assembly & Rendering
            status.write("🎬 Rendering 1080x1920 vertical video & burning neon captions...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                video_path = tmp_video.name
                
            create_short_video(script_input, audio_path, video_path, bg_color_hex)
            
            status.update(label="✅ Video Render Complete!", state="complete")

            # Step 3: Preview & Download
            st.subheader("📺 Video Preview")
            st.video(video_path)
            
            with open(video_path, "rb") as file:
                st.download_button(
                    label="📥 Download Ready Short (.mp4)",
                    data=file,
                    file_name="fintech_pulse_short.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            status.update(label="❌ Error generating video", state="error")
            st.error(f"Error details: {e}")
