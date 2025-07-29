import os
from pydantic import Field
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.transcriber.base_transcriber import BaseAsyncTranscriber
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage

from openai import OpenAI

class WhisperTranscriberConfig(TranscriberConfig):
    transcriber_type: str = Field("whisper_openai", alias="type")
    api_key: str = os.getenv("OPENAI_API_KEY")
    sampling_rate: int = 16000
    audio_encoding: AudioEncoding = AudioEncoding.LINEAR16
    chunk_size: int = 512

    class Config:
        allow_population_by_field_name = True

class WhisperTranscriber(BaseAsyncTranscriber[WhisperTranscriberConfig]):
    def __init__(self, transcriber_config: WhisperTranscriberConfig):
        super().__init__(transcriber_config)
        self.api_key = transcriber_config.api_key
        self.client = OpenAI(api_key=self.api_key)

    async def create_message_from_audio(self, chunk: bytes) -> BaseMessage:
        print("[WHISPER] Received audio chunk")
        try:
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=(b"chunk.wav", chunk, "audio/wav")
            )
            print(f"[WHISPER] Transcription: {response.text}")
            return BaseMessage(text=response.text)
        except Exception as e:
            print(f"[WHISPER ERROR] {e}")
            return BaseMessage(text="[transcription error]")

    def get_encoding(self) -> AudioEncoding:
        return AudioEncoding.LINEAR16

    def get_sampling_rate(self) -> int:
        return 16000
    def get_chunk_size(self) -> int:
        return