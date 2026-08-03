# Phase 13 — Prompt caching

PRD: §20.
Depends on: Phase 1–2 parsing path stable (real provider calls).
Plan: written after this spec is approved — not in this file.

---

## 1. User goal

Nothing the person sees changes; the family keeps writing as usual while the
product pays less for parsing because most prompt tokens are cached.

---

## 2. Acceptance steps I will do by hand

1. One parse call: provider token counters show cached tokens ≥ 90% of input
   tokens.
2. Delete the cache manually; send a quick-entry message → record created
   normally, no user-visible difference; afterwards cache rebuilt.
3. Deploy a changed prompt version → previous cache gone (not still serving).
4. Messages from two families → one installation-wide cache serves both.
5. Confirm static part contains no wallet name, date, member name, or message
   text.

(Steps that need provider console access may be done with the team watching
the counters; customer holds the Google account.)

---

## 3. What is NOT in this phase

- Any user-facing copy change
- Voice (§9) or receipt photo (§10) caching behaviour (images do not benefit
  from this cache per §10.2 — do not invent a second cache design here)
- Per-family caches
- Making cache a hard dependency of parsing
- Uzbek translations

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Static part | Fixed text; substitutions only in variable tail; no conditional fragments that alter the static body. |
| 2 | No family data in static part | Mandatory. |
| 3 | Cache count | Exactly one cache for the whole installation. |
| 4 | Lifetime | Permanent; extended in background; recreate only on new prompt version; old cache deleted on version deploy. |
| 5 | Missing cache | Parsing still works full-prompt; rebuild in background. |
| 6 | Success metric | ≥90% cached tokens on one measured call. |
| 7 | Provider / model | `PARSER_*` env only; never hard-code model name. |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. Automated assertions on prompt assembly: static blob stable; variable tail
   holds wallets/message/date; no family data in static.
2. Integration test or scripted call reading provider usage metadata when
   credentials present; if absent, report blocked and list under finish-later.
3. Test that missing-cache path still creates a transaction (stub provider
   ok for that path).
4. Report before/after; list stubs.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Google parser credentials with cache-capable API | customer |
| `PARSER_PROVIDER`, `PARSER_API_KEY`, `PARSER_MODEL` set | customer |
| Access to token counters for one call | customer / team together |

---

## 7. When you must stop and ask me

- Building per-family caches.
- Making parsing fail when cache is missing.
- Putting family-specific values into the static prompt.
- Hard-coding a model version string.
- Confidence below average — say «not sure».
