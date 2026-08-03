# Phase 6 — Settings: wallets, categories, default, language

PRD: §17.6 rows 1–4 and 7; entity forms in §17.7 (settings entities); name and
count limits from §4 for those entities; soft-delete rules §15.4; app limit
messages §19.1 for wallets and categories.
Depends on: Phase 3 (Settings menu item exists).
Plan: written after this spec is approved — not in this file.
Design: Settings TOC and entity screens one to one with the design file.

---

## 1. User goal

A person opens Settings as a table of contents, manages shared wallets,
categories, and their default wallet, and sees clear limit messages when a
ceiling is hit — without delete buttons sitting in every list row.

---

## 2. Acceptance steps I will do by hand

1. Settings TOC lists **all seven** rows in §17.6 order. This phase fully
   implements rows 1–4 and 7. Rows 5 `Участники` and 6 `Уведомления` are
   visible with honest subtitles (`N из 4`; `Выключены` until Phase 11 ships
   switches) and open design-matching shells; invite/transfer/exit and
   notification behaviour are Phases 9 and 11 — do not invent them here.
2. Subtitles for rows 1–4 and 7 match §17.6 patterns (`4 общих · …`, default
   wallet name, category counts, `Русский` / `Oʻzbekcha` on the language row).
   Uzbek strings for the rest of the product stay out of scope.
3. Inside `Кошельки`, shared and personal sections are separated. Creating
   **shared** wallets: owner only. Personal wallet **creation** completes in
   Phase 7; until then the personal section may list none and must not fake
   create success.
4. Create shared wallets up to 10; create button stays enabled; tap at limit →
   exact §19.1 shared-wallets text. Delete one, create again — works.
5. Parent expense categories to 8; subcategories inside one parent to 8; income
   categories accordingly; each limit shows its §19.1 text. Deleted category
   frees a slot (§4 / §15.4).
6. Name 31 characters rejected; only spaces rejected; 30 characters shown
   truncated with ellipsis in list, not wrapped.
7. Delete control not in list rows — swipe or entity screen, with shared
   confirm sheet (§17.6 / §17.7).
8. Soft-delete: deleted category absent from operation form and filters; still
   visible in analytics/History for past data; no restore control; same-name
   new category is a new entity with a new colour (§15.4 / §5 colour rules).
9. Default wallet picker works for the current user; quick entry without a
   named wallet uses it (regression with Phase 1).
10. New budget still seeds §15.1–§15.2 only; **no migration** of old families
    (§15.5).

---

## 3. What is NOT in this phase

- Full personal wallets product / `Мои личные` (§11) — Phase 7
- Members row behaviour (§13 / §17.6.5) — Phase 9
- Notifications switches (§16 / §17.6.6) — Phase 11
- Goals (§12)
- Change log (§14)
- Migrating existing families to the new category set
- Full Uzbek UI translations (language row label only if present)
- Voice, photo, caching, bot chrome rewrite

---

## 4. Pre-approved decisions (exact values)

| # | Decision | Exact value |
|---|----------|-------------|
| 1 | Settings shape | TOC of sections; not one endless list. |
| 2 | Row order | All seven rows always listed in §17.6 order. This phase fully implements 1–4 and 7; rows 5–6 are shells until Phases 9 and 11. |
| 3 | Limits | Shared wallets 10; personal 5 (enforce when create exists); parents 8; subcats 8 per parent; name 30; create button stays visible. |
| 4 | Limit copy | Exact §19.1 Russian strings for wallets and categories. |
| 5 | Soft-delete | §15.4 package as a whole; no restore. |
| 6 | Colour on new category | Free among active and not used by category deleted in last 12 months; else longest-deleted's colour (§5). |
| 7 | §15.5 | No migration. |
| 8 | Worker model | `composer-2.5` only. |

---

## 5. How the team verifies without me

1. API/UI tests for each limit message character-for-character; slot freed on
   delete; name trim/length; soft-delete picker exclusion; colour assignment
   rule with fixture deleted categories.
2. Default wallet used by quick-entry path (existing bot test).
3. Existing pre-MVP2 budget fixture: category set unchanged after migrations
   for this phase.
4. Report before/after; list stubs; state how non-owned Settings rows appear.

---

## 6. Preconditions: what must be issued in advance

| Need | Who provides |
|------|--------------|
| Phase 3 Settings entry | team |
| Owner Telegram account | customer |
| Optional: old-category-set family fixture | team |
| Design chips for Settings | repo |

---

## 7. When you must stop and ask me

- Migrating old families «to make demos nicer».
- Putting `Удалить` back into every list row.
- Changing limit numbers or hard-coding 50/20 (those stay server config).
- Implementing full members/notifications behaviour inside this phase.
- PRD vs design disagreement.
- Confidence below average — say «not sure».
