import edge_tts, asyncio, pygame, time, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from voice.effects import apply_reverb

#   │ en-US-DavisNeural       │ American │ Deep, mature, confident
#   ├─────────────────────────┼──────────┼───────────────────────────
#   │ en-GB-RyanNeural        │ British  │ Rich, deep, authoritative
#   ├─────────────────────────┼──────────┼───────────────────────────
#   │ en-US-ChristopherNeural │ American │ Clear, deep, mid-age

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_edge_output.mp3")
REVERB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_edge_output_reverb.mp3")

_oracle = get_oracle()
VOICE = _oracle["voice"]
REVERB_SETTINGS = _oracle["reverb"]

async def _generate(text: str):
    communicate = edge_tts.Communicate(text, voice=VOICE)
    await communicate.save(OUTPUT_FILE)

def generate(text: str):
    asyncio.run(_generate(text))
    apply_reverb(OUTPUT_FILE, REVERB_FILE, REVERB_SETTINGS)

def speak(text: str):
    generate(text)
    pygame.mixer.init()
    pygame.mixer.music.load(REVERB_FILE)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.quit()

if __name__ == "__main__":
      speak("Hello, I am your virtual assistant. How can I help you today?")