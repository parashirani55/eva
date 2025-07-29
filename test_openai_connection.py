from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()  # 👈 This line loads your .env file

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Say hello"}],
    temperature=0,
)

print(response.choices[0].message.content)
