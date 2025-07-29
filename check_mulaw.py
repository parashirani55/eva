from pydub import AudioSegment
import audioop

audio = AudioSegment.from_file("greeting.mp3")
audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
raw_audio = audio.raw_data
mulaw_audio = audioop.lin2ulaw(raw_audio, 2)

print(f"✅ Original sample width: {audio.sample_width} bytes")
print(f"📦 Raw audio length: {len(raw_audio)} bytes")
print(f"📦 μ-law audio length: {len(mulaw_audio)} bytes")
print(f"🔍 First 10 bytes of μ-law: {mulaw_audio[:10]}")
