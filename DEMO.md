# 5-Minute Demo Script

Use this script to record a Loom walkthrough of `qbo-mcp` for the launch posts. Total target: **5 minutes**.

Record in 1080p, monospace terminal at 14pt minimum. **Use a sandbox QuickBooks Online realm, never the production books.** Sandbox companies come pre-populated with a believable amount of test data and let you demo without leaking real customer or vendor names.

## Setup before hitting record

- Create (or reuse) a QBO sandbox company at <https://developer.intuit.com/app/developer/sandbox>.
- Run through the README "One-time OAuth setup" against the sandbox company. Save the resulting `.env`.
- Test that `qbo-mcp` runs and Claude Code sees the eight tools (`qbo_search_customers`, …).
- Have one customer with non-zero balance, one open invoice, one open bill, and a few vendors loaded in the sandbox so live queries return non-empty results.
- Have the README open in a second tab for the cold open.
- Fresh terminal window (cleared scrollback).

## Script

### 0:00. 0:30  Cold open

> "If you run a business on QuickBooks Online and you've ever wanted Claude to just *know* what's in your books, this is for you. I built `qbo-mcp`, the Model Context Protocol server for QuickBooks Online. Read-only, MIT-licensed, takes about five minutes to install."

Show the README hero section. Pan slowly through the tool table.

### 0:30. 1:30  Install and configure

Show in the terminal:

```bash
pip install qbo-mcp
cp .env.example .env
# edit .env: paste sandbox client_id, client_secret, refresh_token, realm_id
```

Then show the Claude Code MCP config block, paste it into `~/.claude/claude_code_config.json`. Restart Claude Code. Show the eight new tools showing up in a new session.

> "Five environment variables, one config block. Refresh tokens rotate, the server handles that for you."

### 1:30. 2:30  Live demo: customers + AR

Open a fresh Claude Code session. Type:

> "Use qbo to find every customer matching 'Sample' and tell me what they owe us. Sort by balance descending."

Watch Claude call `qbo_search_customers`, return the list, and synthesize a ranked summary. Read off the top entry.

### 2:30. 3:30  Live demo: invoices

> "Pull every open invoice from this month. Group them by customer and total the balance per group."

Claude calls `qbo_search_invoices` with `status="open"`, gets a list, groups them. Show the resulting summary in the chat.

> "Notice that I never wrote any code. Claude is reading QuickBooks directly through the MCP server."

### 3:30. 4:30  Live demo: combined operation (AP)

> "Pick our top three vendors by open balance. For each one, show me the bills coming due in the next 30 days."

Claude calls `qbo_search_vendors`, then `qbo_search_bills` filtered per vendor with `status="open"`. Highlight the multi-step reasoning happening over the MCP surface.

> "This is the unlock. Claude can chain reads across customers, invoices, vendors, and bills in one conversation. Without an SDK. Without any code I had to write."

### 4:30. 5:00  Close

Show the GitHub repo briefly. Mention:

- MIT-licensed, free to use
- Read-only in v0.1, write tools coming in v0.2
- Open to issues + PRs
- Star + share if it's useful

> "Repo link in the description. v0.2 with write tools is a few weeks out, leave a comment if there's a specific endpoint you'd like exposed first."

End on the README hero shot.

## Post-recording

- Trim silence at start/end.
- Add captions (Loom auto-caption is fine, just review for brand-name accuracy: "QuickBooks", "Intuit", "MCP").
- Thumbnail: a screenshot of the multi-step AP demo with the tool calls visible.

## Distribution

After recording, the launch posts go to:

1. **Twitter/X**, single thread, 6-8 tweets, embed the Loom in tweet 1. Lead: *"QuickBooks has 7M users. There was no MCP server. Now there is."*
2. **Reddit r/MCP**, title: *"qbo-mcp: read-only MCP server for QuickBooks Online (MIT)"*. Body: short framing + Loom + GitHub link.
3. **Reddit r/Bookkeeping and r/smallbusiness**, different framing, lead with the use case (*"Use Claude to query your QuickBooks Online data without copy-pasting"*), Loom + GitHub link.
4. **LinkedIn**, finance-operator angle: *"AR/AP triage in plain English. Sandbox demo, code is open source."*

Draft copy for all four lives in `LAUNCH_POSTS.md` (to be created).
