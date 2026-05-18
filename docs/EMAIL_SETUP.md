# Email Actions Setup Guide

IRIS can send and check emails using SMTP and IMAP protocols.

## Quick Setup

### 1. Update `configs/settings.yaml`

Add your email configuration:

```yaml
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "your_email@gmail.com"
  sender_password: "your_password_or_app_password"
  
  imap_server: "imap.gmail.com"
  receiver_email: "your_email@gmail.com"
  receiver_password: "your_password_or_app_password"
```

### 2. Provider-Specific Instructions

#### **Gmail**

1. Enable 2-step verification (if not already done)
   - Go to myaccount.google.com → Security
   
2. Create an app-specific password:
   - Account.google.com → Security → App passwords
   - Select "Mail" and "Windows Computer"
   - Copy the generated 16-character password
   - Use this in `sender_password` and `receiver_password`

3. Update settings.yaml:
   ```yaml
   smtp_server: "smtp.gmail.com"
   smtp_port: 587
   imap_server: "imap.gmail.com"
   ```

#### **Outlook/Microsoft 365**

1. Create an app password (if using Microsoft account):
   - account.microsoft.com → Security → Advanced security options
   - Add app password

2. Update settings.yaml:
   ```yaml
   smtp_server: "smtp-mail.outlook.com"
   smtp_port: 587
   imap_server: "outlook.office365.com"
   sender_email: "your_email@outlook.com"
   receiver_email: "your_email@outlook.com"
   ```

#### **Other Providers (Yahoo, ProtonMail, etc.)**

| Provider | SMTP | Port | IMAP | Port |
|----------|------|------|------|------|
| Yahoo Mail | smtp.mail.yahoo.com | 587 | imap.mail.yahoo.com | 993 |
| ProtonMail | smtp.protonmail.com | 587 | imap.protonmail.com | 993 |
| iCloud | smtp.mail.me.com | 587 | imap.mail.me.com | 993 |

## Usage

### Send Email

```
"Send email to alice@example.com, subject: Hello, body: Hi Alice, how are you?"
```

IRIS will:
1. Extract recipient, subject, and body from your speech
2. Classify action as WARN (logs + executes, no approval needed)
3. Send via SMTP
4. Respond: "Email sent to alice@example.com"

### Check Email

```
"Check my email"
```

IRIS will:
1. Connect to IMAP server
2. Count unread emails in INBOX
3. Fetch the latest email subject
4. Speak: "You have 3 unread emails. Latest: Meeting rescheduled"

## Safety Classification

| Action | Level | Behavior |
|--------|-------|----------|
| `send_email` | WARN | Executes + logs (no approval needed) |
| `check_email` | SAFE | Auto-execute silently |

## Troubleshooting

### "Email not configured"
- Check that `sender_email` and `sender_password` are not empty in `configs/settings.yaml`
- Verify no leading/trailing spaces in credentials

### "Authentication failed"
- Gmail: Verify you're using an app-specific password, not your account password
- Outlook: Check that 2-step verification is enabled and app password is correct
- Double-check email address matches the account you're authenticating with

### "Connection timeout"
- Verify SMTP/IMAP server address is correct
- Check firewall isn't blocking port 587 or 993
- Try connecting from another app first (Thunderbird, Outlook) to confirm credentials

### "IMAP disabled"
- Gmail: Go to myaccount.google.com → Security → Less secure app access (enable it)
- Or use app passwords (recommended)

### "TLS/SSL error"
- Port 587 uses STARTTLS (recommended)
- Port 465 uses implicit SSL (legacy)
- Most providers prefer 587 — use that first

## Privacy Notes

- Credentials are stored **plaintext in `configs/settings.yaml`**
- Consider restricting file permissions: `chmod 600 configs/settings.yaml`
- For production, consider using environment variables instead (future enhancement)
- IRIS connects directly to provider servers — no credentials sent to third parties

## Examples

**Send an email about a meeting:**
```
"Email bob@company.com. Subject: Team Standup. Body: Hi Bob, standup moved to 10am."
```

**Respond to multiple recipients:**
```
"Send email to alice@example.com, subject: Update, body: Project status is on track"
```

**Check for specific unread emails:**
```
"Check my email"
→ "You have 5 unread emails. Latest: Quarterly review incoming"
```

## Limitations

- **Single recipient:** `send_email` sends to one person at a time
- **No attachments:** Currently unsupported (future enhancement)
- **No scheduling:** Email sends immediately
- **No search:** `check_email` only shows unread count + latest subject

## Future Enhancements

- [ ] Bulk email to multiple recipients
- [ ] Attach files from disk
- [ ] Schedule email for later
- [ ] Search emails by sender/subject
- [ ] Support email templates
- [ ] Integration with calendar for meeting notifications
