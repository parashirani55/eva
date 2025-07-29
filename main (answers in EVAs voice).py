import os
from dotenv import load_dotenv

from vocode.streaming.models.telephony import TwilioConfig, TwilioCallConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.telephony.server.base import TelephonyServer
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
import uvicorn

# Load environment variables
load_dotenv()

# Setup synthesizer
synthesizer_config = ElevenLabsSynthesizerConfig(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
    voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
    sampling_rate=24000,
    audio_encoding=AudioEncoding.LINEAR16,
)

# Setup transcriber
transcriber_config = DeepgramTranscriberConfig(
    api_key=os.getenv("DEEPGRAM_API_KEY"),
    sampling_rate=16000,
    audio_encoding=AudioEncoding.LINEAR16,
    chunk_size=512,
    model="phonecall",
    tier="nova"
)

# Setup agent
agent_config = ChatGPTAgentConfig(
    initial_message=BaseMessage(text="Hi, this is EVA. Are you ready to test your incoming call skills?"),
    prompt_preamble="You are EVA, the Empowered Voice Assistant. You help service advisors practice phone skills.",
    temperature=0.5,
)

# Setup Twilio config
twilio_config = TwilioConfig(
    account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
    auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
)

# Setup Twilio call config
twilio_call_config = TwilioCallConfig(
    twilio_config=twilio_config,
    twilio_sid=os.getenv("TWILIO_SID"),
    from_phone=os.getenv("FROM_PHONE"),
    to_phone=os.getenv("TO_PHONE"),
    agent_config=agent_config,
    transcriber_config=transcriber_config,
    synthesizer_config=synthesizer_config,
    direction="inbound"
)

# Set up the config manager
config_manager_instance = InMemoryConfigManager()
config_manager_instance.configs[os.getenv("FROM_PHONE")] = twilio_call_config

# Create the TelephonyServer
telephony_server = TelephonyServer(
    base_url=os.getenv("PUBLIC_HOST"),
    config_manager=config_manager_instance,
)

# Create FastAPI app
app = FastAPI()

# Mount /static to serve audio files
app.mount("/static", StaticFiles(directory="."), name="static")

# Mount Vocode router
app.include_router(telephony_server.get_router(), prefix="/v1/telephony")

# Inbound route that returns TwiML to play ElevenLabs greeting
@app.post("/v1/telephony/inbound_call")
async def inbound_call(request: Request):
    print("📞 Inbound call received!")

    greeting_url = f"{os.getenv('PUBLIC_HOST')}/static/greeting.mp3"

    twiml_response = f"""
    <Response>
        <Play>{greeting_url}</Play>
        <Pause length="1" />
        <Say voice="alice">Thank you, goodbye.</Say>
        <Hangup/>
    </Response>
    """
    return Response(content=twiml_response.strip(), media_type="application/xml")

# Run app
if __name__ == "__main__":
    print("Mounted routes:")
    for route in app.routes:
        print(route.path)
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=False)
