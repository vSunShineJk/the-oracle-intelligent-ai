# Building `mcp_gmail_primary.py` — Step-by-Step Tutorial

Goal: a **local, stdio-transport MCP server** exposing your primary Gmail account
to **Claude Desktop**, with **no local database** — every tool call talks to the
live Gmail API.

You write the code in `mcp_gmail_primary.py`. This tutorial tells you *what* to
build, *why*, and *in what order*, with small illustrative snippets — not a
finished file to copy-paste.

Foundation you already have and will reuse:
- `tools/gmail/gmail_api_calls.py` — `_get_service`, `check_connection`, `fetch_last_emails`,
  `fetch_new_emails`, `send_email`
- `tools/google/config.py` — `GMAIL_ACCOUNTS` (use `GMAIL_ACCOUNTS[0]` for "primary")

You will **not** use `tools/gmail/gmail_database_queries.py` or `data/database.py` — no DB in this build.

---

## Progress tracker

| Step | Status |
|---|---|
| 0 — Prerequisites | ✅ Done |
| 1 — FastMCP shape | ✅ Done |
| 2 — `ping` smoke test | ✅ Done |
| 3 — Connection check tool | ✅ Done (`gmail_primary_status_check`) |
| 4 — List recent emails | ✅ Done (`list_recent_emails`, trimmed to slim dict) |
| 5 — Search via Gmail query syntax | ✅ Done (`search_emails`, trimmed) |
| 6 — Get one email in full | ✅ Done (`fetch_full_gmail`) |
| 7 — Thread fetching | ⬜ Skipped for now — still a known gap |
| 8 — Fast unread/label counts | ✅ Done (`count_unread`) |
| 9 — Send flow + confirmation | ⚠️ In progress — `compose_email`/`send_email` built, but the confirmation gate (host approval dialog) proved unreliable in practice, see note below |
| 10 — Full local Inspector pass | ✅ Done informally through iterative testing |
| 11 — Wiring into Claude Desktop | ✅ Done — note: this machine runs the **Windows Store/MSIX build** of Claude Desktop, config lives at `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`, NOT the classic `%APPDATA%\Claude\` path — `mcp install` doesn't find this build, had to hand-edit the config |
| 12 — End-to-end conversation tests | ✅ Done — confirmed working via Claude Desktop, first calls a bit slow (cold subprocess spawn + live per-email API round-trips), otherwise solid |
| 13 — Security checklist | ⚠️ Partially — see confirmation-gate note below |

---

## Step 0 — Prerequisites

1. Install the official MCP Python SDK **with its CLI extras** into the project:
   ```
   uv add "mcp[cli]"
   ```
   The `[cli]` extra matters — it's what gives you the `mcp` command-line tool
   (`mcp dev`, `mcp install`) used in Steps 2 and 11 below. Without it you only
   get the library, not the tooling.
2. Confirm Claude Desktop is installed and you can open its settings.

Checkpoint: `uv run mcp --help` prints the CLI's help text without error.

---

## Step 1 — Understand the shape of a FastMCP server

Every FastMCP server has three parts:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gmail-primary")   # 1. one shared app instance

@mcp.tool()                      # 2. tools registered via decorator
def some_tool(arg: str) -> str:
    """This docstring becomes the tool description Claude sees."""
    ...

if __name__ == "__main__":
    mcp.run(transport="stdio")   # 3. entrypoint — blocks, listens on stdin/stdout
```

This is structurally the same pattern as `azure_agent()` + `@oracle.tool` in
`brain/orchestrator_agent.py` — one shared agent/app object, functions attached
via decorator, function signature + docstring become the schema. Nothing exotic here.

**Critical rule for this whole file: never use `print()`.** stdout is the exact
channel MCP uses to talk to Claude Desktop — any stray `print()` corrupts the
protocol stream and the server will appear to "hang" or error out with no clear
message. `gmail_api_calls.py` is full of `print()` calls for debugging — when
you call those functions from your tools, either:
- accept the print output will break things and remove/replace it with logging to stderr, or
- write your own equivalents inline in `mcp_gmail_primary.py` that don't print.

