import { execSync } from "node:child_process";
const src = JSON.parse(execSync(`./.venv/bin/python -c "import json,snake_upload as s;print(json.dumps(s.SNEK))"`).toString());

const E = {
  spriteClasses: [], tilts: {}, update: null,
  Sprite: function (c, x, y, dx, dy) { this.costume = c; this.x = x; this.y = y; },
  makeGameCostume: (w, h, px) => ({ w, h, px: [...px] }),
  WhenTilted: (d, fn) => (E.tilts[d] = fn),
  WhenGameUpdates: (fn) => (E.update = fn),
};
new Function("Engine", "Costumes", src)(E, {});
const S = E.spriteClasses[0][0];
const green = (i) => S.costume.px[i * 3 + 1];
const red = (i) => S.costume.px[i * 3 + 2];

E.update();                       // head 66 -> 67
if (S.costume.px.length !== 432) throw new Error("bad fb size");
if (green(67) !== 99) throw new Error("head not at 67");
if (red(6) !== 99) throw new Error("food not at 6");

// steer: FORWARD from 67 -> 55 -> 43 -> 31 -> 19 -> 7 ; LEFT -> 6 (food!)
E.tilts.FORWARD();
for (let i = 0; i < 5; i++) E.update();
if (green(7) !== 99) throw new Error("head not at 7");
E.tilts.LEFT(); E.update();
if (green(6) !== 99) throw new Error("did not reach food");
const F2 = (6 * 7 + 31) % 144;    // 73
if (red(F2) !== 99) throw new Error("food did not respawn at " + F2);
// body grows to 4 over next ticks
E.update(); E.update();
let body = [...Array(144).keys()].filter((i) => green(i) === 99).length;
if (body !== 4) throw new Error("expected body 4, got " + body);

// torus wrap: LEFT for 200 ticks, no crash, body intact
for (let i = 0; i < 200; i++) E.update();

// self-collision reset: grow snake, then reverse into own body
E.tilts.BACK(); E.update(); E.tilts.FORWARD(); E.update();
body = [...Array(144).keys()].filter((i) => green(i) === 99).length;
if (body !== 1) throw new Error("reverse should reset body, got " + body);
for (let i = 0; i < 50; i++) E.update();  // still alive after reset
console.log("SNAKE V2 SIM PASSED");
