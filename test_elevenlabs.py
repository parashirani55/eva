import requests
import os

API_KEY = "sk_a028d0de814db3a70daec708216206af66a58b45ae5beb91"
VOICE_ID = "yj30vwTGJxSHezdAGsv9"
text = "Hi, this is EVA. Are you ready to test your incoming call skills?"

response = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
    headers={
        "xi-api-key": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "text": text,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("✅ Audio saved to output.wav — play it to confirm")
else:
    print("❌ Error:", response.status_code, response.text)
