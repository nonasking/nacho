# nacho

An automation tool for driving a Notion database from the shell or Claude Code slash commands.
Adds new rows to a work-tracking Notion DB, accumulates a progress log, generates a daily briefing, and auto-captures the Claude session ID.

## Prerequisites

- macOS / Linux
- Python ≥ 3.10
- A Notion **Internal Integration** ([my-integrations](https://www.notion.so/my-integrations))
- Add that Integration under the target Notion DB's ... menu → Connections
- Optional: [Claude Code](https://docs.anthropic.com/claude-code) — only if you use the slash commands / session-context mode

## Install

```bash
git clone <repo-url> nacho && cd nacho

# isolated venv recommended
python3 -m venv .venv
.venv/bin/pip install -e .

# make it callable from anywhere (optional)
mkdir -p ~/.local/bin
ln -sf "$PWD/.venv/bin/nacho" ~/.local/bin/nacho
```

## First run

```bash
nacho init
```

The wizard asks, in order:

1. **Notion Integration Token** (getpass — hidden on screen)
2. **DB URL** — top-right of the DB page → Share → Copy link
3. **DB schema lookup** + **automatic field mapping** (Korean/English pattern heuristics)
4. **Automatic status classification** (using Notion status groups — To-do/In progress = active, Complete = inactive)
5. **Defaults** (status, assignee)

Result:
- `~/.config/nacho/config.yaml` — DB ID, field mappings, defaults
- `~/.config/nacho/credentials.json` — token (chmod 0600)

To write it by hand, see [`config.example.yaml`](./config.example.yaml).

## Usage — directly from the shell

### Create a new row

```bash
# interactive (recommended) — your DB's options show up as a dynamic menu
nacho new

# pre-specify args + skip the confirmation step
nacho new \
  --title "sort-rendering bug" \
  --category 운영 \
  --project "Project A" \
  --link https://example.atlassian.net/browse/KEY-123 \
  --yes
```

- Unmapped fields (keys left empty in `config.yaml`) aren't even prompted → it adapts to your DB structure.
- Option values only accept the actual options from the DB schema (free-form input is rejected).
- `--link auto` → extracts a URL from the system clipboard automatically.
- When `--session-id` is omitted, it's read from `~/.cache/nacho/current-session` automatically (requires the Claude Code SessionStart hook — see below).

### List rows

```bash
nacho list --active                    # active statuses only (status_categories.active)
nacho list --status "진행 중"           # a specific status
nacho list --json                      # for automation / LLMs
```

### Add a progress-log entry (status note)

```bash
nacho note "curation" "monitoring on staging, deploy to follow"
```
- Appends `- YYYY-MM-DD HH:MM: note` to the row body's `## 진행 일지` (progress log) section.
- Simultaneously overwrites the `status_note` field (e.g. "status summary") with that note → visible at a glance as one column in the DB list view.

### Briefing

```bash
nacho brief                                          # to stdout
nacho brief --to-file ~/Desktop/today-brief.md       # save to file
```
- Organized into due-soon (~7 days) / in-progress / waiting·on-hold groups.
- Each row shows a `[project]` prefix + the `status_note` status memo.

### Resume a session

```bash
nacho resume "curation"          # prints 'claude --resume <id>' for that row's session_id
nacho resume "curation" --exec   # runs claude --resume directly
```

## Usage — Claude Code slash commands

```bash
./install.sh
```
→ registers symlinks in `~/.claude/commands/`.

Three slash commands:

| Slash | Purpose | Processing |
|---|---|---|
| `/nacho` | create a new row (auto-summarizes session context) | full auto — body written by the LLM |
| `/nacho-quick` | create a new row (user-stated only, just auto session_id) | no body processing (security-first) |
| `/nacho-note` | add a one-line note to an existing row + refresh the status summary | dual mode |

See `commands/*.md` for each slash command's behavior and safety guards.

## SessionStart hook (optional) — auto-capture the Claude session ID

Add to the SessionStart hook array in `~/.claude/settings.json`:

```json
{
  "type": "command",
  "command": "mkdir -p ~/.cache/nacho && jq -r .session_id > ~/.cache/nacho/current-session"
}
```

→ The session_id is written to a file when a Claude Code session starts. `nacho new` then inserts it into the body's `## Session` section automatically.

## Design — why a CLI + thin skill instead of the Notion MCP

(A shared design principle with oobs · tako.)

MCP's context cost comes not from calls but from **residency**. Attach the official Notion MCP and ~20 tool schemas ride in the system prompt of *every* session — taking thousands to tens of thousands of tokens *even in sessions that never touch Notion*. nacho converts that residency cost into a per-call cost:

- **Residency cost**: just one line of skill description (tens of tokens). Usage loads only at the moment `/nacho` is invoked.
- Per-call cost is similar to MCP — the savings are entirely in the resident schemas.
- **Direct shell calls outside a session = 0 tokens** (also consistent with the audit-bypass in the Security notes) + deterministic behavior.

Honest trade-offs:

- Recent Claude Code lazy-loads MCP tools (ToolSearch), so the residency gap is smaller than it used to be.
- Where MCP wins — typed schemas reduce malformed calls, the server manages auth, and **vendor maintenance**: when the Notion API changes, nacho has to be fixed by hand. Registering field mappings directly in config is also a manual cost versus the MCP's runtime lookup.

## Security notes

- The token is stored in plaintext at `~/.config/nacho/credentials.json` (chmod 0600).
- Calling nacho from inside Claude Code means the command + args + result may end up in the Anthropic API response → if you have audit concerns (e.g. a corporate Team Plan), prefer **calling the shell directly in a separate cmux panel**.
- `/nacho-quick` reduces exposure by blocking LLM processing of the body, but the slash invocation itself still shows up in the audit log — the safest option is to bypass Claude Code.

## Directory

```
nacho/
├── commands/
│   ├── nacho.md             /nacho slash command
│   ├── nacho-quick.md       /nacho-quick slash command
│   └── nacho-note.md        /nacho-note slash command
├── nacho/                   Python package
│   ├── auth.py              credentials loader
│   ├── notion_client.py     REST entry point
│   ├── page_draft.py        properties builder + preview
│   ├── prompts.py           interactive input
│   ├── schema.py            DB schema option extraction
│   ├── session.py           Claude session id
│   ├── progress.py          progress-log section
│   ├── clipboard.py         clipboard URL extraction
│   ├── config.py            settings + init wizard
│   └── main.py              CLI entry point
├── config.example.yaml      example config (for manual setup)
└── install.sh               register slash commands (optional)
```

## Troubleshooting

- `nacho: command not found` — the `~/.local/bin/nacho` symlink isn't set, or `~/.local/bin` isn't on PATH.
- `설정 파일이 없습니다` (no config file) — run `nacho init` first.
- `credentials 없음` (no credentials) — same.
- `400 ... validation error` — a value that doesn't match the DB schema options. Check the `fields` mapping in `~/.config/nacho/config.yaml`, or re-setup with `nacho init --force`.
- `401 unauthorized` — token expired/wrong. Re-enter with `nacho init --force`.
- `404 ... database not found` — the Integration lacks access to that DB. Add the Integration under the DB page's ... → Connections.
