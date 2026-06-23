# AI Receptionist — Demo Frontend

A clean, modern ChatGPT-like interface for demonstrating the Kinderuniversiteit AI Receptionist system to a client.

## Stack

| Layer | Tech |
|-------|------|
| Framework | Next.js 15 (App Router) |
| UI | React 19 + TypeScript |
| Styling | TailwindCSS + shadcn/ui |
| HTTP | Axios |
| Icons | Lucide React |

## Prerequisites

* Node.js ≥ 18
* The FastAPI backend running on `http://localhost:8000`
  * Must expose `POST /demo/chat` → `{ message }` → `{ reply }`
  * Optionally expose `GET /health` for the header status badge

## Installation

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

Copy `.env.local.example` to `.env.local` to change the backend URL:

```bash
cp .env.local.example .env.local
```

The default is `http://localhost:8000`.

## Project Structure

```
demo-frontend/
├── app/
│   ├── globals.css        # Tailwind base + custom keyframes
│   ├── layout.tsx         # Root layout (Inter font, metadata)
│   └── page.tsx           # Main page — state, API wiring, layout
├── components/
│   ├── ChatWindow.tsx     # Scrollable message list + auto-scroll
│   ├── ChatInput.tsx      # Textarea + send button + suggestion chips
│   ├── MessageBubble.tsx  # Individual message (user / assistant / error)
│   ├── Sidebar.tsx        # Customer info card
│   ├── SuggestionChips.tsx# Clickable quick-question buttons
│   ├── TypingIndicator.tsx# Animated dots while awaiting response
│   ├── Header.tsx         # Top bar with online/offline badge
│   └── ui/                # shadcn/ui primitives
├── lib/
│   ├── api.ts             # sendMessage() — Axios + error handling
│   └── utils.ts           # cn() helper
└── types/
    └── index.ts           # Message, ChatRequest, ChatResponse interfaces
```

## API Contract

```
POST /demo/chat
Content-Type: application/json

{ "message": "What holiday camps do you offer?" }

→ 200 OK
{ "reply": "We offer several holiday camps..." }
```

Requests are proxied by Next.js `/backend/* → localhost:8000/*` to avoid CORS.
