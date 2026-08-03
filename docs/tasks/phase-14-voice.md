# Phase 14 — Voice input

PRD: §9.
Depends on: Phase 1–2 (text quick entry path that voice reuses).
Plan: written after this spec is approved — not in this file.

---

## 1. User goal

A person sends a voice message; the bot types silently, then answers with the
same cards as text — without ever showing a transcription.

---

## 2. Acceptance steps I will do by hand

1. Clear voice describing one expense → typing indicator immediately → ordinary
   card.
2. Transcription text appears **nowhere** in the chat.
3. Voice with description but no amount → exact §7.9 text; unparsed +1.
4. Silence/noise → exact «Не разобрал голосовое…» text; unparsed +1.
5. Voice with three operations → three cards; model quota of 50 drops by 1,
   not by 3.
6. **Customer gate (my evening checklist):** 18 of 20 real recordings acceptable
   — not a team CI gate; team ships the plumbing.

---

## 3. What is NOT in this phase

- Receipt photo (§10) — Phase 15
- Showing transcription or «Расшифровываю…» service messages
- A separate voice daily limit
- Choosing a different speech vendor than the customer decision (Google)
- Hard-coding `SPEECH_MODEL`
- Uzbek translations
- Prompt-cache design for audio (out of scope unless already identical to text
  path after transcription)

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Pipeline | Transcribe → treat text exactly as quick entry (same parse, cards, buttons, counters). |
| 2 | Provider | Google. Env: `SPEECH_PROVIDER`, `SPEECH_API_KEY`, `SPEECH_MODEL` — model name only from env. |
| 3 | While running | Standard Telegram typing indicator only; no service message. |
| 4 | Transcription visibility | Never shown. |
| 5 | Failure: not recognised | Exact §9 Russian text; unparsed +1. |
| 6 | Failure: no amount | Exact §7.9; unparsed +1. |
| 7 | Counters | Same as text; no separate voice ceiling. |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Tests with stubbed speech provider: typing indicator set/cleared; card path
   invoked with transcribed text; noise → §9 text; no-amount → §7.9; three ops
   spend 1 model call after stubbed parse; assert reply never includes
   transcription string.
2. Live call if `SPEECH_*` present; else list as finish-later.
3. Report before/after; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Google speech account + key | customer |
| `SPEECH_PROVIDER`, `SPEECH_API_KEY`, `SPEECH_MODEL` | customer |
| 20 real test recordings for the gate | customer (§22) |

---

## 7. When you must stop and ask me

- Showing transcription «for transparency».
- Switching speech provider away from Google.
- Hard-coding a model id.
- Inventing a separate voice quota.
- Confidence below average — say «not sure».
