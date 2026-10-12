# iCloud Calendar Read-only MCP

Personal fork of [eodozzy/icloud-mcp](https://github.com/eodozzy/icloud-mcp),
retaining the original MIT license. This fork is **calendar-only** and is not
an Apple or OpenAI product. The Python package is `icloud-calendar-readonly`;
it is not published to PyPI. Do not install upstream `icloud-mcp` to use this fork.

## Tools

- `list_calendars`: list accessible calendar names.
- `list_events`: events from today through `days_ahead` (0–366).
- `search_events`: case-insensitive title search in that window.
- Resource `icloud://calendar/today`: today's events.

All accessible calendars are included. There is no per-calendar selection.
Mail, contacts, SMTP and all mutation implementations have been removed.
Query failures are reported as errors instead of silently omitted calendars.
Titles and other calendar content are untrusted data, never instructions.

## Security boundary

- Fixed bootstrap URL `https://caldav.icloud.com/`.
- Every outgoing request, including discovered URLs and every redirect hop,
  permits only HTTPS port 443 at `caldav.icloud.com` or `p[0-9]+-caldav.icloud.com`.
  Other Apple services, arbitrary iCloud subdomains, userinfo URLs, plaintext,
  proxies and TLS verification bypasses are rejected.
- HTTP/2 and HTTP/3 Alt-Svc upgrades and separate OCSP/CRL network lookups
  are disabled to avoid out-of-policy connections. TLS certificate chain and
  hostname verification remain required. Normal OS DNS resolution is still used.
- The transport allows only GET, HEAD, OPTIONS, PROPFIND and REPORT. There is
  no write-enable flag and no write tool, including when legacy environment
  variables are present.
- Passwords come only from OS keyring service `icloud-calendar-readonly`, under
  the configured Apple account. No `.env` loading or password-env fallback.
- Endpoint/proxy/.netrc/CA environment overrides are not inherited by transport.
- Direct dependencies are pinned; `uv.lock` locks the complete environment.
  The allowlist/redirect tests depend on these versions and must pass on upgrades.

These are application restrictions, not an Apple-issued read-only credential.
The process still needs the app-specific password in memory to authenticate.
A compromised OS or dependency is outside this boundary. Calendar data returned
by tools is shared with the MCP client/model. This is not a formal security audit.

## Local setup

Requires Python 3.12+ and uv. Clone this fork, then:

```sh
uv sync --locked
# Interactive hidden prompt; never put the password in a shell command or chat.
.venv/bin/python -m keyring set icloud-calendar-readonly your-apple-account@example.com
codex mcp add icloud-calendar --env ICLOUD_USERNAME=your-apple-account@example.com --env ICLOUD_TZ=Asia/Seoul -- /absolute/path/to/checkout/.venv/bin/icloud-calendar-readonly
```

Use an Apple **app-specific password**, not your primary password. Revoke it in
Apple account settings to revoke access. Keychain may request local permission.
MCP tool discovery works before credentials exist; calendar calls return an
error until the keyring entry is available. No inbound port or tunnel is needed
for local stdio use. ChatGPT web needs a separate connection; this setup only
registers the local Codex-host MCP.

Only `ICLOUD_USERNAME` and `ICLOUD_TZ` configure the server. Timezone defaults to
UTC, so set it explicitly for your location. To remove the local registration:

```sh
codex mcp remove icloud-calendar
```

## Verification

```sh
uv sync --locked --extra test
uv run --locked --extra test pytest -q
```

Tests use fake credentials and HTTP adapters; they do not read your keychain or
connect to your iCloud account. They cover the MCP surface, missing credentials,
calendar results, failure reporting, endpoint spoofing, redirects, transport
write rejection and mandatory TLS validation. Live iCloud validation is separate.