If you want visibility while debugging, use Python's `logging` module configured
to write to a file or `sys.stderr`, never `print()`.

---

## Step 2 — Prove the plumbing works before touching Gmail

Before wiring anything Gmail-related, get a **trivial** tool working end-to-end.
In `mcp_gmail_primary.py`, create the `FastMCP` instance and one fake tool, e.g.
`ping() -> str` that just returns `"pong"`.

Then test it **without Claude Desktop**, using the MCP CLI's dev command:
```
uv run mcp dev mcp_gmail_primary/mcp_gmail_primary.py
```
This is the officially recommended way to iterate on a FastMCP server — it
starts your server *and* launches the MCP Inspector web UI already connected
to it (no separate `npx` invocation needed, and no manually constructing the
command-line the Inspector should use to spawn your process — `mcp dev` handles
that wiring for you). Open the URL it prints, find `ping` in the tool list, and
call it manually. If you don't see `pong` come back, stop and fix this before
building anything else — every later bug will be harder to isolate if the
basic transport isn't confirmed working first.

(You may still encounter references elsewhere to running the Inspector
standalone via `npx @modelcontextprotocol/inspector <command>` — that's the
more manual, framework-agnostic version of the same idea. Since you're already
using the official Python SDK's CLI, `mcp dev` is the simpler path and the one
this tutorial uses from here on.)

Checkpoint: Inspector lists your server, shows `ping` in the tool list, and
calling it returns `"pong"`.

---

## Step 3 — First real tool: connection check

Wrap `check_connection` from `gmail_api_calls.py` as your second tool, e.g.
`gmail_connection_status() -> str`. Inside, call
`check_connection(GMAIL_ACCOUNTS[0].token_path)` and return a short human-readable
string based on the boolean result.

Why this one first: it exercises real OAuth token loading/refresh (the riskiest
part of the whole system) while still being a pure read, no data returned, easy
to reason about if something breaks (expired token, wrong path, missing scopes).

Design note: notice the token path itself (`GMAIL_ACCOUNTS[0].token_path`) is
**resolved inside your tool function, not passed in as a tool argument.** The
model should never be able to choose which credential file to load — keep every
credential-path decision on your side of the wrapper, always.

Checkpoint: Inspector call to `gmail_connection_status` reports success.

---

## Step 4 — Listing recent emails (live, no DB)

Wrap `fetch_last_emails(token_path, count)` as a tool, e.g.
`list_recent_emails(count: int = 5) -> list[dict]`.

Design decisions to make deliberately here:
- Clamp `count` to a sane max inside your wrapper (e.g. `min(count, 20)`) —
  each unit of `count` costs a real Gmail API round-trip (`fetch_last_emails`
  does one `list` + N `get` calls). Don't let the model request 500 emails by accident.
- Trim the returned dict per email before returning to Claude — do you need to
  send the full `body` for a *listing* tool, or just `subject`, `from`, `date`,
  `snippet`, `id`? Sending full bodies for every item in a list is exactly the
  mistake your own `progress.md` describes hitting before (context-length blowup)
  — it happened once already in this project with the DB-based version, don't
  reintroduce it here.
- Write the docstring to explicitly say what `id` is for — that's what makes
  Claude able to later call a "get one email in full" tool.

Checkpoint: `list_recent_emails(count=3)` in Inspector returns 3 slim email summaries.

---

## Step 5 — Search using Gmail's own query syntax (not custom SQL-style filters)

Since there's no DB, don't reimplement sender/subject/body filtering yourself.
Gmail's API already accepts its native search syntax (`from:`, `subject:`,
`after:`, `is:unread`, `has:attachment`, ...) via the `q` parameter on
`messages().list`.

