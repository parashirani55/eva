import os
import requests
from flask import Flask, request, send_file, Response
from dotenv import load_dotenv
from pydub import AudioSegment
import openai
import uuid
import logging
from requests.auth import HTTPBasicAuth

load_dotenv()

print("LOADED TWILIO SID:", os.getenv("TWILIO_ACCOUNT_SID"))
print("LOADED TWILIO TOKEN:", os.getenv("TWILIO_AUTH_TOKEN"))

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")
PUBLIC_HOST = os.getenv("PUBLIC_HOST")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

conversation_history = [
    {
        "role": "system",
        "content": "You are a helpful AI service advisor coach who helps front desk staff deal with customers in real-time."
    }
]

@app.route("/voice", methods=["POST"])
def voice():
    greeting_text = "Hello, please describe the customer interaction."
    return generate_twiml_response(greeting_text, filename="greeting.mp3")

@app.route("/process_recording", methods=["POST"])
def process_recording():
    try:
        recording_url = request.form["RecordingUrl"] + ".mp3"
        audio_response = requests.get(
            recording_url,
            auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        )

        # Validate Twilio response is actually audio
        if "audio" not in audio_response.headers.get("Content-Type", ""):
            logging.error(f"Invalid audio file from Twilio: {audio_response.text}")
            return Response("<Response><Say>There was a problem receiving the audio. Please try again.</Say><Record action=\"{0}/process_recording\" method=\"POST\" maxLength=\"30\" /></Response>".format(PUBLIC_HOST), mimetype="text/xml")

        # Save to file
        audio_id = uuid.uuid4()
        audio_mp3 = f"call_{audio_id}.mp3"
        audio_wav = f"call_{audio_id}.wav"

        with open(audio_mp3, "wb") as f:
            f.write(audio_response.content)

        try:
            audio = AudioSegment.from_file(audio_mp3, format="mp3")
            audio.export(audio_wav, format="wav")
        except Exception as e:
            logging.error(f"Failed to convert audio: {e}")
            return Response("<Response><Say>Sorry, I couldn't understand the audio.</Say><Record action=\"{0}/process_recording\" method=\"POST\" maxLength=\"30\" /></Response>".format(PUBLIC_HOST), mimetype="text/xml")

        with open(audio_wav, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        user_text = transcript.text.strip()
        logging.debug(f"User said: {user_text}")

        if "goodbye" in user_text.lower():
            return Response("<Response><Say>Goodbye!</Say><Hangup/></Response>", mimetype="text/xml")

        conversation_history.append({"role": "user", "content": user_text})

        chat_response = client.chat.completions.create(
            model="gpt-4",
            messages=conversation_history
        )

        ai_reply = chat_response.choices[0].message.content.strip()
        logging.debug(f"AI reply: {ai_reply}")

        conversation_history.append({"role": "assistant", "content": ai_reply})

        return generate_twiml_response(ai_reply)

    except Exception as e:
        logging.error(f"Error in /process_recording: {e}")
        return Response(f"<Response><Say>Error: {str(e)}</Say></Response>", mimetype="text/xml")

@app.route("/greeting", methods=["GET"])
def greeting():
    return send_file("greeting.mp3", mimetype="audio/mpeg")

@app.route("/playback", methods=["GET"])
def playback():
    return send_file("response.mp3", mimetype="audio/mpeg")

def generate_twiml_response(text, filename="response.mp3"):
    try:
        tts_response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}",
            headers={
                "xi-api-key": ELEVEN_LABS_API_KEY,
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

        if tts_response.status_code != 200:
            logging.error(f"TTS Error: {tts_response.text}")
            return Response(f"<Response><Say>Error: {tts_response.text}</Say></Response>", mimetype="text/xml")

        with open(filename, "wb") as f:
            f.write(tts_response.content)

        return Response(f"""
            <Response>
                <Play>{PUBLIC_HOST}/playback</Play>
                <Record action="{PUBLIC_HOST}/process_recording" method="POST" maxLength="30" />
            </Response>
        """, mimetype="text/xml")

    except Exception as e:
        logging.error(f"Error generating TTS: {e}")
        return Response(f"<Response><Say>Error generating TTS: {str(e)}</Say></Response>", mimetype="text/xml")

if __name__ == "__main__":
    app.run(debug=True)
