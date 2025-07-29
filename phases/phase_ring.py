import os
import requests
import logging

ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

def handle_ring():
    ring_text = "Ring ring."
    logging.debug("🔔 Sending ring TTS request")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVEN_LABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": ring_text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
    )

    if response.status_code == 200:
        with open("ring.mp3", "wb") as f:
            f.write(response.content)
        logging.debug("✅ Ring TTS saved as ring.mp3")
        return "ring.mp3"
    else:
        logging.error(f"❌ ElevenLabs TTS error during ring: {response.text}")
        return None
