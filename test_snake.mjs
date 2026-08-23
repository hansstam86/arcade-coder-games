// Simulate the uploaded XS sources against a mock Engine.
import { execSync } from "node:child_process";

const sources = JSON.parse(
  execSync(
    `./.venv/bin/python -c "import json,snake_upload as s;print(json.dumps({n:src for n,src,_f,_w in s.STAGES}))"`,
    { cwd: new URL(".", import.meta.url).pathname }
  ).toString()
);

function makeEngine() {
  const E = {
    spriteClasses: [],
    tilts: {},
    update: null,
    Sprite: function (costume, x, y, dx, dy) {
      this.costume = costume; this.x = x; this.y = y; this.speedX = dx; this.speedY = dy;
    },
    makeGameCostume: (w, h, px) => ({ w, h, px: [...px] }),
    WhenTilted: (d, fn) => (E.tilts[d] = fn),
    WhenGameUpdates: (fn) => (E.update = fn),
    WhenShaken: () => {},
    mathRandomInt: (a, b) => a + Math.floor(Math.random() * (b - a + 1)),
    tick() {
      // engine moves sprites by speed each tick, then calls update
      for (const cls of E.spriteClasses) for (const s of cls) { s.x += s.speedX; s.y += s.speedY; }
      if (E.update) E.update();
    },
  };
  return E;
}

function run(name, src) {
  const E = makeEngine();
  new Function("Engine", "Costumes", src)(E, {});
  return E;
}

// --- chk: checkerboard ------------------------------------------------------
{
  const E = run("chk", sources.chk);
  E.tick();
  const px = E.spriteClasses[0][0].costume.px;
  if (px.length !== 432) throw new Error("chk: bad framebuffer size");
  // (0,0): i=0 parity 0 -> device byte 0 (blue channel) = 99
  if (px[0] !== 99 || px[1] !== 0) throw new Error("chk: wrong pixel 0");
  // i=1 parity 1 -> byte 3*1+1 (green) = 99
  if (px[4] !== 99) throw new Error("chk: wrong pixel 1");
  console.log("chk OK");
}

// --- tlt: tilt moves sprite -------------------------------------------------
{
  const E = run("tlt", sources.tlt);
  const S = E.spriteClasses[0][0];
  E.tilts.RIGHT();
  E.tick(); E.tick();
  if (S.x !== 8 || S.y !== 6) throw new Error(`tlt: expected (8,6), got (${S.x},${S.y})`);
  E.tilts.FORWARD();
  for (let i = 0; i < 7; i++) E.tick();
  if (S.y !== 11) throw new Error(`tlt: wrap failed, y=${S.y}`); // 6 -> up 7 with wrap: 6,5,4,3,2,1,12,11
  console.log("tlt OK");
}

// --- snek: full game --------------------------------------------------------
{
  const E = run("snek", sources.sk);
  const S = E.spriteClasses[0][0];
  E.tick(); // head 66 -> right -> 67
  let px = S.costume.px;
  const green = (i) => px[i * 3 + 1];
  if (green(67) !== 99) throw new Error("snek: head not at 67");
  if (px[30 * 3 + 2] !== 255) throw new Error("snek: food not at 30");
  // steer FORWARD (up), walk until we eat food at 30 = (6,2); head at (7,5)
  E.tilts.LEFT(); E.tick();          // 66
  E.tilts.FORWARD();
  E.tick(); E.tick(); E.tick();      // 54, 42, 30 -> eat
  px = S.costume.px;
  if (green(30) !== 99) throw new Error("snek: head should be on old food cell");
  if (px[30 * 3 + 2] === 255) throw new Error("snek: food should have moved");
  const newFood = (30 * 7 + 31) % 144;
  if (px[newFood * 3 + 2] !== 255) throw new Error("snek: new food wrong place");
  // body should now grow to 5 over next ticks; count green pixels after 4 more ticks
  E.tick(); E.tick(); E.tick(); E.tick();
  px = S.costume.px;
  const bodyLen = [...Array(144).keys()].filter((i) => px[i * 3 + 1] === 99).length;
  if (bodyLen !== 5) throw new Error(`snek: expected body 5, got ${bodyLen}`);
  // wrap: keep going FORWARD across the top edge for 144 ticks, no crash
  for (let i = 0; i < 144; i++) E.tick();
  console.log("snek OK");
}
console.log("ALL SIM TESTS PASSED");
