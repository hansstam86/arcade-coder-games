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

The example config: mute toggle (with live state), Music play/pause, volume
up/down, screenshot-to-clipboard, display sleep, links, and an apps page.

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
