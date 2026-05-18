# Timer & Reminder Setup & Usage

IRIS can set timers and reminders via voice.

## Quick Start

### Timers

```
"Set a timer for 10 minutes"
"Timer for 5 minutes, label: cooking"
"Start a 30 second timer"
```

When timer expires:
```
🔔 TIMER ALERT: cooking is done!
```

### Reminders

```
"Remind me to check email in 30 minutes"
"Set reminder: call Mom in 2 hours"
"Reminder: meeting in 1 hour"
```

### Check Reminders

```
"Show my reminders"
"What reminders do I have?"
"List reminders"
```

Expected output:
```
UPCOMING REMINDERS:
  1. Check email (in 28m)
  2. Call Mom (in 1h 45m)
  3. Team meeting (in 23h)
```

### Cancel Reminder

```
"Cancel reminder 1"
"Delete reminder 2"
```

## Usage Scenarios

### Cooking
```
"Add task: make dinner"
"Set timer for 20 minutes, label: pasta"
"Remind me to check on the oven in 15 minutes"
```

### Meetings
```
"Remind me about the standup in 30 minutes"
"Set reminder: prepare presentation in 1 hour"
```

### Breaks
```
"Set a timer for 5 minutes"  # Quick break
"Remind me to take a break in 2 hours"
```

### Sleep
```
"Set reminder: prepare for bed in 1 hour"
"Remind me to set an alarm in 30 minutes"
```

## Limits

### Timer Duration
- Minimum: 1 second
- Maximum: 1 hour (3600 seconds)
- Examples: "10 seconds", "5 minutes", "1 hour"

### Reminder Duration
- Minimum: 1 minute
- Maximum: 24 hours (1440 minutes)
- Examples: "30 minutes", "2 hours", "tomorrow morning"

## Configuration

Edit `configs/settings.yaml`:

```yaml
timers:
  default_timezone: "UTC"  # For display purposes
```

## Storage

### Timers
- Stored **in memory** during IRIS session
- Lost when IRIS restarts
- No notification file

### Reminders
- Stored in `~/.iris/reminders.json`
- Survives IRIS restarts
- Auto-cleaned (expired reminders removed)

## Safety Level

| Action | Level | Approval |
|--------|-------|----------|
| set_timer | WARN | No (logged) |
| set_reminder | WARN | No (logged) |
| list_reminders | SAFE | Auto-execute |
| cancel_reminder | WARN | No (logged) |

## How Timers Work

1. You say: *"Set timer for 10 minutes"*
2. IRIS starts a background async countdown
3. **10 minutes later:**
   - Timer expires
   - IRIS prints alert: `🔔 TIMER ALERT: Timer is done!`
   - (Future: TTS will speak "Timer is done!")

Timers are **lost on restart** — they only persist during your IRIS session.

## How Reminders Work

1. You say: *"Remind me to check email in 30 minutes"*
2. IRIS stores reminder in `~/.iris/reminders.json` with due time
3. **30 minutes later:**
   - Reminder time arrives
   - (Future: IRIS will notify you, pop alert, or speak)
4. You can check reminders: *"Show my reminders"*

Reminders are **persistent** — they survive IRIS restarts.

## Examples

### Time Conversion

When you say "minutes", IRIS converts to seconds:

| You say | Seconds |
|---------|---------|
| "10 seconds" | 10 |
| "5 minutes" | 300 |
| "1 hour" | 3600 |
| "30 minutes" | 1800 |

For reminders:

| You say | Minutes |
|---------|---------|
| "30 minutes" | 30 |
| "1 hour" | 60 |
| "2 hours" | 120 |
| "tomorrow" | 1440 |

## Use Cases

### Kitchen Timer
```
"Set timer for 20 minutes, label: pasta"
"Set another timer for 10 minutes, label: sauce"
"How much time left on my timer?"
```

### Work Breaks
```
"Remind me to take a break in 1 hour"
"Set a 5 minute timer"  # Stretch break
"Remind me to stand up in 30 minutes"
```

### Morning Routine
```
"Remind me to shower in 10 minutes"
"Set timer for 15 minutes"  # Shower
"Remind me about breakfast in 20 minutes"
```

### Study Sessions
```
"Set reminder: study session start in 30 minutes"
"Timer for 25 minutes"  # Pomodoro technique
"Remind me to take a break in 25 minutes"
```

### Sleep & Bedtime
```
"Remind me about bedtime in 1 hour"
"Set reminder: morning workout in 8 hours"
```

## Limitations

- **Timers don't notify yet** — (future: TTS alert)
- **No recurring reminders** — set manually each time
- **No reminder notifications** — (future: popup or TTS)
- **No timezone conversion** — all times in local time
- **No delay between reminders** — they execute immediately at due time

## Future Enhancements

- [ ] TTS alert when timer expires
- [ ] Desktop notification for reminders
- [ ] Recurring reminders ("every day at 9am")
- [ ] Reminder sounds/alarms
- [ ] Integration with calendar
- [ ] Multiple concurrent timers
- [ ] Timer pause/resume

## File Location

`~/.iris/reminders.json` — JSON format

Example:
```json
{
  "id": 1,
  "text": "Check email",
  "time": "2026-05-18T13:30:00",
  "created": "2026-05-18T13:00:00"
}
```

## Backup

Copy reminders file:
```powershell
Copy-Item $env:USERPROFILE\.iris\reminders.json $env:USERPROFILE\Desktop\reminders.json
```

## Common Phrases

You can use natural language:

```
✓ "Set a timer for 10 minutes"
✓ "Timer for 5 minutes"
✓ "Set timer: 10 minutes"

✓ "Remind me in 30 minutes"
✓ "Set reminder for 2 hours"
✓ "Reminder to call mom in 1 hour"
```
