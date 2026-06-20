# icloud-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI
assistants **read-only** access to your iCloud mail and calendar over IMAP and
CalDAV. Credentials live in your OS keyring (macOS Keychain by default) — never
in a config file or the repo.

Defaults target iCloud, but every endpoint is overridable, so it works against
any standard IMAP/CalDAV provider.

## Status

**v1 is read-only.** Mail and calendar can be listed, searched, and read, but
nothing can be sent, created, modified, or deleted. The IMAP connection is opened
read-only and bodies are fetched with `BODY.PEEK[]`, so messages are never even
marked as read. Mutating tools (send mail, create events) are planned for a
future version behind explicit per-action confirmation.

## Install

```bash
pip install git+ssh://git@github.com/eodozzy/icloud-mcp
```

Or for local development:

```bash
git clone git@github.com:eodozzy/icloud-mcp
cd icloud-mcp
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
```

Requires Python 3.11+.

## Credentials

Generate an [app-specific password](https://appleid.apple.com) for your Apple ID
(never use your main password), then store it in your keyring:

```bash
# macOS
security add-generic-password -a "you@icloud.com" -s "icloud-mcp" -w "xxxx-xxxx-xxxx-xxxx"
```

On other platforms, the cross-platform [`keyring`](https://pypi.org/project/keyring/)
library is used — `keyring set icloud-mcp you@icloud.com` also works anywhere.

The username comes from the `ICLOUD_USERNAME` environment variable. Resolution
order for the password:

1. OS keyring (`ICLOUD_KEYRING_SERVICE`, default `icloud-mcp`, + username)
2. `ICLOUD_APP_PASSWORD` environment variable (fallback)

To **reuse an existing keyring entry** (e.g. one named `talos-icloud`), set
`ICLOUD_KEYRING_SERVICE=talos-icloud`.

## Configuration

Set `ICLOUD_USERNAME` (required). All else is optional — see
[`.env.example`](.env.example) for the full list of endpoint/timezone overrides.

## Register with Claude Code / Claude Desktop

```json
{
  "mcpServers": {
    "icloud": {
      "command": "icloud-mcp",
      "env": {
        "ICLOUD_USERNAME": "you@icloud.com"
      }
    }
  }
}
```

(If installed in a virtualenv, point `command` at `.venv/bin/icloud-mcp`.)

## Tools & resources

**Tools** (model-invoked):

| Tool | Description |
|---|---|
| `search_mail` | Full-text search the inbox (or a named folder) |
| `get_message` | Fetch one message by UID, with full body |
| `list_events` | Calendar events in a date window |
| `search_events` | Events whose title matches text, in a window |
| `list_calendars` | Names of all calendars |

**Resources** (passive context):

| URI | Description |
|---|---|
| `icloud://mail/inbox/recent` | Most recent inbox messages |
| `icloud://calendar/today` | Today + tomorrow's events |

## Development

```bash
.venv/bin/pytest            # run the fixture-based test suite (no live account)
.venv/bin/mcp dev -m icloud_mcp.server   # interactive MCP Inspector
```

## Security notes

- The app-specific password lives in the OS keyring only — never in `.env`,
  never committed.
- Mail/calendar access is read-only; the IMAP session cannot mutate the mailbox.
- An app-specific password can be revoked at any time from appleid.apple.com
  without affecting your Apple ID.

## License

MIT — see [LICENSE](LICENSE).