Design: write a new small helper (not currently in `gmail_api_calls.py`) that
takes a raw query string and a max result count, calls
`service.users().messages().list(userId="me", q=query, maxResults=...)`,
then fetches full messages for each ID the same way `fetch_last_emails` does.
Expose it as a tool, e.g. `search_emails(query: str, max_results: int = 10) -> list[dict]`.

Docstring must teach the model the query syntax it can use — a couple of
examples in the docstring (e.g. `from:someone@example.com`, `subject:invoice`,
`is:unread`, `after:2026/01/01`) go a long way, since this is the *only* place
Claude learns the contract.

Checkpoint: `search_emails(query="is:unread", max_results=5)` returns only unread emails.

---

## Step 6 — Fetching one email in full

Wrap a "get by id" tool, e.g. `get_email(message_id: str) -> dict`, calling
`service.users().messages().get(userId="me", id=message_id)` and reusing the
existing `_parse_email` helper from `gmail_api_calls.py` (you may need to import
it, or call through a small function that mirrors it — `_parse_email` is
currently a private helper, decide whether to import it directly or copy the
minimal logic you need).

This is the tool that returns the full `body` — deliberately not the listing
tools, to keep list responses small (see Step 4).

Checkpoint: `get_email(message_id=...)` using an ID from Step 4/5's output
returns the full body text.

---

## Step 7 — Known gap: fetching a full thread

Your DB layer had `get_emails_by_thread(thread_id)` — there is **no live
equivalent yet** in `gmail_api_calls.py`. Gmail's API supports this directly:
`service.users().threads().get(userId="me", id=thread_id)` returns all messages
in a thread in one call, each shaped like the `raw` dict `_parse_email` expects.

Write a new tool `get_thread(thread_id: str) -> list[dict]` that calls this
endpoint and parses each message in the `messages` list of the response the
same way you parse a single message elsewhere.

Checkpoint: calling `get_thread` on a `thread_id` from a previous result
returns every message in that conversation, oldest first (check `internalDate`
ordering — you may need to sort explicitly, the API doesn't guarantee order).

---

## Step 8 — Counting unread/total, the fast way

Don't count by listing everything. Gmail exposes counts directly on labels:
`service.users().labels().get(userId="me", id="UNREAD")` returns a response
containing `messagesUnread` and `messagesTotal` fields instantly, no pagination
needed. Wrap this as `count_unread() -> int` (and optionally a general
`count_by_label(label: str) -> dict` for any label, not just UNREAD).

Checkpoint: `count_unread()` matches what you see in Gmail's own UI.

---

## Step 9 — Sending email: keep the two-step confirmation pattern, upgrade it if you want

Your orchestrator already has a good pattern: `compose_email` (draft, no side
effect) then a separate confirmation step before `send_email` actually fires.
Recreate that shape here:

- `compose_email(to: str, subject: str, body: str) -> str` — returns a
  formatted draft preview, calls nothing in the Gmail API. No side effects, ever.
- `send_email_confirmed(to: str, subject: str, body: str, confirmation_keyword: str) -> str`
  — checks the keyword against `os.getenv("SEND_CONFIRMATION_CODE")` the same
  way `send_email_tool` does in `orchestrator_agent.py`, then calls
  `send_email(GMAIL_ACCOUNTS[0].token_path, to, subject, body)` only if it matches.

Optional upgrade to research on your own once this works: MCP's **elicitation**
feature lets a tool pause and ask the *user* a yes/no question mid-call, which
is a more "native" replacement for the keyword hack — worth trying once the
basic flow works, not before.

Checkpoint: asking Claude to "email X about Y" produces a draft via
`compose_email` first, and only actually sends after you provide the
confirmation keyword.

> **⚠️ Real-world finding (post-build):** we initially shipped `compose_email` +
> `send_email` relying on **Claude Desktop's built-in per-tool-call approval
> dialog** as the confirmation gate, instead of the keyword. In practice this
> was unreliable: after the first approval click (likely "Allow for this chat"
> rather than "Allow once"), Claude Desktop stopped re-prompting for the rest
> of the conversation and `send_email` fired silently on later calls. **Lesson:
> host-level approval dialogs are a UI setting, not a hard gate — they can
> silently degrade and shouldn't be the only thing standing between the model
> and an irreversible action.**
>
> Still undecided / to implement next: bring back a real code-level gate that
> can't degrade — either (a) a required confirmation argument on `send_email`
> itself that must come from something the model can only get by asking the
> user fresh each time (closer to the keyword approach, just needs a cleaner
> secret-handling story than plain env var comparison), or (b) MCP elicitation,
> if this Claude Desktop build supports it — check before committing to it as
> the design.

---

## Step 10 — Full local test pass (still via Inspector)

Before touching Claude Desktop, re-test every tool built so far via
```
uv run mcp dev mcp_gmail_primary/mcp_gmail_primary.py
```
in this order: `ping` → `gmail_connection_status` →
`list_recent_emails` → `search_emails` → `get_email` → `get_thread` →
`count_unread` → `compose_email` → `send_email_confirmed` (send yourself a test
email to close the loop safely).

Only move to Step 11 once every one of these works standalone — debugging
inside Claude Desktop's UI is much harder than debugging in the Inspector.

---

## Step 11 — Wiring into Claude Desktop

Two ways to do this — use the first, understand the second.

**Preferred: let the CLI do it.**
```
uv run mcp install mcp_gmail_primary/mcp_gmail_primary.py
```
This is the counterpart to `mcp dev` — instead of launching a throwaway
Inspector session, it registers your server directly into Claude Desktop's own
config so Claude Desktop will spawn it on every future launch. Run it, then
fully quit and restart Claude Desktop (not just close the window).

**What it's doing under the hood (worth knowing even if you don't do it by hand):**
It edits Claude Desktop's config file:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

