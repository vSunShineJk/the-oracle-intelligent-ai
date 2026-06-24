"""
This file does the followings:
- gets a text input
- send the text to ElevenLabs
- get an audio back
"""

import os
from dotenv import load_dotenv
from elevenlabs import save
from elevenlabs.client import ElevenLabs
import json
from datetime import datetime
import pygame
import time
from effects import apply_reverb, mix_background

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

LOG_FILE = os.path.join(os.path.dirname(__file__), "usage_log.json")
BACKGROUND_MUSIC = os.path.join(os.path.dirname(__file__),"background.mp3")
def log_usage(text: str):
    char_used = len(text)
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    else:
        log = []

    total_so_far = sum(entry["char_used"] for entry in log) + char_used

    log.append({
        "timestamp": datetime.now().isoformat(),
        "char_used": char_used,
        "total_so_far": total_so_far
    })

    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    print(f"Chars used this call: {char_used} | Total chars used so far: {total_so_far}")

def play(file_path: str):
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.quit()

def speak(text: str, voice_id: str = "8FxbOKOUKHQ2Dav54TlG"):

    log_usage(text)
    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
    )

    save(audio, "test_output.mp3")
    print("Audio saved as test_output.mp3")

    apply_reverb("test_output.mp3", "test_output_reverb.mp3")
    print("Reverb applied and saved as test_output_reverb.mp3")

    mix_background("test_output_reverb.mp3", BACKGROUND_MUSIC, "final_output.mp3")

    play("final_output.mp3")

speak(
    """ Maslow’s hierarchy of needs is one of those ideas that sounds simple on the surface but gets richer the deeper you go.

Most people picture it as a pyramid — five levels, bottom to top. But Maslow himself never drew that pyramid. It was a consulting psychologist named Charles McDermid who first depicted it that way. The image stuck because it captures the core idea so cleanly: the most fundamental needs sit at the base, and you work your way up only once the lower levels are reasonably satisfied.

The bottom layer is physiological needs — air, water, food, sleep, shelter. These are biological non-negotiables. Your body demands them before anything else gets attention. Above that comes safety — physical security, financial stability, health, a predictable environment. When safety is threatened, whether through war, poverty, or an unstable home, everything higher on the hierarchy gets pushed aside.

The third level is belonging. Humans are deeply social — we need to feel accepted, loved, and connected, whether through family, friendships, or community. Maslow noted that the absence of belonging leads to loneliness, anxiety, and depression. Interestingly, this need can sometimes override even safety — which explains why people stay in harmful relationships rather than face isolation.

Above belonging sits esteem — in two forms. The first is respect from others: recognition, status, attention. The second, which Maslow considered higher, is self-respect: confidence, competence, independence. Both matter, and they are more intertwined than sharply separated.

Then come cognitive needs — the drive to learn, understand, and stay curious. And aesthetic needs — the desire for beauty, order, and meaningful experience in daily life.

At the top sits self-actualization: becoming the most that you can be. For one person that means becoming a great parent. For another it is art, athletics, or building something lasting. Maslow later added a final layer — transcendence — going beyond yourself entirely, toward altruism, spirituality, or a sense of connection to something greater than your own life.

One important nuance: Maslow never said you must fully complete one level before the next activates. Multiple needs operate simultaneously. It is more about which need dominates at a given moment than a strict sequence.

The theory has critics — mainly for lacking rigorous empirical support. But it endures because it maps something true: we cannot chase meaning while starving, and we cannot build confidence while feeling fundamentally unsafe. The order matters.”””
"""
)