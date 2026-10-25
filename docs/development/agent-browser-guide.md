# Agent-browser on the Mac

Installed globally with npm: `agent-browser` 0.39.2, native Apple Silicon binary.
Chrome for Testing was installed with `agent-browser install`.

## Image generation moved to Codex

The ChatGPT website image-generator wrapper was removed on 2026-10-24 at the
owner's request. Sleever now uses Codex's built-in image tool when Gemini's image
quota is exhausted. See the [sleeves guide](tts-sleeves-guide.md). Browser setup
below remains available for ordinary browsing; sleever does not use it.

## Persistent ChatGPT login

The Mac's local `~/.agent-browser/config.json` contains:

```json
{
  "headed": true,
  "session": "chatgpt-account",
  "restore": "chatgpt-account"
}
```

Commands now reuse the same visible browser and automatically save/restore its
cookies and browser storage. Authentication state stays outside the repository
in `~/.agent-browser/sessions/`, with owner-only permissions. On 2026-10-22,
closing the browser and reopening ChatGPT restored the signed-in Plus account;
the CLI reported `restore: loaded`.

```sh
agent-browser open https://chatgpt.com/
agent-browser snapshot -i -s main
agent-browser click @e1  # use a current snapshot's reference
agent-browser close
```

The website can still require reauthentication if its session expires or is
revoked. The earlier repeated logins happened before automatic restore was set.

## Browser mode and waiting

Headless Chrome reached ChatGPT but encountered a human-verification challenge
in this test. Keep the visible browser for this account workflow.

Avoid `wait <ref> --state detached` in 0.39.2: despite the wait help example,
`--state` was parsed as an authentication-state filename, produced a file error,
and the subsequent session lost its browser/login. Use a JavaScript condition:

```sh
agent-browser wait --fn 'document.querySelectorAll("main button").length > 1'
```

References: [installation](https://agent-browser.dev/installation),
[configuration](https://agent-browser.dev/configuration).
