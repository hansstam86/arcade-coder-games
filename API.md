# Arcade Coder API — control the board from anything

The board runs a tiny web server on your Mac at **`http://127.0.0.1:7770`**.
Anything that can make a web request — your browser, a terminal, a script, a
Shortcut, or an AI agent — can put a message on the board, draw a picture, or
launch an app. It only listens on your own machine, so it's private.

> **Easiest way:** open **`http://127.0.0.1:7770/control`** in a browser — a
> point-and-click panel to send messages, launch apps, and draw on the board
> live. Everything below is what that panel does under the hood.

The board must be running (`open ArcadeMinesweeper.app`). That's it.

---

## 1. Send a scrolling message — `POST /say`

```bash
curl -s http://127.0.0.1:7770/say -d '{"text":"HELLO"}'
```
Options (all optional): `"rainbow": true`, `"color": [255,40,40]`,
`"speed": 4` (2 = slow, 14 = fast), `"background": [0,0,0]`.
```bash
curl -s http://127.0.0.1:7770/say -d '{"text":"IN A MEETING","color":[255,40,40],"speed":5}'
```
Tip: text is shown in CAPITALS.

## 2. Draw a picture — `POST /paint`

Send **12 rows of 12 letters**. Each letter is a colour; `.` or space is off:

| letter | colour | letter | colour | letter | colour |
|---|---|---|---|---|---|
| `r` | red | `o` | orange | `w` | white |
| `g` | green | `c` | cyan | `k` | pink |
| `b` | blue | `m` | magenta | `n` | brown |
| `y` | yellow | `p` | purple | `a` | grey |

```bash
curl -s http://127.0.0.1:7770/paint -d '{"rows":[
"............",
"..rr..rr....",
".rrrrrrrr...",
".rrrrrrrr...",
".rrrrrrrr...",
"..rrrrrr....",
"...rrrr.....",
"....rr......",
"............",
"............",
"............",
"............"]}'
```
For exact colours, send `"pixels": [[r,g,b], … 144 values]` instead of `rows`.

## 3. Launch an app — `POST /switch`

```bash
curl -s http://127.0.0.1:7770/switch -d '{"app":"backdrop"}'
curl -s http://127.0.0.1:7770/switch -d '{"app":"home"}'
```
Apps: `games deck kopads seq midiviz rhythm ambient party marquee pomodoro
countdown weather onair ytmusic doodle stopwatch worldclock pet ttt othello
dice chessclock sand backdrop studioclock remote` (and `home`).

## 4. See what's running — `GET /status`

```bash
curl -s http://127.0.0.1:7770/status
# {"app":"backdrop","apps":["home","games",…],"busy":false,"uptime_s":123}
```

---

## Shortcut: a `say` command

Add this to your `~/.zshrc` so you can just type `say-board "HELLO"`:
```bash
say-board() { curl -s http://127.0.0.1:7770/say -d "{\"text\":\"$*\",\"rainbow\":true}" >/dev/null; }
```
(Reload with `source ~/.zshrc`.)

## Notes

- You can omit the `-H 'Content-Type: application/json'` header with curl — the
  server reads the body either way. Add it if your client is strict.
- All the `POST` bodies are plain JSON.
- More detail for AI agents: see `AGENT_CONTROL.md`.
