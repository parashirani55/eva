from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.transcript import Transcript
import asyncio
import time
import logging
import os
from typing_extensions import Literal
from pydantic import Field


class EVAAgentConfig(AgentConfig):
    agent_type: Literal["custom_eva"] = Field("custom_eva", alias="type")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            str: lambda v: v
        }


class EVAAgent(RespondAgent):
    def __init__(self, agent_config: EVAAgentConfig):
        super().__init__(agent_config)
        print("🧠 EVAAgent __init__ called")
        self.agent_config = agent_config
        self.transcript = []
        self.state = "GREETING"
        self.done = False
        self.last_response_time = time.time()

    def get_initial_message(self) -> BaseMessage:
        print("[EVA] get_initial_message() called")
        return BaseMessage(text="Hi, this is EVA. Are you ready to test your incoming call skills?")

    async def respond(self, message: BaseMessage) -> BaseMessage:
        print("[EVA] respond() triggered")
        user_input = message.text.strip()
        print(f"[EVA] Current state: {self.state}")
        print(f"[EVA] Received: {user_input}")
        self.transcript.append(f"Caller: {user_input}")
        self.last_response_time = time.time()

        if self.state == "GREETING":
            self.state = "RING"
            response = "Hi, this is EVA. Are you ready to test your incoming call skills?"
            print(f"[EVA] Responding: {response}")
            return BaseMessage(text=response)

        elif self.state == "RING":
            self.state = "SCENARIO"
            response = "Ring ring."
            print(f"[EVA] Responding: {response}")
            return BaseMessage(text=response)

        elif self.state == "SCENARIO":
            self.state = "ROLEPLAY"
            response = "Hi, I’ve never been there before. My check engine light just came on. What do I need to do?"
            print(f"[EVA] Responding: {response}")
            return BaseMessage(text=response)

        elif self.state == "ROLEPLAY":
            if "appointment" in user_input.lower():
                self.state = "THANK_YOU"
                response = "Thank you, goodbye."
                print(f"[EVA] Responding: {response}")
                return BaseMessage(text=response)
            else:
                response = "Can you help me understand what I need to do next?"
                print(f"[EVA] Responding: {response}")
                return BaseMessage(text=response)

        elif self.state == "THANK_YOU":
            self.state = "WAITING"
            self.done = True
            print("[EVA] Entering WAITING state with pause.")
            return BaseMessage(text="...")  # Silent pause before grading

        elif self.state == "WAITING":
            print("[EVA] Waiting 10 seconds before grading...")
            await asyncio.sleep(10)
            return await self.grade_transcript()

        return BaseMessage(text="...")

    async def grade_transcript(self) -> BaseMessage:
        response = "Thanks for completing the roleplay! You did a great job. Keep practicing!"
        print(f"[EVA] Final Feedback: {response}")
        return BaseMessage(text=response)

    def should_continue(self):
        return not self.done

    def receive_handoff(self, transcript: Transcript):
        pass

    def get_config(self) -> EVAAgentConfig:
        return self.agent_config
