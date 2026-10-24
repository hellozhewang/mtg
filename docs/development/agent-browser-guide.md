# Agent-browser on the Mac

Installed globally with npm: `agent-browser` 0.39.2, native Apple Silicon binary.
Chrome for Testing was installed with `agent-browser install`.

## Python image generator

Use the wrapper from the repository root:

```sh
python3 scripts/discord/chatgpt-browser-image-generator.py \
  --prompt "A happy golden retriever sitting in a sunny park, square photograph" \
  --out assets/generated/my-dog.png
```

The script asks for exactly one image based on your description and downloads
the original PNG. It uses your normal signed-in ChatGPT website session and its
own allowance and checks. It does not call Codex's built-in image tool or an image
API. It stops on sign-in challenges, usage limits or rejected requests instead
of trying to bypass them or silently switching providers.

Options:

- `--prompt-file path.txt`: read a UTF-8 description instead of `--prompt`.
- `--chat-url https://chatgpt.com/c/...`: choose an existing chat explicitly.
- `--timeout 600`: maximum generation wait in seconds.
- `--session chatgpt-account`: select the browser's saved session.
- `--download-only`: recover the latest turn's completed image without sending
  another prompt. Older successful images are never substituted for a new failure.

The Mac's private `~/.agent-browser/image-generation.json` stores the preferred
chat as `{"chat_url": "https://chatgpt.com/c/..."}`. Without that file or
`--chat-url`, the script opens New chat. Actual chat IDs and authentication state
are kept out of the repository.

The output must be a new `.png` path. Existing files and unsent composer drafts
are preserved. The script locks its browser session against concurrent script
runs, submits each prompt once, waits for the NEW response and image to load,
and validates the PNG header, dimensions and end marker before installing it.
Successful output prints a JSON receipt with the path, dimensions, byte size and
SHA-256. It leaves Chrome open. The UI selectors were tested against the English
ChatGPT interface; UI changes may require updating them.

For a lost download acknowledgement, it checks for an already-completed PNG,
then permits one retry of the original-file download only. It never retries a
prompt submission automatically. This addresses a CLI daemon read error observed
during the live test without spending another image generation.

If a generation times out, inspect the same chat, then recover it without
spending another generation:

```sh
python3 scripts/discord/chatgpt-browser-image-generator.py \
  --download-only --out assets/generated/recovered.png
```

Run the local regression checks without browser requests:

```sh
python3 -m unittest discover -s tests -p test_chatgpt_browser_image_generator.py -v
```

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

The composer can appear before chat history and image bytes finish loading. The
wrapper waits for both. Snapshot JSON can also contain hidden controls in its
`refs` map; it only clicks references actually present in the visible snapshot.

A successful click only dispatches a request. Inspect the resulting response
and image/download controls before reporting generation or download success.
The Spider-Man test on 2026-10-22 returned a third-party-similarity guardrail
message on both the initial request and one ordinary retry. No generated image
or download control was present, so no image file was added to the repository.
Use the original download when available:

```sh
agent-browser download @e1 /absolute/path/to/output.png
```

Persistent helper scripts belong in `scripts/`; image outputs can live in
`assets/generated/`. Screenshots are not substitutes for original downloads.

## Verified generation and original download

On 2026-10-22 the signed-in browser generated a golden retriever successfully.
The image was opened using its `Generated image 1` button, then downloaded from
the `Image preview` dialog's `Download` button using the CLI:

```sh
agent-browser snapshot -i -s main
agent-browser click @e196  # Generated image 1; references change per snapshot
agent-browser snapshot -i -s '[role="dialog"]'
agent-browser download @e203 /Users/zzwang/projects/mtg/assets/generated/dog.png
```

The downloaded original is `assets/generated/dog.png`, a verified 1254 × 1254 RGB
PNG, visually inspected as a golden retriever sitting in a park. This used the
ChatGPT website session and browser CLI, without an image API call or screenshot
substitution. The prompt was:

> Generate one square photograph of a happy golden retriever sitting on green
> grass in a sunny park, natural soft lighting, detailed golden fur, friendly
> expression, no text or watermarks.

The Python wrapper was also tested with a new beagle/red-ball prompt. Generation
was submitted once; after a lost download acknowledgement, `--download-only`
recovered the new response using the bounded download retry. The result is
`assets/generated/dog-script-test.png`, a visually verified 1254 × 1254 PNG,
distinct from the earlier retriever image. All nine local regression checks pass.

References: [installation](https://agent-browser.dev/installation),
[configuration](https://agent-browser.dev/configuration).