adding an entry under `"mcpServers"` pointing at this file, using `uv run` so it
executes inside your project's environment, roughly shaped like:
```json
{
  "mcpServers": {
    "gmail-primary": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "C:\\Users\\umm\\PycharmProjects\\New_project",
        "python", "mcp_gmail_primary/mcp_gmail_primary.py"
      ]
    }
  }
}
```
Fully quit and restart Claude Desktop (not just close the window) so it re-reads
the config and spawns your server. Look for a small tool/plug icon in the chat
input area — that's how you confirm Claude Desktop sees your server and its tools.

---

## Step 12 — End-to-end conversation tests

Try these prompts directly in Claude Desktop and confirm the right tool fires:
1. "Am I connected to Gmail?" → `gmail_connection_status`
2. "Show me my last 3 emails" → `list_recent_emails`
3. "Any unread emails about invoices?" → `search_emails`
4. "Read me the full email with id ..." → `get_email`
5. "Show me the whole thread for ..." → `get_thread`
6. "How many unread emails do I have?" → `count_unread`
7. "Draft an email to test@example.com saying hi" → `compose_email`, then confirm to send

---

## Step 13 — Security/quality checklist before considering this "done"

- [ ] No `print()` anywhere in the file or in any function it calls on the request path
- [ ] `token_path` / credentials never appear as a tool parameter — always resolved server-side
- [ ] List/search tools return slim data (no full body) — only `get_email`/`get_thread` return full bodies
- [ ] `count` / `max_results` parameters are clamped to a sane upper bound in your wrapper, not left unbounded
- [ ] Sending mail is impossible without going through `compose_email` → confirmation → `send_email_confirmed`
- [ ] Every tool docstring stands alone — assume Claude has never read any other file, and has no system prompt giving it extra context
- [ ] You've manually tested every tool via Inspector before trusting Claude Desktop's UI

---

## Where this can go next (not part of this build)

Once this works reliably, revisit earlier discussions on: remote hosting
(Railway/Fly.io) if you want ChatGPT or other devices to reach it, OAuth between
the host and your server for remote access, and expanding the tool set to
labels/archive/trash actions with their own confirmation gates.
