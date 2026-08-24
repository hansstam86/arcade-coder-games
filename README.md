# Arcade Coder Games (Mac, stock firmware, no screwdriver)

Playable games for the [Tech Will Save Us Arcade Coder](https://github.com/padraigfl/awesome-arcade-coder)
(the 12×12 RGB LED button matrix), driven from a Mac over Bluetooth LE against
the **unmodified stock firmware**. No disassembly, no reflashing, no UART.

**▶ Try it now, no hardware needed: [Arcade Coder Studio](https://hansstam86.github.io/arcade-coder-games/)** —
a web IDE with the emulator built in. Write Python games in the browser (real
Python via Pyodide, the actual `arcadecoder` SDK), run them on the virtual
board — and in Chrome/Edge, hit **⚡ Run on board** to drive a real Arcade
Coder over Web Bluetooth, straight from the page, nothing installed. The same
file also runs locally with `--hw`.

Working games — all launchable from an on-board menu ([arcade.py](arcade.py)):

- **Minesweeper** ([minesweeper.py](minesweeper.py)) — 12×12, 18 mines, colour-coded
  neighbour counts, flood reveal, first-press-safe.
- **Whack-a-Mole** ([whackamole.py](whackamole.py)) — 1-pixel moles, 45-second
  rounds with a timer bar, ramping difficulty, score screen.
- **Simon** — 4-quadrant memory sequence.
- **Lights Out** — 5×5 puzzle, always-solvable scramble.
- **Connect Four** — 12×12, 1-pixel discs, two players at the board.
- **Colour Sudoku** — 9×9, colours as digits, palette row to pick, guided
  mode (wrong colours flash red and don't stick).
- **Memory Pairs** — 4×4 cards, 8 colour pairs, mismatches flip back.
- **Tetris** — press left/right thirds to move, middle to rotate.
- **Reaction Duel** — two players, top vs bottom half; hit your white target
  first, false starts give the point away, first to 5.
- **Snake** — press where you want it to go; wraps at edges, speeds up.

The menu shows ten icons; press one to play. After a game: green = replay,
blue = back to the menu.

Work in progress:

- **Snake** ([snake_upload.py](snake_upload.py), [run_snake.py](run_snake.py)) —
  accelerometer-steered, running *on the board* as an uploaded XS-JavaScript
  game. Uploads cleanly; display not yet confirmed (see findings below).

Built on the reverse-engineering work of the
[awesome-arcade-coder](https://github.com/padraigfl/awesome-arcade-coder) community,
[LightyCoderDoodad](https://github.com/diggedypomme/LightyCoderDoodad), and
[rs-arcade-coder](https://github.com/jake-walker/rs-arcade-coder). Thank you!

## How it works

The board's micro-USB port is charge-only, but the stock firmware speaks BLE
(service `778d5426-fa29-4363-91fd-a9f5cfcfce85`, advertises as `Gamer-TSW`):

- **Display**: start the built-in `paint` module (protobuf command type 2), then
  send frames as compact canvases — `[12, 12] + raw DEFLATE` of 432 device-order
  RGB bytes — via command type 4 frame mode. Red and blue channels are swapped,
  and frames must use **Huffman-only DEFLATE** (the stock inflater corrupts LZ77
  backreferences — a LightyCoderDoodad discovery).
- **Input**: in paint mode, every physical pad press makes the firmware notify
  the **full canvas state** on the callback characteristic. Diff that against
  the frame you last sent; the pixel that changed to the brush colour
  (device `(5,20,220)`) is the pressed pad.

That's a complete game loop: frames out, presses in, ~10 fps effective.

## Findings that may save you a day

- **macOS: write WITH response.** The command and game characteristics support
  only write-with-response (`props=['write']`). CoreBluetooth **silently
  discards** write-without-response on such characteristics — everything looks
  connected while nothing happens. (Windows/Bleak tolerated `response=False`,
  which is why community examples use it.)
- **Module switching wedges.** The firmware ignores "start module/game"
  commands while another module is running (testmode→paint, paint→game, all
  silently dropped). Start things from a freshly booted, idle board. A crashed
  uploaded game also wedges the board until power cycle.
- **macOS Bluetooth permission (TCC).** CoreBluetooth clients running under an
  app without `NSBluetoothAlwaysUsageDescription` are killed with SIGABRT.
  This repo ships a minimal ad-hoc-signed app bundle
  (`ArcadeMinesweeper.app`) that holds the permission and runs whichever
  script `launch_target.txt` names.
- **Uploaded-game VM strips JS builtins.** Uploaded XS JavaScript throwing
  `Error: (host): dead strip` means you called a builtin the firmware build
  dead-stripped. Our first snake died on `Array(n)`/`.fill`/`.indexOf`/
  `.unshift`/`.pop` (exact culprit unknown — the board wedged before bisecting
  finished; [builtin_probe.py](builtin_probe.py) automates the bisection using
  BLE error notifications as the oracle). The current snake uses only loops,
  assignments, `push`, and the Engine API.
- **No accelerometer over BLE.** 60 seconds of tilting/shaking in paint mode
  produced zero notifications. Tilt/shake only reach games running on-board
  (`Engine.WhenTilted("LEFT"|"RIGHT"|"FORWARD"|"BACK")`, `Engine.WhenShaken`).

## Write your own game (SDK + emulator)

The `arcadecoder/` package lets anyone build games with no hardware and no
protocol knowledge — and run the same file on a real board:

```python
from arcadecoder import Game, run

class Chase(Game):
    fps = 10
    def start(self):            self.target = (5, 5)
    def on_press(self, x, y):
        if (x, y) == self.target: ...
    def update(self, dt):       ...
    def draw(self, screen):     screen.set(*self.target, (0, 220, 0))

run(Chase)
```

- `python examples/chase.py` — opens the **browser emulator** at
  http://127.0.0.1:7777: a virtual Arcade Coder with clickable pads and live
  frames (stdlib only, no dependencies).
- `python examples/chase.py --hw` — the same game on the real board over BLE.
  On macOS run it through the permission-holding app bundle:
  `echo examples/chase.py > launch_target.txt && open ArcadeMinesweeper.app`.

API: `Screen.set/get/rect/clear` with display-RGB colours and (0,0) top-left;
`Game.start/on_press(x,y)/update(dt)/draw(screen)/end()`; `fps` picks the tick
rate; games auto-restart after `end()`. The BLE backend handles the colour
swap, Huffman-only compression, write pacing, press decoding, and reconnects.
See [examples/chase.py](examples/chase.py) (minimal) and
[examples/snake.py](examples/snake.py) (real-time).

The **entire 10-game arcade also runs in the emulator** — try every game with
no hardware at all:

```bash
python examples/full_arcade.py
```

## ArcadeOS — everything in one process

[arcadeos.py](arcadeos.py) is the way to run the whole platform: a home
screen of seven icons (games / deck / ko-pads / sequencer / visualizer /
rhythm / ambient). **Triple-tap the top-left pad** from anywhere to get home.
Idle for 10 minutes and it slips into ambient mode — one press returns you
to the app you were in (apps that are busy, like a playing sequencer, are
never interrupted). A dashboard at http://127.0.0.1:7770 (hosted:
[/arcadeos.html](https://hansstam86.github.io/arcade-coder-games/arcadeos.html))
shows what's running and switches apps remotely.

```bash
echo arcadeos_hw.py > launch_target.txt && open ArcadeMinesweeper.app
scripts/install_login.sh    # optional: start ArcadeOS at login
```

## Pixoo mirror

Mirror the board onto a paired **Divoom Pixoo 16**. On macOS the Pixoo 16 is
driven over its Bluetooth *serial* port (Classic SPP), not BLE: pair it in
System Settings so `/dev/cu.Pixoo` appears, then set `pixoo_mirror: true` in
`arcadeos.json`. Whatever the board shows plays on the Pixoo, scaled 12->16
(colour-reduced and paced for the link). `pixoo.py` is a standalone driver
too (image/brightness/solid-colour). Image encoding matches
jvandenbos/pixoo-python and virtualabs/pixoo-client.

## Scrolling marquee

[marquee.py](marquee.py): a scrolling-text display in a 3×5 pixel font
(A–Z, 0–9, punctuation), solid or animated-rainbow, with configurable speed.
Message hot-reloads from `marquee.json`, or set it live from the ArcadeOS
dashboard's message box (http://127.0.0.1:7770). An ArcadeOS app (cyan icon).

## Party mode — the board dances to live audio

[party.py](party.py): a 12-band spectrum analyzer with peak-hold dots, a
gradient from green to red, a bass-driven background pulse, and auto-gain.
By default it captures the Mac's **system audio** — anything playing, from
Spotify to the EP-133 through speakers — digitally via ScreenCaptureKit
(`sysaudio.swift` helper; grant the bundle Screen Recording). Falls back to
an audio input device (the EP-133's USB audio stream) when unavailable;
`party.json` picks source and device. Runs as an ArcadeOS app (rainbow icon).

## Notification center

Reads the macOS Notification Center via **NCReader.app** (build with
`scripts/build_ncreader.sh`; grant it Full Disk Access — macOS ties FDA to
the bundle identity and only honours it when launched via LaunchServices,
which ArcadeOS does). It POSTs each notification to the service webhook.

Every macOS notification queues on the board and **stays until you press a pad
to mark it read** (modal — it overrides the equalizer, games, and idle). Shows
the alert text scrolling with the source app name, a coloured border, unread-
count dots on the top row, and a pulsing dismiss bar. When the queue is empty
the board returns to what it was doing. `show_all` (default on) means *all*
notifications show; per-app rules add custom colour/EP-133 sound. Needs Full
Disk Access for the Notification Center source; the webhook always works.

## Notifications — see them on the board, hear them on the EP-133

ArcadeOS runs a notification service: rules map alerts (e.g. Slack) to a
coloured overlay on the board (border pulse / full flash / corner glow) over
whatever app is running, plus an EP-133 note (load a clap where the rule
points). Configure everything in the webapp at http://127.0.0.1:7760
(hosted: [/notify.html](https://hansstam86.github.io/arcade-coder-games/notify.html)).
Sources: the macOS Notification Center database (grant the app bundle Full
Disk Access — the webapp shows the status) and a universal webhook:
`curl -X POST http://127.0.0.1:7760/notify -d '{"app":"slack","title":"hi"}'`.

## ArcadeDeck — a customizable Stream Deck

[deck.py](deck.py) turns the board into a 12×12 macro pad. Everything is
configured in [deck.json](deck.json): pages of buttons with position, size,
colour, and an action — `shell` (any command), `open` (app/URL/file),
`applescript`, or `page` (switch profile pages). Buttons flash white on press
and green/red by exit code, and a button with a `status` check command polls
it on an interval and colours itself by the result (the included mute button
shows your real mute state).

```bash
python deck.py          # design your layout in the browser emulator
echo deck_hw.py > launch_target.txt && open ArcadeMinesweeper.app   # real board
```

While the deck runs it serves a **visual config editor at
http://127.0.0.1:7788** — also hosted at
[hansstam86.github.io/arcade-coder-games/deck.html](https://hansstam86.github.io/arcade-coder-games/deck.html),
which connects to your locally running deck (or falls back to a demo where
Save downloads `deck.json`). Buttons can be any size from 1×1 up (the default
layout is 2×2). click a pad to edit or create a button, pick colour
and action in the form, manage pages, and Save — the running deck hot-reloads
`deck.json` within a second, so the physical board updates live. Hand-editing
`deck.json` hot-reloads too.

The example config: mute toggle (with live state), Music play/pause, volume
up/down, screenshot-to-clipboard, display sleep, links, and an apps page.

## KO-pads — play a Teenage Engineering EP-133

[kopads.py](kopads.py) maps the grid to all 48 pads of an EP-133 K.O. II over
USB MIDI: four 3-row bands = groups A–D (notes 36-47/48-59/60-71/72-83),
columns = pads. Auto-finds the EP-133's MIDI port and reopens it on unplug.
Configure everything in the visual editor at http://127.0.0.1:7799 (also
hosted at [/kopads.html](https://hansstam86.github.io/arcade-coder-games/kopads.html)):
band colours and base notes, channel/velocity/note length, per-pad note and
colour overrides, and a send-test-note button. Saves hot-reload live.

```bash
echo kopads_hw.py > launch_target.txt && open ArcadeMinesweeper.app
```

## Rhythm game

[rhythm.py](rhythm.py): falling notes in four wide lanes — press the lane as
the note lands on the hit line, and a good hit **fires that lane's EP-133
pad**, so accurate play builds the beat out loud. Perfect/good judgment,
combos (every 8 heals), health bar on top, endless procedural chart with
rising tempo and density. `rhythm.json` sets lane pads, tempo range, and the
input-latency `offset` (raise it if your hits feel late over BLE).

```bash
echo rhythm_hw.py > launch_target.txt && open ArcadeMinesweeper.app
```

## Ambient mode

[ambient.py](ambient.py): the board as a living desk object. Seven scenes —
pixel clock with a day-cycle sky, fire, plasma, matrix rain, game of life
(self-reseeding), starfield with shooting stars, dvd bounce. Press any pad
for the next scene; auto-rotates every 10 minutes; dims itself at night.
Configure rotation, brightness, night hours, and 12/24h in `ambient.json`.

```bash
echo ambient_hw.py > launch_target.txt && open ArcadeMinesweeper.app
```

## Step sequencer

[seq.py](seq.py) makes the board a hardware sequencer driving the EP-133:
rows 0-9 are ten tracks (MIDI notes, default EP-133 group A pads), columns are
12 sixteenth-note steps. Tap to toggle steps while it plays; a dedicated
timing thread fires the MIDI with ~1 ms steady-state precision, independent of
the BLE frame rate. Bottom row: play/stop (pulses on the beat), tempo -/+,
clear (press twice). Pattern auto-saves to `seq.json` (hot-editable — change
track notes/colours there).

```bash
echo seq_hw.py > launch_target.txt && open ArcadeMinesweeper.app
```

## MIDI visualizer

[midiviz.py](midiviz.py) turns the board into a light show while you play the
EP-133 itself: every pad you hit spawns a velocity-sensitive, group-coloured
ripple at that pad's position (A orange / B yellow / C white / D red), and the
FX knobs (CC 12/13) tint the background. Pressing the board makes splashes too.

```bash
echo midiviz_hw.py > launch_target.txt && open ArcadeMinesweeper.app
```

## Setup (macOS)

```bash
git clone https://github.com/hansstam86/arcade-coder-games
cd arcade-coder-games
uv venv --python 3.11 .venv        # or python3.11 -m venv .venv
uv pip install --python .venv/bin/python 'bleak==0.22.3'
codesign --force --deep -s - ArcadeMinesweeper.app   # re-sign for your machine
echo arcade.py > launch_target.txt
open ArcadeMinesweeper.app
```

Power on the board, approve the Bluetooth permission prompt if one appears,
and watch `game.log`. The first run scans for the board and caches its
address in `device_config.json`. Switch games with:

```bash
echo whackamole.py > launch_target.txt && pkill -f 'minesweeper.py|whackamole.py'; open ArcadeMinesweeper.app
```

Stop everything with `pkill -f 'minesweeper.py|whackamole.py'`.

## Minesweeper rules on LEDs

Dim white = covered. Colours are neighbour-mine counts:
**1 blue · 2 green · 3 yellow · 4 orange · 5 magenta · 6 cyan · 7 white**;
revealed zeros go dark and flood open. Mine → red flash, new game.
Clear all 126 safe pads → green flash.

## Repo map

- `arcadecoder/` — the SDK: game API, browser emulator, BLE backend,
  protocol (canonical home of the protocol code)
- `examples/` — SDK example games
- `minesweeper.py` — BLE client + protocol encode/decode + minesweeper (the
  `Board` class here is the original plumbing)
- `arcade.py` — the 10-game launcher that runs on the board
- `whackamole.py` — whack-a-mole on the same plumbing
- `snake_upload.py`, `run_snake.py` — WIP on-board snake (uploaded XS JS)
- `builtin_probe.py` — automated dead-strip bisection over BLE
- `debug_board.py`, `observe_accel.py`, `control_test.py`, `takeover.py`,
  `scan.py` — diagnostics used during reverse engineering
- `test_logic.py`, `test_snake.mjs`, `test_snake2.mjs` — offline tests
  (canvas round-trip, captured-notification decode, game rules, snake sim)

## License

MIT
