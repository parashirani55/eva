import openai
import os
import logging
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def evaluate_response(advisor_transcript, guide_text):
    logging.debug("🧠 Sending advisor transcript to GPT for evaluation...")

    prompt = f"""
You are a call coach grading a service advisor using the following call handling guide:

{guide_text}

The advisor said:

\"\"\"{advisor_transcript}\"\"\"

Please provide detailed, constructive feedback, including specific steps they followed or missed.
Conclude with an encouraging tone and summarize how they can improve next time.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a call coach grading a service advisor."},
            {"role": "user", "content": prompt}
        ]
    )

    feedback = response.choices[0].message.content.strip()
    logging.debug(f"🧠 Feedback from GPT: {feedback}")
    return feedback
