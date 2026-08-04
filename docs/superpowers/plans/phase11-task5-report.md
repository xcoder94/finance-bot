# Phase 11 Task 5 — Report: Frontend toggles and settings subtitle

## Summary

Wired notification preference toggles on the settings notifications screen and dynamic TOC subtitle per PRD §17.6. Two independent `role="switch"` rows PATCH `/api/v1/me`; subtitle lists enabled notification names joined with ` · ` or `Выключены` when both off.

## Tests

### Before implementation (touched files)

```text
npm test -- --run src/utils/settingsSubtitles.test.ts src/pages/settings/notificationsSettingsShell.test.tsx src/api/me.test.ts
4 failed | 15 passed (19)
```

Failures: `notificationsSubtitle` ignored args; no `role="switch"` in notifications body; `eveningReminderEnabled` / `weeklyDigestEnabled` not mapped.

### After implementation (touched files)

```text
npm test -- --run src/utils/settingsSubtitles.test.ts src/pages/settings/notificationsSettingsShell.test.tsx src/api/me.test.ts
19 passed
```

### Full frontend suite

```text
npm test -- --run
37 files, 198 passed (+2 vs baseline 196)
```

## Changes

| File | Change |
|------|--------|
| `frontend/src/components/settings/SettingsToggleRow.tsx` | New toggle row: `role="switch"`, track/knob classes |
| `frontend/src/index.css` | Toggle styles: 44×26 track, 20px knob, radius 13, on `var(--acc)`, off `var(--chip)`, knob flex-end when on |
| `frontend/src/pages/settings/NotificationsSettingsShellPage.tsx` | Real toggles from auth store; optimistic PATCH + rollback |
| `frontend/src/utils/settingsSubtitles.ts` | `notificationsSubtitle(eveningEnabled, weeklyEnabled)` |
| `frontend/src/api/me.ts` | Map/patch `evening_reminder_enabled`, `weekly_digest_enabled` |
| `frontend/src/store/authStore.ts` | `eveningReminderEnabled`, `weeklyDigestEnabled`, local setters |
| `frontend/src/pages/SettingsPage.tsx` | TOC subtitle from user prefs |
| Tests | Subtitle cases, switch count/aria-checked, me mapping/PATCH |

## Subtitle rules (PRD §17.6)

| Evening | Weekly | Subtitle |
|---------|--------|----------|
| on | on | `Напоминание вечером · Итоги недели` |
| on | off | `Напоминание вечером` |
| off | on | `Итоги недели` |
| off | off | `Выключены` |

Design strings `Оба включены` / `Включено одно из двух` are not used.

## Disabled / stubbed / mocked

None in production code. Tests mock `useAuthStore` and `patchMe` in `notificationsSettingsShell.test.tsx`.

## Commit

`3d52d13` — `feat(settings): notification toggles and dynamic subtitle`
