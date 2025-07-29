import os
import json
import requests
from flask import Flask, request, send_file, Response
from dotenv import load_dotenv
from pydub import AudioSegment
import openai
import uuid
import logging
from twilio.rest import Client
import time

load_dotenv()

app = Flask(__name__)

# Enhanced logging to both console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("eva_debug.log"),
        logging.StreamHandler()
    ]
)

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")
PUBLIC_HOST = os.getenv("PUBLIC_HOST")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = openai.OpenAI(api_key=OPENAI_API_KEY)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Phase state persistence using JSON
PHASE_FILE = "session_state.json"

def load_phase():
    if not os.path.exists(PHASE_FILE):
        return "greeting"
    with open(PHASE_FILE, "r") as f:
        return json.load(f).get("phase", "greeting")

def save_phase(phase):
    with open(PHASE_FILE, "w") as f:
        json.dump({"phase": phase}, f)

# EA Call Guide for grading
EA_CALL_GUIDE = """
When answering incoming calls, follow these steps:

1. Greeting:
   - “Thank you for calling [shop name], this is [your name]. How may I help you?”
   - OR: “Thank you for calling [shop name], this is [your name]. I’m with a client, may I take your name and number and call you back?”

2. After the caller gives their reason:
   - “I can help you with that! What’s your name?”

3. After name:
   - “When was the last time we had your vehicle in, [name]?”
   - “How did you hear about us?”

4. Confirm caller ID number:
   - “The caller ID shows you’re calling from [number], is that the best number for you?”

5. Offer next available appointment:
   - “The next available day/time is...”

6. Verify info:
   - Confirm phone, email, and name spelling

7. Set expectations:
   - “Please plan to be here 5–10 minutes so we can get to know you and your vehicle.”

8. Confirm appointment details and transportation needs

9. Ask for additional work:
   - “What else can I do for you while the [vehicle] is here?”

10. Close the call:
   - “Thank you, [name]. My name is [your name] and I look forward to seeing you!”

Use this guide to grade the caller’s call-handling skills. Point out what they did well and what they missed.
"""

phase = "initial"

@app.route("/voice", methods=["POST"])
def voice():
    global phase
    phase = "initial"
    logging.debug(">>>>> /voice endpoint HIT — greeting should play")
    greeting_text = "Hi, this is Eva. Are you ready to test your incoming call skills?"
    return generate_twiml_response(greeting_text, filename="greeting.mp3", serve_path="/greeting_playback", record_after=True)

@app.route("/greeting_playback", methods=["GET"])
def greeting_playback():
    logging.debug("Serving greeting.mp3 from /greeting_playback")
    return send_file("greeting.mp3", mimetype="audio/mpeg")

@app.route("/playback", methods=["GET"])
def playback():
    logging.debug("Serving response.mp3 from /playback endpoint")
    return send_file("response.mp3", mimetype="audio/mpeg")

@app.route("/process_recording", methods=["POST"])
def process_recording():
    global phase
    try:
        recording_url = request.form["RecordingUrl"]
        recording_sid = recording_url.strip().split("/")[-1]

        # Fetch audio from Twilio
        recording = twilio_client.recordings(recording_sid).fetch()
        media_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
        audio_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

        if "audio" not in audio_response.headers.get("Content-Type", ""):
            logging.error(f"Invalid audio file: {audio_response.text}")
            return Response("<Response><Say>There was a problem receiving the audio.</Say></Response>", mimetype="text/xml")

        audio_id = uuid.uuid4()
        audio_mp3 = f"call_{audio_id}.mp3"
        audio_wav = f"call_{audio_id}.wav"

        with open(audio_mp3, "wb") as f:
            f.write(audio_response.content)

        audio = AudioSegment.from_file(audio_mp3, format="mp3")
        audio.export(audio_wav, format="wav")

        with open(audio_wav, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        user_text = transcript.text.strip()
        logging.debug(f"User said: {user_text}")

        if phase == "initial" and "yeah" in user_text.lower():
            phase = "ring"
            return generate_twiml_response("Ring ring", filename="response.mp3", serve_path="/playback", record_after=True)

        if phase == "ring":
            phase = "scenario"
            scenario = "Hi, I’ve never been there before. My check engine light just came on. What do I need to do?"
            return generate_twiml_response(scenario, filename="response.mp3", serve_path="/playback", record_after=True)

        if "goodbye" in user_text.lower():
            time.sleep(10)
            phase = "initial"

            chat_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are an expert call coach grading a service advisor's call skills using the following Empowered Advisor Call Guide:\n{EA_CALL_GUIDE}"},
                    {"role": "user", "content": f"Please evaluate this mock call intro: {user_text}"}
                ]
            )
            feedback = chat_response.choices[0].message.content.strip()
            logging.debug(f"Feedback: {feedback}")
            return generate_twiml_response(feedback)

        return generate_twiml_response("Thanks. Please continue.", record_after=True)

    except Exception as e:
        logging.error(f"Error in /process_recording: {e}")
        return Response(f"<Response><Say>Error: {str(e)}</Say></Response>", mimetype="text/xml")

def generate_twiml_response(text, filename="response.mp3", serve_path="/playback", record_after=False):
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

        logging.debug(f"TTS audio saved as {filename}")

        if record_after:
            return Response(f"""
                <Response>
                    <Play>{PUBLIC_HOST}{serve_path}</Play>
                    <Record action="{PUBLIC_HOST}/process_recording" method="POST" maxLength="30" />
                </Response>
            """, mimetype="text/xml")
        else:
            return Response(f"""
                <Response>
                    <Play>{PUBLIC_HOST}{serve_path}</Play>
                    <Hangup />
                </Response>
            """, mimetype="text/xml")

    except Exception as e:
        logging.error(f"Error generating TTS: {e}")
        return Response(f"<Response><Say>Error: {str(e)}</Say></Response>", mimetype="text/xml")

if __name__ == "__main__":
    app.run(debug=True)
