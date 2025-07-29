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
from threading import Thread
import sys
import io

# Fix Unicode logging in Windows
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

from phases.phase_greeting import handle_greeting
from phases.phase_ring import handle_ring
from phases.phase_scenario import handle_scenario
from phases.phase_listen import record_and_transcribe
from phases.phase_evaluate import evaluate_response

load_dotenv()

app = Flask(__name__)

# Enhanced logging to both console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("eva_debug.log", encoding='utf-8'),
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

SESSION_FILE = "session_state.json"

def save_phase(phase):
    with open(SESSION_FILE, "w") as f:
        json.dump({"phase": phase}, f)

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
   - “The next available day/time is..."

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

@app.route("/voice", methods=["POST"])
def voice():
    logging.debug(">>>>> /voice endpoint HIT")

    # Force reset to greeting phase at the start of every call
    save_phase("greeting")
    phase = "greeting"

    if phase == "greeting":
        handle_greeting()
        return Response(f"""
        <Response>
            <Play>{PUBLIC_HOST}/greeting_playback</Play>
            <Pause length="1"/>
            <Record
                recordingStatusCallback="{PUBLIC_HOST}/recording_complete"
                recordingStatusCallbackMethod="POST"
                action="{PUBLIC_HOST}/process_greeting_reply"
                method="POST"
                maxLength="15"
                timeout="5"
                playBeep="false"
                record="record-from-answer-dual"
            />
        </Response>
        """, mimetype="text/xml")

    elif phase == "ring":
        handle_ring()
        save_phase("scenario")
        return Response(f"""
        <Response>
            <Play>{PUBLIC_HOST}/greeting_playback</Play>
        </Response>
        """, mimetype="text/xml")

    elif phase == "scenario":
        handle_scenario()
        save_phase("listen")
        return Response(f"""
        <Response>
            <Play>{PUBLIC_HOST}/greeting_playback</Play>
        </Response>
        """, mimetype="text/xml")

    elif phase == "listen":
        call_sid = request.form.get("CallSid")
        if not call_sid:
            logging.error("Missing CallSid in request")
            return Response("<Response><Say>There was a problem retrieving the recording.</Say></Response>", mimetype="text/xml")

        advisor_response = record_and_transcribe(call_sid)
        if not advisor_response:
            logging.error("❌ Transcription failed or no recording found.")
            return Response("<Response><Say>We couldn’t get your response. Please try again.</Say></Response>", mimetype="text/xml")

        with open("transcript.txt", "w", encoding="utf-8") as f:
            f.write(advisor_response)

        save_phase("evaluate")
        return Response("<Response></Response>", mimetype="text/xml")

    elif phase == "evaluate":
        with open("transcript.txt", "r", encoding="utf-8") as f:
            advisor_response = f.read()
        feedback = evaluate_response(advisor_response, EA_CALL_GUIDE)
        logging.debug("Sending feedback to ElevenLabs...")
        tts_response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}",
            headers={
                "xi-api-key": ELEVEN_LABS_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "text": feedback,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
        )
        if tts_response.status_code == 200:
            with open("feedback.mp3", "wb") as f:
                f.write(tts_response.content)
            logging.debug("✅ Feedback TTS saved as feedback.mp3")
            save_phase("greeting")
            return send_file("feedback.mp3")
        else:
            logging.error(f"Failed to generate feedback audio: {tts_response.text}")
            return Response("<Response><Say>There was a problem generating feedback.</Say></Response>", mimetype="text/xml")

    else:
        logging.error(f"Unexpected phase: {phase}")
        return Response("<Response><Say>We're sorry, an error has occurred.</Say></Response>", mimetype="text/xml")

@app.route("/process_greeting_reply", methods=["POST"])
def process_greeting_reply():
    call_sid = request.form.get("CallSid")
    if not call_sid:
        logging.error("Missing CallSid in greeting reply")
        return Response("<Response><Say>There was a problem.</Say></Response>", mimetype="text/xml")

    logging.debug("🔍 Processing greeting reply synchronously...")
    advisor_response = record_and_transcribe(call_sid)
    logging.debug(f"📝 Transcription result: {advisor_response}")

    if advisor_response and any(keyword in advisor_response.lower() for keyword in ["yes", "yeah", "ready", "go"]):
        logging.debug("✅ Valid confirmation received, proceeding to next phase")
        save_phase("ring")
        return Response("<Response><Redirect>/voice</Redirect></Response>", mimetype="text/xml")
    else:
        logging.warning(f"❌ Invalid or no response detected: {advisor_response}")
        return Response("<Response><Say>I didn’t catch that. Please try again.</Say><Redirect>/voice</Redirect></Response>", mimetype="text/xml")

@app.route("/recording_complete", methods=["POST"])
def recording_complete():
    recording_url = request.form.get("RecordingUrl")
    call_sid = request.form.get("CallSid")

    if recording_url and call_sid:
        logging.info(f"📼 Full call recording available: {recording_url}")
        try:
            time.sleep(2)  # Give Twilio time to finish processing
            response = requests.get(recording_url + ".mp3", auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            if response.status_code == 200:
                with open(f"full_call_{call_sid}.mp3", "wb") as f:
                    f.write(response.content)
            else:
                logging.error(f"Failed to download recording: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"Error downloading recording: {e}")
    else:
        logging.warning("Recording complete webhook received without URL or CallSid.")

    return Response("<Response></Response>", mimetype="text/xml")

@app.route("/greeting_playback")
def greeting_playback():
    logging.debug("Serving greeting.mp3 from /greeting_playback")
    return send_file("greeting.mp3")

@app.route("/playback")
def playback():
    logging.debug("Serving response.mp3 from /playback")
    return send_file("response.mp3")

if __name__ == "__main__":
    app.run(debug=True)
