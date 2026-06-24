import datetime

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import sys
import os
import asyncio
import atexit
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from voice.tts_edge import generate, REVERB_FILE

from brain.orchestrator_agent import oracle
from brain.utilities.system_processes import run_system_processes_background
from quality_check.latency_check import set_tracer, trace

# MEMORY
from memories.conversation_manager import manage_conversation
from memories.memory_manager import append_memory

conversation_history = []

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

set_tracer(lambda text, final: socketio.emit('trace', {'text': text, 'final': final}))

def broadcast(role: str, text: str):
    socketio.emit('new_message', {'role': role, 'text': text})

def llm(prompt: str, history: list) -> tuple[str, list]:
    print("\n--- MESSAGE HISTORY ---")
    for msg in history:
        print(msg)
    print("--- END ---\n")
    t = time.perf_counter()
    result = asyncio.run(oracle.run(prompt, message_history=history))
    trace(f"⏱ total  {time.perf_counter() - t:.2f}s  |  {result.usage().total_tokens or 0} tokens", final=True)
    return result.output, result.new_messages()

# @app.route('/voice', methods=['POST'])
# def handle_voice():
#     global conversation_history
#     data = request.get_json()
#     transcript = data.get('text', '')
#
#     broadcast('user', transcript)
#     response_text, new_messages = llm(transcript, conversation_history)
#
#     conversation_history = manage_conversation(conversation_history, new_messages)
#
#     broadcast('assistant', response_text)
#
#     try:
#         generate(response_text)
#     except Exception as e:
#         print(f"[TTS ERROR] {e}")
#         return jsonify({'error': str(e)}), 500
#
#     return send_file(REVERB_FILE, mimetype='audio/mpeg')

@app.route('/chat', methods=['POST'])
def handle_chat():
    global conversation_history
    data = request.get_json()
    text = data.get('text', '')

    broadcast('user', text)
    response_text, new_messages = llm(text, conversation_history)

    conversation_history = manage_conversation(conversation_history, new_messages)

    broadcast('assistant', response_text)

    return jsonify({'status': 'ok'})


def _save_session():
    entry = f"\n## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\nSession ended."
    append_memory("sessions.md", entry)

if __name__ == '__main__':
    # RUN SYSTEM PROCESSES
    run_system_processes_background()

    atexit.register(_save_session)
    # user_reload is set to False to prevent the app from running twice in debug mode, which causes interaction time to be registered twice in episodic memory and thus causes confusion for the assistant.
    socketio.run(app, host='localhost', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
