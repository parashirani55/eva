from fastapi import FastAPI
import uvicorn
import os
from vocode.streaming.telephony.server.base import TelephonyServer
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager
from vocode.streaming.models.telephony import TwilioConfig, TwilioCallConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from eva_agent import EVAAgentConfig
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager

class DynamicConfigManager(InMemoryConfigManager):
    async def get_config(self, conversation_id: str) -> TwilioCallConfig:
        print("[DynamicConfigManager] triggered for:", conversation_id)
        agent_config = EVAAgentConfig(type="custom_eva")
        return TwilioCallConfig(
            twilio_config=TwilioConfig(account_sid=os.environ["TWILIO_ACCOUNT_SID"]),
            from_phone=os.environ["FROM_PHONE"],
            to_phone=os.environ["TO_PHONE"],
            twilio_sid=os.environ.get("TWILIO_SID", "test-call-sid"),
            direction="inbound",
            agent_config=agent_config,
            synthesizer_config=ElevenLabsSynthesizerConfig(
                api_key=os.environ["ELEVENLABS_API_KEY"],
                voice_id=os.environ["ELEVENLABS_VOICE_ID"]
            ),
            transcriber_config=DeepgramTranscriberConfig(api_key=os.environ["DEEPGRAM_API_KEY"]),
        )

config_manager: BaseConfigManager = DynamicConfigManager()

telephony_server = TelephonyServer(
    base_url=os.environ["PUBLIC_HOST"],
    config_manager=config_manager,
)

app = FastAPI()
app.include_router(telephony_server.get_router())

if __name__ == "__main__":
    print("🚀 EVA server starting...")
    uvicorn.run(app, host="0.0.0.0", port=5000)
