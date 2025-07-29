import os
import logging
import openai
import requests
from datetime import datetime

# Empowered Advisor Call Guide for grading
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

def handle_phase(user_input):
    logging.debug("📊 Phase: Evaluate")

    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        eleven_api_key = os.getenv("ELEVEN_LABS_API_KEY")
        eleven_voice_id = os.getenv("ELEVEN_LABS_VOICE_ID")

        # Grade the response
        system_prompt = (
            "You are a call coach grading a service advisor using the following call guide:\n\n" + EA_CALL_GUIDE
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the full advisor response: {user_input}"}
        ]

        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )

        feedback = response.choices[0].message.content.strip()
        logging.debug(f"📝 Evaluation:\n{feedback}")

        # Save evaluation to file for records
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"evaluation_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(feedback)

        # Convert feedback to speech
        tts_response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}",
            headers={
                "xi-api-key": eleven_api_key,
                "Content-Type": "application/json"
            },
            json={
                "text": feedback,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
            }
        )

        if tts_response.status_code != 200:
            logging.error(f"❌ TTS error: {tts_response.text}")
            return None

        with open("response.mp3", "wb") as f:
            f.write(tts_response.content)

        return "response.mp3"

    except Exception as e:
        logging.error(f"❌ Error in phase_evaluate: {e}")
        return None
