import os
import requests
import logging

ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

def handle_scenario():
    scenario_text = "Hi, I’ve never been there before. My check engine light just came on. What do I need to do?"
    logging.debug("🎭 Sending scenario TTS request")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVEN_LABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": scenario_text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
    )

    if response.status_code == 200:
        with open("scenario.mp3", "wb") as f:
            f.write(response.content)
        logging.debug("✅ Scenario TTS saved as scenario.mp3")
        return "scenario.mp3"
    else:
        logging.error(f"❌ ElevenLabs TTS error during scenario: {response.text}")
        return None
