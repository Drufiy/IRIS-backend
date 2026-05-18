# Todo/Task Manager Setup & Usage

IRIS can manage your todo list via voice.

## Quick Start

### Add a Task
```
"Add task: finish project report"
"Add task: buy groceries, priority high"
"Add task: call mom"
```

### List Tasks
```
"Show my todos"
"What tasks do I have?"
```

Expected output:
```
PENDING TASKS:
  1. 🔴 Finish project report (high)
  2. ⚪ Buy groceries (normal)
  3. 🟢 Call mom (low)

COMPLETED:
  4. ✓ Email presentation to Bob
```

### Mark Task Complete
```
"Mark task 2 complete"
"Check off task 1"
```

### Delete Task
```
"Delete task 4"
"Remove task 2"
```

## Priority Levels

| Priority | Indicator | Use For |
|----------|-----------|---------|
| high | 🔴 Red | Urgent, important |
| normal | ⚪ White | Regular tasks |
| low | 🟢 Green | Nice-to-have |

## Configuration

Edit `configs/settings.yaml`:

```yaml
todo:
  default_priority: "normal"  # "low", "normal", or "high"
```

## Storage

Tasks are stored in `~/.iris/tasks.json` (JSON format):

```json
{
  "id": 1,
  "name": "Finish project report",
  "priority": "high",
  "completed": false,
  "created": "2026-05-18T12:00:00",
  "completed_at": null
}
```

- File is created automatically
- Survives IRIS restarts
- You can edit it directly if needed

## Safety Level

| Action | Level | Approval |
|--------|-------|----------|
| add_task | WARN | No (logged) |
| list_tasks | SAFE | Auto-execute |
| mark_task_complete | WARN | No (logged) |
| delete_task | WARN | No (logged) |

## Examples

### Daily Workflow
```
Morning:
"Add task: review emails"
"Add task: standup meeting"
"Show my todos"

Afternoon:
"Mark task 1 complete"
"Add task: code review for PR #42"

Evening:
"Delete task 3"
"What tasks do I have?"
```

### Using with other actions
```
"Add task: Email Bob about the budget"
# Later:
"Show my todos"
"Mark task 1 complete"
"Send email to bob@company.com, subject: Budget, body: Check your inbox"
```

## Tips

- **Link tasks to reminders:** *"Add task: call Mom" → "Set reminder: call Mom in 1 hour"*
- **Check before meetings:** *"Show my todos"*
- **Clean up weekly:** *"Delete task X"*
- **Batch add:** Say multiple "Add task" commands in a row

## Limitations

- No task due dates (future enhancement)
- No task descriptions (just task names)
- No subtasks or categories
- No recurrence/repeat tasks
- No multi-user / shared lists

## File Location

`~/.iris/tasks.json` — portable to other devices

## Backup

Manually copy the file:
```powershell
Copy-Item $env:USERPROFILE\.iris\tasks.json $env:USERPROFILE\Desktop\tasks.json
```
