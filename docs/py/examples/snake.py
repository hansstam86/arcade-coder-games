#!/usr/bin/env python3
"""Snake on the arcadecoder SDK — press where you want the snake to go."""
import random
import time

from arcadecoder import Game, run


class Snake(Game):
    fps = 12

    def start(self):
        self.body = [(5, 5), (4, 5), (3, 5)]
        self.d = (1, 0)
        self.pending = None
        self.food = (9, 5)
        self.eaten = 0
        self.grow = 0
        self.step = 0.30
        self.acc = 0.0
        self.dead = False

    def on_press(self, x, y):
        hx, hy = self.body[0]
        dx, dy = x - hx, y - hy
        if dx == dy == 0:
            return
        nd = (1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
        if (nd[0] + self.d[0], nd[1] + self.d[1]) != (0, 0):
            self.pending = nd

    def update(self, dt):
        if self.dead:
            return
        self.acc += dt
        while self.acc >= self.step:
            self.acc -= self.step
            if self.pending:
                self.d, self.pending = self.pending, None
            hx, hy = self.body[0]
            nh = ((hx + self.d[0]) % 12, (hy + self.d[1]) % 12)
            if nh in self.body:
                self.dead = True
                self.died_at = time.monotonic()
                return
            self.body.insert(0, nh)
            if nh == self.food:
                self.eaten += 1
                self.grow += 2
                self.step = max(0.15, self.step * 0.96)
                while True:
                    p = (random.randrange(12), random.randrange(12))
                    if p not in self.body:
                        self.food = p
                        break
            if self.grow:
                self.grow -= 1
            else:
                self.body.pop()

    def draw(self, screen):
        screen.clear()
        if self.dead:
            for i in range(min(self.eaten, 144)):
                screen.set(i % 12, i // 12, (0, 200, 0))
            if time.monotonic() - self.died_at > 3:
                self.end()
            return
        for i, (x, y) in enumerate(self.body):
            screen.set(x, y, (60, 255, 60) if i == 0 else (0, 170, 0))
        screen.set(*self.food, (255, 0, 0))


if __name__ == "__main__":
    run(Snake)
