import os
import requests
import logging

ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

def handle_greeting():
    greeting_text = "Hi, this is Eva. Are you ready to test your incoming call skills?"
    logging.debug("Sending greeting TTS request")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVEN_LABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": greeting_text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
    )

    if response.status_code == 200:
        with open("greeting.mp3", "wb") as f:
            f.write(response.content)
        logging.debug("✅ Greeting TTS saved as greeting.mp3")
        return "greeting.mp3"
    else:
        logging.error(f"❌ ElevenLabs TTS error: {response.text}")
        return None
