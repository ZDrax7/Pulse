import os
import asyncio
import tempfile
import requests
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
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>⚡ FINTECH PULSE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Autonomous Free Stock & Audio Video Engine</p>", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.header("⚙️ Engine Settings")
# Optional free Pexels API key field (or it uses a reliable built-in fallback keyword search)
pexels_api_key = st.sidebar.text_input("Pexels API Key (Optional, for custom stock footage)", type="password")
selected_voice = st.sidebar.selectbox(
    "Voice Actor",
    ["en-US-ChristopherNeural", "en-US-EricNeural", "en-US-JennyNeural"],
    index=0
)

# ==============================================================================
# 2. HELPER FUNCTIONS: DYNAMIC CLIP FETCHING & TTS
# ==============================================================================
async def generate_speech(text: str, voice: str, output_file: str):
    """Generates voiceover using Microsoft's Free Edge-TTS engine."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def fetch_stock_video(query: str, api_key: str) -> str:
    """Automatically searches and downloads a matching free vertical stock video clip."""
    fallback_video_url = "https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-screens-with-financial-data-31910-large.mp4"
    
    if not api_key:
        # Use a high-quality free stock video stream directly if no API key is provided
        return fallback_video_url
        
    try:
        headers = {"Authorization": api_key}
        response = requests.get(
            f"https://api.pexels.com/v1/videos/search?query={query}&per_page=1&orientation=portrait",
            headers=headers
        )
        data = response.json()
        if "videos" in data and len(data["videos"]) > 0:
            # Grab the best HD download link
            video_files = data["videos"][0]["video_files"]
            hd_file = next((v for v in video_files if v.get("quality") == "hd"), video_files[0])
            return hd_file["link"]
    except Exception:
        pass
        
    return fallback_video_url

def compile_final_reel(video_url: str, audio_path: str, output_path: str):
    """Downloads background clip and merges with audio using FFmpeg."""
    # Download background video clip temporarily
    stock_clip_req = requests.get(video_url, stream=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_clip:
        for chunk in stock_clip_req.iter_content(chunk_size=8192):
            tmp_clip.write(chunk)
        stock_path = tmp_clip.name

    # FFmpeg processing: scale/crop to 9:16 vertical, map audio, and render
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", stock_path,
        "-i", audio_path,
        "-shortest",
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True)

# ==============================================================================
# 3. MAIN APPLICATION CONTROLLER
# ==============================================================================
script_input = st.text_area(
    "💡 Enter or Paste Your Video Script / Topic:", 
    "Stop scrolling if you want to automate your wealth in 2026. These three fintech tools manage your money on autopilot so you don't have to lift a finger. Link in bio to start."
)

if st.button("🚀 Render Autonomous Reel"):
    if not script_input.strip():
        st.error("Please enter a script or topic.")
    else:
        status = st.status("⚡ Generating Automated Reel...", expanded=True)
        
        try:
            status.write("🎙️ Synthesizing professional voiceover track...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                audio_path = tmp_audio.name
            asyncio.run(generate_speech(script_input, selected_voice, audio_path))

            status.write("🎬 Fetching matching financial visual clips & compiling video...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                video_path = tmp_video.name
                
            # Extract a keyword from script for stock search
            keyword = script_input.split()[0] if script_input else "finance"
            video_url = fetch_stock_video(keyword, pexels_api_key)
            
            compile_final_reel(video_url, audio_path, video_path)
            
            status.update(label="✅ Reel Rendered Successfully!", state="complete")

            st.subheader("📺 Reel Preview")
            st.video(video_path)
            
            with open(video_path, "rb") as file:
                st.download_button(
                    label="📥 Download Ready Reel (.mp4)",
                    data=file,
                    file_name="fintech_pulse_reel.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            status.update(label="❌ Error generating video", state="error")
            st.error(f"Error details: {e}")
