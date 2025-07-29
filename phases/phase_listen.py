import os
import logging
import openai
import requests
import uuid
from dotenv import load_dotenv
from pydub import AudioSegment
from twilio.rest import Client

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

client = openai.OpenAI(api_key=OPENAI_API_KEY)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def record_and_transcribe(call_sid):
    logging.debug(f"🎙 Fetching recording for call: {call_sid}")

    recordings = twilio_client.recordings.list(call_sid=call_sid)
    if not recordings:
        logging.error("❌ No recordings found for this call SID.")
        return None

    latest_recording = recordings[0]
    recording_url = f"https://api.twilio.com{latest_recording.uri.replace('.json', '.mp3')}"
    recording_sid = latest_recording.sid
    response = requests.get(recording_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    mp3_filename = f"call_{str(uuid.uuid4())}.mp3"
    wav_filename = mp3_filename.replace(".mp3", ".wav")

    with open(mp3_filename, "wb") as f:
        f.write(response.content)
    logging.debug(f"📥 Saved recording as {mp3_filename}")

    sound = AudioSegment.from_mp3(mp3_filename)
    sound.export(wav_filename, format="wav")
    logging.debug(f"🔊 Converted MP3 to WAV: {wav_filename}")

    with open(wav_filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    logging.debug(f"📝 Transcription result: {transcript.text}")

    return transcript.text
