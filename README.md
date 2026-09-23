# Build an AI Voice Agent with Vonage and OpenAI

A small Flask app that answers your support line and talks with customers in real time.

A customer calls your support number and asks a question out loud. Vonage transcribes what they say and posts it to the app, OpenAI answers it against your company support playbook, and OpenAI's text-to-speech renders that answer as audio the caller hears back on the line. The conversation continues until they hang up, and the full transcript is saved to a text file.

## How it works

```
Customer call
      │
      ▼
/webhooks/answer ──► NCCO: Stream (greeting, in an OpenAI voice) + Input (speech)
      │
      ▼
Caller speaks; Vonage transcribes it
      │
      ▼
/webhooks/asr ──► OpenAI (gpt-5-mini) answers from playbook.txt
      │           └─► OpenAI TTS renders the reply to audio/<random>.mp3
      │
      ▼
NCCO: Stream (the reply) + Input ──► loops until the caller hangs up
      │
      ▼
/webhooks/event (status: completed) ──► save_transcript() writes transcripts/<timestamp>.txt
```

`/audio/<filename>` serves the generated MP3s so Vonage can fetch them. The whole conversation is held in memory, keyed by conversation ID, and sent to OpenAI on every turn so the agent can follow up questions.

## Prerequisites

- A Vonage API account
- An OpenAI API key
- Python 3
- ngrok (or any tunneling tool) so Vonage can reach your local webhooks

## Vonage setup

1. In the Vonage dashboard, go to **Build → Applications** and click **Create a new application**. Give it a name.
2. Click **Generate public and private key**. The private key downloads to your machine — keep it, though this app never uses it directly.
3. Under **Capabilities**, toggle on **Voice**. Fill the webhook fields with a placeholder like `example.com` for now; you'll come back to these.
4. Click **Generate new application**.
5. Under **Build → Phone Numbers**, get a virtual number and link it to your application. This is the number customers will call. If you're in the US, follow the additional steps to make your number 10DLC compliant.

This app never calls the Vonage API — Vonage calls it. All the traffic is inbound, so there are no Vonage credentials in the code and nothing to authenticate. The application and number still have to exist, which is what the steps above are for.

## Install

```bash
mkdir support-agent
cd support-agent
python3 -m venv venv && source venv/bin/activate
pip3 install vonage flask openai python-dotenv
```

| Package | Why |
| --- | --- |
| `vonage` | Vonage Python SDK — provides the `Stream`, `Input`, and `Speech` NCCO models |
| `flask` | Lightweight web framework for the webhook routes |
| `openai` | Answers the customer's question and generates the speaking voice |
| `python-dotenv` | Loads environment variables |

## Configuration

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_openai_api_key
PLAYBOOK_FILE=playbook.txt
PORT=3000
BASE_URL=
```

Start ngrok and paste the forwarding URL into `BASE_URL`:

```bash
ngrok http 3000
```

`BASE_URL` has to be a public HTTPS address. Vonage fetches every generated MP3 over the internet, so a localhost URL won't play anything.

## playbook.txt

The document OpenAI uses to decide how each issue should be resolved. Swap in your own — this is the demo version:

```
REFUNDS: Orders under $100 can be refunded right away. Orders over
$100 need manager approval before refunding.

SHIPPING: If a package is more than 5 days late, offer a replacement
or a full refund, and email the customer a tracking update.

ACCOUNT ACCESS: Send the customer a password reset link. Never change
account details over the phone.

ESCALATION: If the customer is upset or mentions legal action, set
the priority to High and assign a manager.

UNKNOWN: If an issue doesn't fit any of the categories above, set
the priority to High and leave the plan for an employee to decide.
```

## audio/ and transcripts/

Both folders are created automatically on startup. Generated speech lands in `audio/`, and one text file per call lands in `transcripts/`, named for the time the call ended:

```
Caller: 15551234567

AGENT: Hello, thanks for calling customer support. Please tell me what information you're looking for.
CALLER: my package never arrived
AGENT: I'm sorry about that. If it's more than five days late, I can offer a replacement or a full refund.
```

## Point Vonage at your webhooks

Back in your application's Voice capability settings, paste your ngrok forwarding URL into:

- **Answer URL** — `https://your-ngrok-url/webhooks/answer`
- **Event URL** — `https://your-ngrok-url/webhooks/event`

Click **Save changes**. There's no field for the ASR webhook — the app passes that URL to Vonage itself, inside the Input action.

## Run it

```bash
python3 app.py
```

The app starts on `localhost:3000` (or whatever `PORT` you set). Make sure ngrok is still running, then call your support number and ask a question. The agent answers out loud, remembers what you've already said, and saves the transcript once you hang up.

Expect a pause of a few seconds before each reply — the app waits for the full answer from OpenAI, then for the audio to be generated, before anything plays. Keeping the agent's answers short is the simplest way to shrink it.

## Voices

`speak()` uses the `alloy` voice. Swap it for `echo`, `fable`, `onyx`, `nova`, or `shimmer`.

## Resources

- [Voice API overview](https://developer.vonage.com/en/voice/voice-api/overview)
- [NCCO reference](https://developer.vonage.com/en/voice/voice-api/ncco-reference)
- [Input action](https://developer.vonage.com/en/voice/voice-api/ncco-reference#input)
- [Automatic speech recognition](https://developer.vonage.com/en/voice/voice-api/concepts/asr)
- [OpenAI text to speech](https://platform.openai.com/docs/guides/text-to-speech)
- [OpenAI Platform](https://platform.openai.com)
