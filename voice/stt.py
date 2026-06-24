from RealtimeSTT import AudioToTextRecorder

def start_listening(on_transcription):
    print("Listening... (speak now)")

    recorder = AudioToTextRecorder()

    while True:
        recorder.text(on_transcription)