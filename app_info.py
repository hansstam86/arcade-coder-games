"""Short description + quick usage guide for each ArcadeOS app.

Surfaced in the web App Organizer (click an app to see how it works). Keep each
`desc` to one line and `use` to a few short, board-accurate bullets.
"""

APP_INFO = {
    "games": {
        "desc": "Ten classic mini-games in one launcher.",
        "use": [
            "Tap a game tile to start playing.",
            "Play with the pads — controls vary per game.",
            "Includes minesweeper, tetris, snake, simon, connect four and more.",
        ],
    },
    "deck": {
        "desc": "A customizable macro pad (Stream Deck).",
        "use": [
            "Press a button to run its Mac action — launch an app, hotkey, or shortcut.",
            "Design your own layout in the editor at 127.0.0.1:7788.",
        ],
    },
    "kopads": {
        "desc": "Play pads for the Teenage Engineering EP-133.",
        "use": [
            "Tap pads to trigger EP-133 sounds over MIDI.",
            "Configure the pad mapping in the editor at 127.0.0.1:7799.",
        ],
    },
    "seq": {
        "desc": "A step sequencer for drum patterns.",
        "use": [
            "Tap grid cells to toggle steps in the pattern.",
            "It loops and plays through the EP-133; patterns are saved to seq.json.",
        ],
    },
    "midiviz": {
        "desc": "A live visualizer for the MIDI you play.",
        "use": [
            "Play the EP-133 (or any MIDI) and watch the board react.",
            "No controls — it's a display.",
        ],
    },
    "rhythm": {
        "desc": "A beat-matching rhythm game.",
        "use": [
            "Hit the pads in time with the marked targets.",
            "Your score climbs the closer you land to the beat.",
        ],
    },
    "ambient": {
        "desc": "A calm idle display — a live clock.",
        "use": [
            "Shows the time and gently dims at night.",
            "This is the default idle screen when nothing else is running.",
        ],
    },
    "party": {
        "desc": "A 12-band audio equalizer light show.",
        "use": [
            "Reacts to whatever audio your Mac is playing.",
            "Opens automatically when sound starts and returns to idle when it's quiet.",
        ],
    },
    "marquee": {
        "desc": "Scrolls any text across the board.",
        "use": [
            "Set the message from the dashboard at 127.0.0.1:7770.",
            "Also used to flash incoming notifications.",
        ],
    },
    "pomodoro": {
        "desc": "A Pomodoro focus / break timer.",
        "use": [
            "Press anywhere to start or pause.",
            "Amber pad (top-right) cycles presets: 25/5, 50/10, 15/3, 90/20.",
            "Blue pad (bottom-left) resets; white pad (bottom-right) skips the interval.",
            "The ring counts down and the board flashes between work and breaks.",
        ],
    },
    "countdown": {
        "desc": "A countdown timer you set on the board.",
        "use": [
            "Set the time: red − / green + for minutes (outer) and seconds (inner).",
            "Press the green START in the middle to begin.",
            "Running: centre = pause, top-left = stop, top-right = +1 min, bottom-left = restart.",
            "At zero it flashes red and sounds an alarm — press to stop it.",
        ],
    },
    "weather": {
        "desc": "Animated local weather and forecast.",
        "use": [
            "Shows current conditions as an animated scene plus the temperature.",
            "The bottom row is a 12-hour forecast ribbon (blue = cold, red = hot).",
            "Tap to toggle temperature / feels-like. Set your location in weather.json.",
        ],
    },
    "onair": {
        "desc": "An on-air busy light driven by your mic.",
        "use": [
            "Turns red ON AIR when your microphone is in use, green when free.",
            "Tap to cycle mode: AUTO (follow the mic) / force-ON / force-OFF.",
            "The marker on the left edge shows the current mode.",
        ],
    },
    "stopwatch": {
        "desc": "A count-up stopwatch with laps.",
        "use": [
            "Centre = start / pause, left pad = lap, right pad = reset.",
            "A lap flashes its split time in yellow while the clock keeps running.",
        ],
    },
    "doodle": {
        "desc": "A free-draw sketch pad.",
        "use": [
            "Tap the drawing area to paint with the current colour.",
            "Bottom row: 10-colour palette, then eraser and clear. Your art is saved.",
        ],
    },
    "worldclock": {
        "desc": "Clocks for several time zones.",
        "use": [
            "Shows one city's time with a day/night sky tint; dots mark the city.",
            "Tap anywhere to cycle cities. Edit the list in worldclock.json.",
        ],
    },
    "pet": {
        "desc": "A desk pet that lives on your habits.",
        "use": [
            "Tap the pet to play, tap the apple (bottom-left) to feed it.",
            "It naps while your mic is live and at night; neglect makes it hungry.",
            "Bottom gauges = happiness, energy, fullness; it keeps living while away.",
        ],
    },
    "ttt": {
        "desc": "Noughts & crosses (tic-tac-toe).",
        "use": [
            "Tap a cell to place your mark — X (red) first, then O (cyan).",
            "Three in a row wins and pulses; tap after a game to replay.",
            "Right-edge pad toggles a perfect CPU opponent (play solo).",
        ],
    },
    "spaces": {
        "desc": "AeroSpace / Omachy workspace switcher.",
        "use": [
            "3×3 grid = workspaces 1–9 (numpad layout). Focused one pulses; solid = has windows.",
            "Tap a tile to jump to that workspace on your Mac.",
        ],
    },
    "focus": {
        "desc": "A directional focus pad for AeroSpace / Omachy.",
        "use": [
            "The whole board is a D-pad — tap a side to move window focus that way.",
            "Tap the centre to toggle mode: cyan FOCUS (move highlight) / orange MOVE (drag window).",
            "After each move it flashes the name of the app you landed on.",
        ],
    },
    "gifs": {
        "desc": "Plays animated GIFs on the board.",
        "use": [
            "Drop any .gif into the gifs/ folder — it plays looped, downsampled to 12×12.",
            "Tap to skip to the next GIF. Pixel-art GIFs look best.",
        ],
    },
    "fireworks": {
        "desc": "A particle firework show.",
        "use": [
            "Runs by itself — rockets rise and burst into glowing showers.",
            "Tap anywhere to launch an extra one from that spot.",
        ],
    },
    "reactions": {
        "desc": "A live engagement/reaction meter.",
        "use": [
            "Shows a count that climbs with confetti — point it at a LinkedIn post's reactions.",
            "Drive it with POST /meter {\"count\": N}. Milestones flash the board.",
        ],
    },
    "ambilight": {
        "desc": "The board glows your screen's colours.",
        "use": [
            "Mirrors a live, blurred average of your Mac screen onto the board.",
            "Great behind you on camera. Needs Screen Recording; tune brightness/saturation in ambilight.json.",
        ],
    },
    "oracle": {
        "desc": "Ask the crystal ball; it answers.",
        "use": [
            "Tap the orb — it swirls while it thinks, then a fortune scrolls in gold.",
            "Local fortunes by default; set ai:true (+ token) in oracle.json for real Claude.",
        ],
    },
    "remote": {
        "desc": "An AI-controlled canvas.",
        "use": [
            "Shows whatever an agent draws via the dashboard's POST /paint.",
            "Used to let NanoClaw / Claude draw pictures on the board.",
        ],
    },
    "studioclock": {
        "desc": "A broadcast-style clock (camera background).",
        "use": [
            "Big HH:MM with a red seconds ring sweeping the border + hour ticks.",
            "Tap to scroll the date. Stays on; edit clock_24h/accent/brightness in studioclock.json.",
        ],
    },
    "backdrop": {
        "desc": "Calm ambient scenes — a camera background.",
        "use": [
            "Five slow visuals: aurora, lo-fi rainy window, jellyfish, flow field, lava lamp.",
            "Tap anywhere to cycle; the name flashes and your choice is remembered.",
            "Stays on (won't idle away). Set brightness in backdrop.json.",
        ],
    },
    "sand": {
        "desc": "A falling-sand physics sandbox.",
        "use": [
            "Pick an element on the bottom row, then tap the play area to drop it.",
            "Sand piles & sinks in water, water flows, fire burns wood & is doused by water.",
            "Bottom row also has an eraser and a clear button.",
        ],
    },
    "chessclock": {
        "desc": "A two-player chess clock.",
        "use": [
            "Tap your own half to end your move — your clock stops, theirs starts.",
            "Left middle pad cycles presets (1/3/5/10 min) & resets; right pad pauses.",
            "Run out of time and your flag falls (you lose). Orange = P1, blue = P2.",
        ],
    },
    "dice": {
        "desc": "A fair dice roller for board games.",
        "use": [
            "Tap anywhere to roll; the dice tumble then settle.",
            "Right-edge pad toggles one or two dice.",
            "Results come from a cryptographic RNG (secrets) — provably fair.",
        ],
    },
    "othello": {
        "desc": "Othello / Reversi — flank & flip.",
        "use": [
            "Tap a glowing square to place a disc; flanked lines flip to you.",
            "Dark (blue) first, then Light (white); no move = auto-pass.",
            "Most discs wins (bottom bar = live score). Right pad toggles a CPU.",
        ],
    },
    "ytmusic": {
        "desc": "A remote for YouTube Music (and other players).",
        "use": [
            "Transport: ⏮ previous · ⏯ play-pause · ⏭ next — works even in the background.",
            "The bars up top react to the music.",
            "Use the bottom-row volume − / mute / volume + pads.",
        ],
    },
}


def info_for(name: str) -> dict:
    return APP_INFO.get(name, {"desc": "", "use": []})
