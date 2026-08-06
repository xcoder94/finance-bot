# Cascade keyword dictionary — PM review

Source of truth right now: `backend/app/parsing/cascade_keywords.py` (this
is what actually runs — the mini-PRD's Appendix A table was the draft
that became this file, never walked through with the PM before it
shipped). This document is the working copy to review and edit — once
you're done, the changes get carried into `cascade_keywords.py` and the
existing prefilter tests re-run to confirm nothing broke.

## What I checked myself (mechanical, no language judgment needed)

- **Coverage: complete.** Every category in the current 7-parent/23-sub
  expense set + 4 income categories (`backend/app/services/budget_seed.py`)
  has a row here. `income_other` ("Прочее") is deliberately absent — a
  catch-all has no keyword by definition; any unmatched message should
  fall through to the LLM, not get force-matched here.
- **The "той" duplicate is not a bug.** It appears as a keyword on both
  the parent `События и тои` and its child `Тои и маърака`. The prefilter
  code (`app/parsing/prefilter.py`, `_apply_subcategory_first`) already
  drops the parent match whenever a child of the same parent also
  matched — so a message containing "той" resolves to the subcategory,
  never the parent. No fix needed, flagging so it doesn't look like an
  oversight.
- **How matching actually works, relevant to judging a keyword's
  quality:** a single word is matched as a **whole word only** (Cyrillic-
  and Latin-aware boundary check — "дом" won't match inside
  "домашний"). A phrase with a space or apostrophe is matched as a
  **plain substring**, no boundary check. So: a single short common
  word is safe from most false hits (word-boundary protects it), but a
  short *phrase* is not — pick phrases specific enough that they won't
  appear inside an unrelated sentence.
- **What I did not check:** whether any Uzbek term below is the word an
  actual family would type, whether spelling/spoken-form is right, and
  whether common local brand names/apps (taxi, delivery, marketplaces)
  are missing. That needs you, not me guessing.

## Table — edit the RU/UZ columns directly, use the last column for notes

Legend for the last column: leave blank if the row is fine as-is; write
what to add/change/remove otherwise.

### Expenses

| Parent → sub | key | RU keywords | UZ keywords | PM notes |
|---|---|---|---|---|
| Еда | `food` | еда | ovqat | |
| ↳ Продукты | `groceries` | продукты, магазин, супермаркет | oziq-ovqat, market, do'kon | |
| ↳ Кафе и рестораны | `cafes_restaurants` | кафе, ресторан, кофе, обед | kafe, restoran, taomxona | |
| ↳ Доставка | `delivery` | доставка, яндекс еда, uzum tezkor | yetkazib berish | |
| Транспорт | `transport` | транспорт | transport | |
| ↳ Такси | `taxi` | такси, яндекс такси, болт | taksi | |
| ↳ Топливо | `fuel` | бензин, заправка, топливо, газ (авто) | benzin, yoqilg'i | |
| ↳ Общественный транспорт | `public_transport` | автобус, метро, маршрутка, проезд | avtobus, metro | |
| ↳ Обслуживание авто | `car_maintenance` | сто, автосервис, шиномонтаж, мойка | avto servis, moyka | |
| Дом | `home` | дом | uy | |
| ↳ Аренда | `rent` | аренда, съём квартиры | ijara | |
| ↳ Коммунальные услуги | `utilities` | коммуналка, свет, вода, электричество | kommunal, svet, suv | |
| ↳ Связь и интернет | `telecom_internet` | интернет, связь, симкарта | internet, aloqa | |
| ↳ Ремонт и обустройство | `repairs_furnishing` | ремонт, мебель, стройматериалы | ta'mir, mebel | |
| Дети | `children` | дети | bolalar | |
| ↳ Садик и школа | `kindergarten_school` | садик, школа, детский сад | bog'cha, maktab | |
| ↳ Кружки и репетиторы | `clubs_tutoring` | кружок, репетитор | to'garak, repetitor | |
| ↳ Детские товары | `kids_goods` | игрушки, детская одежда, подгузники | bolalar buyumlari | |
| Здоровье | `health` | здоровье | salomatlik | |
| ↳ Лекарства и аптека | `pharmacy` | лекарства, аптека, таблетки | dori, apteka | |
| ↳ Врачи и клиники | `doctors_clinics` | врач, клиника, больница, анализы | shifokor, klinika | |
| ↳ Стоматология | `dentistry` | стоматолог, зубы, дантист | stomatolog, tish | |
| События и тои | `events_celebrations` | той, мероприятие | to'y, tadbir | |
| ↳ Тои и маърака | `toi_celebrations` | той, маърака, свадьба, юбилей | to'y, marosim | |
| ↳ Подарки | `event_gifts` | подарок на той, цветы | sovg'a | |
| Покупки и досуг | `shopping_leisure` | покупки | xarid | |
| ↳ Одежда | `clothing` | одежда, обувь, кроссовки | kiyim, poyabzal | |
| ↳ Развлечения | `entertainment` | кино, боулинг, развлечения | kino, ko'ngilochar | |
| ↳ Подписки | `subscriptions` | подписка, netflix, spotify | obuna | |
| ↳ Красота и уход | `beauty_care` | салон красоты, парикмахерская, косметика | go'zallik saloni | |

### Income

| Category | key | RU keywords | UZ keywords | PM notes |
|---|---|---|---|---|
| Зарплата | `salary` | зарплата, зп, аванс, оклад | maosh, ish haqi | |
| Подработка | `side_job` | подработка, фриланс, шабашка | qo'shimcha ish | |
| Подарки | `gifts` | подарили, подарок получил | sovg'a oldim | |
| Переводы от родных | `family_transfers` | перевод от родителей, от родных, от мамы, от папы | qarindoshdan pul | |
| Прочее | `income_other` | *(intentionally no keyword — always falls to LLM)* | — | |

## When you're done

Tell me (or tell Cursor directly, your call) which rows changed. It's a
small, mechanical edit to `CASCADE_KEYWORDS` in
`backend/app/parsing/cascade_keywords.py` — a dict literal, one entry per
`key` above, values are just the RU+UZ terms as a flat list of strings
(order doesn't matter functionally). Existing prefilter tests
(`backend/tests/test_phase16_prefilter.py`,
`test_phase16_prefilter_handlers.py`) should be re-run after — new keywords may need new test cases if you want them
covered, but that's optional, not required for the edit itself to be
safe.
