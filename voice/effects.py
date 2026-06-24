"""
This file is responsible for the followings:
- get generated audio from TTS
- apply audio effects to the generated audio
- save the processed audio to a file
"""

import numpy as np
from pedalboard import Pedalboard, Reverb, Chorus, Delay
from pedalboard.io import AudioFile

def apply_reverb(input_file: str, output_file: str, settings: dict):
    board = Pedalboard([
        Reverb(
            room_size=settings["room_size"],
            damping=settings["damping"],
            wet_level=settings["wet_level"],
            dry_level=settings["dry_level"],
            width=settings["width"],
        )
    ])

    with AudioFile(input_file) as f:
        audio = f.read(f.frames)
        sample_rate = f.samplerate

    processed = board(audio, sample_rate)

    with AudioFile(output_file, 'w', sample_rate, processed.shape[0]) as f:
        f.write(processed)


def mix_background(voice_path: str, music_path: str,
                   output_path: str, music_volume: float = 0.08):
    with AudioFile(voice_path) as f:
        voice = f.read(f.frames)
        sample_rate = f.samplerate

    with AudioFile(music_path) as f:
        music = f.read(f.frames)

    # if music is shorter than the voice, it loops it
    if music.shape[1] < voice.shape[1]:
        repeats = (voice.shape[1] // music.shape[1]) + 1
        music = np.tile(music, repeats)

    # trims music to voice length
    music = music[:, :voice.shape[1]]
    music = music * music_volume

    final = voice + music

    with AudioFile(output_path, 'w', sample_rate,
                   final.shape[0]) as f:
        f.write(final)



