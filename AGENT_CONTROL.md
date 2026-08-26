# Controlling the Arcade Coder from an AI agent

The board is driven over Bluetooth by one process (`arcadeos_hw.py`), which
also runs a small HTTP control server on **`http://127.0.0.1:7770`**. Any
agent with shell access on the Mac mini (e.g. NanoClaw / `claude -p` with
Bash) can control the board by `curl`-ing this API — no Bluetooth or extra
permissions needed. It's loopback-only, so nothing is exposed to the network.

If the board isn't running, start it first:
```
open /Users/hansstam/Projects/arcade-minesweeper/ArcadeMinesweeper.app
```

## Draw a picture — `POST /paint`
Send 12 rows of 12 characters. Each letter is a colour; `.` or space = off.
Palette: `r`ed `g`reen `b`lue `y`ellow `o`range `c`yan `m`agenta/pink `p`urple
`w`hite `k`pink `n`brown `a`gray `d`dim. Fewer/short rows are fine.
```
curl -s -X POST http://127.0.0.1:7770/paint -H 'Content-Type: application/json' -d '{
  "rows":["............","..rr..rr....",".rrrrrrrr...",".rrrrrrrr...",
          ".rrrrrrrr...","..rrrrrr....","...rrrr.....","....rr......",
          "............","............","............","............"]}'
```
For full colour control send `"pixels": [[r,g,b], ... 144 entries]` instead.

## Scroll a message — `POST /say`
```
curl -s -X POST http://127.0.0.1:7770/say -H 'Content-Type: application/json' \
  -d '{"text":"BACK IN 5","rainbow":true}'
```
Optional: `"color":[r,g,b]`, `"background":[r,g,b]`, `"speed":7`.

## Launch an app — `POST /switch`
```
curl -s -X POST http://127.0.0.1:7770/switch -H 'Content-Type: application/json' \
  -d '{"app":"backdrop"}'      # or "home", "pomodoro", "othello", "studioclock", ...
```

## See what's running / list apps — `GET /status`
```
curl -s http://127.0.0.1:7770/status
# -> {"app":"...", "apps":["home","games",...], "busy":..., "uptime_s":...}
```

## Apps you can launch
games, deck, kopads, seq, midiviz, rhythm, ambient, party, marquee, pomodoro,
countdown, weather, onair, ytmusic, doodle, stopwatch, worldclock, pet, ttt,
othello, dice, chessclock, sand, backdrop, studioclock, remote — plus `home`.
`/paint` automatically switches to the `remote` canvas app.
