import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from vonage_voice import Input, Speech, Stream
from openai import OpenAI
 
# Load environment variables
load_dotenv()
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 3000))
PLAYBOOK_FILE = os.getenv("PLAYBOOK_FILE")
 
# Set up the OpenAI client
openai_client = OpenAI()
 
# Load the company playbook
with open(PLAYBOOK_FILE) as f:
    PLAYBOOK = f.read()
 
# Create the folders our audio and transcripts are saved to
os.makedirs("audio", exist_ok=True)
os.makedirs("transcripts", exist_ok=True)
 
# Create Flask app
app = Flask(__name__)
 
# Keep track of each call, keyed by conversation ID
calls = {}
 
GREETING = ("Hello, thanks for calling customer support. "
            "Please tell me what information you're looking for.")
 
SYSTEM_PROMPT = (
    "You are a customer support agent on a live phone call. Answer the "
    "customer's question using only the company playbook below. If the "
    "playbook doesn't cover it, say so and offer to pass them to a "
    "human. Keep your answers conversational and under 50 words, since "
    "they'll be read out loud over the phone."
    "\n\nPLAYBOOK:\n" + PLAYBOOK)
 
 
def speak(text):
    speech = openai_client.audio.speech.create(
        model="gpt-4o-mini-tts", voice="alloy", input=text)
    filename = uuid.uuid4().hex + ".mp3"
    with open("audio/" + filename, "wb") as f:
        f.write(speech.content)
    stream = Stream(streamUrl=[BASE_URL + "/audio/" + filename])
    return stream.model_dump(exclude_none=True, mode="json")
 
 
def listen(call_uuid):
    listen_for = Input(
        type=["speech"],
        speech=Speech(uuid=[call_uuid], language="en-US", endOnSilence=2),
        eventUrl=[BASE_URL + "/webhooks/asr"])
    return listen_for.model_dump(exclude_none=True, mode="json")
 
 
@app.route("/audio/<filename>", methods=["GET"])
def audio(filename):
    return send_from_directory("audio", filename)
 
 
@app.route("/webhooks/answer", methods=["GET"])
def answer():
    calls[request.args.get("conversation_uuid")] = {
        "caller": request.args.get("from"),
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "assistant", "content": GREETING}],
    }
    return jsonify([speak(GREETING), listen(request.args.get("uuid"))])
 
 
@app.route("/webhooks/asr", methods=["POST"])
def asr():
    data = request.get_json()
    results = data.get("speech", {}).get("results")
 
    # If we didn't hear anything, ask the caller to try again
    if not results:
        return jsonify([speak("Sorry, I didn't catch that."),
                        listen(data["uuid"])])
 
    # Add what the caller said to this call's history
    messages = calls[data["conversation_uuid"]]["messages"]
    messages.append({"role": "user", "content": results[0]["text"]})
 
    # Ask OpenAI how to resolve it
    completion = openai_client.chat.completions.create(
        model="gpt-5-mini", messages=messages)
    reply = completion.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})
 
    return jsonify([speak(reply), listen(data["uuid"])])
 
 
def save_transcript(call):
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    with open("transcripts/" + filename, "w") as f:
        f.write("Caller: " + call["caller"] + "\n\n")
        for message in call["messages"][1:]:
            speaker = "CALLER" if message["role"] == "user" else "AGENT"
            f.write(speaker + ": " + message["content"] + "\n")
 
 
@app.route("/webhooks/event", methods=["POST"])
def event():
    data = request.get_json()
    conversation = data["conversation_uuid"]
    if data.get("status") == "completed" and conversation in calls:
        save_transcript(calls.pop(conversation))
    return ("", 204)
 
 
if __name__ == "__main__":
    app.run(port=PORT)
