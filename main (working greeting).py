import os
import requests
from flask import Flask, request, send_file, Response
from dotenv import load_dotenv
from pydub import AudioSegment
import openai
import uuid
import logging
from twilio.rest import Client

load_dotenv()

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
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.route("/voice", methods=["POST"])
def voice():
    logging.debug(">>>>> /voice endpoint HIT — greeting should play")
    greeting_text = "Hello, please describe the customer interaction."
    return generate_twiml_response(greeting_text, filename="greeting.mp3", serve_path="/greeting_playback")

@app.route("/process_recording", methods=["POST"])
def process_recording():
    try:
        recording_url = request.form["RecordingUrl"]
        recording_sid = recording_url.strip().split("/")[-1]

        # Fetch the recording from Twilio
        recording = twilio_client.recordings(recording_sid).fetch()
        media_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
        audio_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

        if "audio" not in audio_response.headers.get("Content-Type", ""):
            logging.error(f"Invalid audio file: {audio_response.text}")
            return Response("<Response><Say>There was a problem receiving the audio.</Say></Response>", mimetype="text/xml")

        # Save audio
        audio_id = uuid.uuid4()
        audio_mp3 = f"call_{audio_id}.mp3"
        audio_wav = f"call_{audio_id}.wav"

        with open(audio_mp3, "wb") as f:
            f.write(audio_response.content)

        # Convert to WAV for Whisper
        audio = AudioSegment.from_file(audio_mp3, format="mp3")
        audio.export(audio_wav, format="wav")

        with open(audio_wav, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        user_text = transcript.text.strip()
        logging.debug(f"User said: {user_text}")

        if "goodbye" in user_text.lower():
            return Response("<Response><Say>Goodbye!</Say><Hangup/></Response>", mimetype="text/xml")

        # Get AI reply
        chat_response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI service advisor coach who helps front desk staff deal with customers in real-time."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        ai_reply = chat_response.choices[0].message.content.strip()
        logging.debug(f"AI reply: {ai_reply}")

        return generate_twiml_response(ai_reply)

    except Exception as e:
        logging.error(f"Error in /process_recording: {e}")
        return Response(f"<Response><Say>Error: {str(e)}</Say></Response>", mimetype="text/xml")

@app.route("/playback", methods=["GET"])
def playback():
    logging.debug("Serving response.mp3 from /playback endpoint")
    return send_file("response.mp3", mimetype="audio/mpeg")

@app.route("/greeting_playback", methods=["GET"])
def greeting_playback():
    logging.debug("Serving greeting.mp3 from /greeting_playback")
    return send_file("greeting.mp3", mimetype="audio/mpeg")

def generate_twiml_response(text, filename="response.mp3", serve_path="/playback"):
    try:
        logging.debug(f"Sending text to ElevenLabs: {text}")
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
            return Response(f"<Response><Say>Error generating voice. Message: {text}</Say></Response>", mimetype="text/xml")

        with open(filename, "wb") as f:
            f.write(tts_response.content)

        logging.debug("TTS audio saved as response.mp3")

        return Response(f"""
            <Response>
                <Play>{PUBLIC_HOST}{serve_path}</Play>
                <Record action="{PUBLIC_HOST}/process_recording" method="POST" maxLength="30" />
            </Response>
        """, mimetype="text/xml")

    except Exception as e:
        logging.error(f"Error generating TTS: {e}")
        return Response(f"<Response><Say>Error: {str(e)}</Say></Response>", mimetype="text/xml")

if __name__ == "__main__":
    app.run(debug=True)
