#!/usr/bin/env python3
"""
██████╗ ██████╗ ███████╗ █████╗ ██╗  ██╗██████╗  ██████╗ ██╗███╗   ██╗████████╗
██╔══██╗██╔══██╗██╔════╝██╔══██╗██║ ██╔╝██╔══██╗██╔═══██╗██║████╗  ██║╚══██╔══╝
██████╔╝██████╔╝█████╗  ███████║█████╔╝ ██████╔╝██║   ██║██║██╔██╗ ██║   ██║
██╔══██╗██╔══██╗██╔══╝  ██╔══██║██╔═██╗ ██╔═══╝ ██║   ██║██║██║╚██╗██║   ██║
██████╔╝██║  ██║███████╗██║  ██║██║  ██╗██║     ╚██████╔╝██║██║ ╚████║   ██║
╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝

  Real-time roguelike sports survival. Every move damages your bones.
  Permadeath. Procedural matches. Skeletal injury physics.
  Built by Mark | Python 3 + curses | Zero dependencies

  HOW TO PLAY:
    Arrow keys / WASD  — move your athlete
    SPACE              — sprint (fast but high bone stress)
    Z                  — slide tackle
    X                  — jump / header
    P                  — pause
    Q                  — quit

  OBJECTIVE:
    Score goals. Survive. Your bones degrade with every action.
    Push too hard → stress fracture → you're done. Permanently.
    Chain actions for combo multipliers. Reach the final whistle.
"""

import curses
import curses.ascii
import time
import random
import math
import json
import os
import sys
import collections
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

VERSION = "1.0.0"
SCORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "breakpoint_scores.json")

# Field dimensions (will be adjusted to terminal size)
FIELD_W = 70
FIELD_H = 22
HUD_H   = 8

# Bone regions with their base stress thresholds
BONES = {
    "L.Ankle":   {"max": 100, "stress": 0, "symbol": "LA", "regen": 0.3},
    "R.Ankle":   {"max": 100, "stress": 0, "symbol": "RA", "regen": 0.3},
    "L.Knee":    {"max": 120, "stress": 0, "symbol": "LK", "regen": 0.2},
    "R.Knee":    {"max": 120, "stress": 0, "symbol": "RK", "regen": 0.2},
    "Hamstring": {"max": 90,  "stress": 0, "symbol": "HS", "regen": 0.25},
    "Lumbar":    {"max": 110, "stress": 0, "symbol": "LB", "regen": 0.15},
    "Shoulder":  {"max": 100, "stress": 0, "symbol": "SH", "regen": 0.2},
}
BONE_NAMES = list(BONES.keys())

# Action bone costs (which bones each action stresses)
ACTION_COSTS = {
    "walk":    {"L.Ankle": 1.2, "R.Ankle": 1.2, "L.Knee": 0.8, "R.Knee": 0.8},
    "sprint":  {"L.Ankle": 4.5, "R.Ankle": 4.5, "L.Knee": 3.5, "R.Knee": 3.5, "Hamstring": 5.0},
    "slide":   {"L.Knee": 8.0,  "R.Knee": 8.0,  "Hamstring": 6.0, "L.Ankle": 5.0},
    "jump":    {"L.Ankle": 6.0, "R.Ankle": 6.0, "L.Knee": 5.0,  "R.Knee": 5.0, "Lumbar": 4.0},
    "tackle":  {"Shoulder": 10.0, "Lumbar": 7.0, "L.Knee": 4.0},
    "collision":{"Lumbar": 12.0, "Shoulder": 8.0, "L.Knee": 5.0, "R.Knee": 5.0},
    "header":  {"Lumbar": 3.0, "Shoulder": 2.0},
}

# Match durations (seconds of real time per half)
DIFFICULTY = {
    "Rookie":      {"duration": 45,  "opponents": 3, "ball_speed": 0.4, "label": "ROOKIE"},
    "Pro":         {"duration": 70,  "opponents": 5, "ball_speed": 0.6, "label": "PRO"},
    "Elite":       {"duration": 90,  "opponents": 7, "ball_speed": 0.8, "label": "ELITE"},
    "Breakpoint":  {"duration": 120, "opponents": 9, "ball_speed": 1.0, "label": "BREAKPOINT"},
}

# Colours (curses pair indices)
COL_FIELD    = 1
COL_PLAYER   = 2
COL_BALL     = 3
COL_OPPONENT = 4
COL_GOAL     = 5
COL_HUD      = 6
COL_DANGER   = 7
COL_WARN     = 8
COL_SAFE     = 9
COL_TITLE    = 10
COL_WHITE    = 11
COL_STRESS_LOW  = 12
COL_STRESS_MED  = 13
COL_STRESS_HIGH = 14
COL_FLASH    = 15

# ═══════════════════════════════════════════════════════════════
# SCORE PERSISTENCE
# ═══════════════════════════════════════════════════════════════

def load_scores():
    try:
        with open(SCORES_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_score(entry: dict):
    scores = load_scores()
    scores.append(entry)
    scores.sort(key=lambda x: x.get("score", 0), reverse=True)
    try:
        with open(SCORES_FILE, "w") as f:
            json.dump(scores[:20], f, indent=2)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# GAME ENTITIES
# ═══════════════════════════════════════════════════════════════

class Vec2:
    """Simple 2D vector."""
    __slots__ = ("x", "y")
    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)
    def __add__(self, o): return Vec2(self.x + o.x, self.y + o.y)
    def __sub__(self, o): return Vec2(self.x - o.x, self.y - o.y)
    def __mul__(self, s): return Vec2(self.x * s, self.y * s)
    def dist(self, o): return math.hypot(self.x - o.x, self.y - o.y)
    def norm(self):
        m = math.hypot(self.x, self.y)
        return Vec2(self.x/m, self.y/m) if m > 0 else Vec2(0, 0)
    def copy(self): return Vec2(self.x, self.y)
    def ix(self): return int(round(self.x))
    def iy(self): return int(round(self.y))


class Player:
    """The human-controlled athlete."""

    SPRINT_STAMINA_COST = 2.5
    STAMINA_REGEN       = 1.8

    def __init__(self, field_w, field_h):
        self.pos        = Vec2(field_w * 0.25, field_h * 0.5)
        self.vel        = Vec2(0, 0)
        self.stamina    = 100.0
        self.has_ball   = False
        self.score      = 0
        self.combo      = 0
        self.combo_timer= 0.0
        self.invincible = 0.0   # seconds of post-collision immunity
        self.bones      = {k: {"stress": 0.0, "max": v["max"], "regen": v["regen"]}
                           for k, v in BONES.items()}
        self.injury_log  = []   # list of (bone, event_str)
        self.actions_taken = collections.Counter()
        self.is_sprinting  = False
        self.is_sliding    = False
        self.slide_timer   = 0.0
        self.jump_timer    = 0.0
        self.is_jumping    = False
        self.flash_timer   = 0.0
        self.total_distance = 0.0

    def max_stress_bone(self) -> tuple:
        worst = max(self.bones.items(), key=lambda kv: kv[1]["stress"] / kv[1]["max"])
        ratio = worst[1]["stress"] / worst[1]["max"]
        return worst[0], ratio

    def overall_stress(self) -> float:
        total = sum(b["stress"] / b["max"] for b in self.bones.values())
        return total / len(self.bones)

    def apply_stress(self, action: str) -> str | None:
        """Apply bone stress for an action. Returns injury string if fracture occurs."""
        costs = ACTION_COSTS.get(action, {})
        for bone, cost in costs.items():
            self.bones[bone]["stress"] = min(
                self.bones[bone]["max"],
                self.bones[bone]["stress"] + cost
            )
        # Check fractures
        for bone, data in self.bones.items():
            if data["stress"] >= data["max"]:
                return bone
        return None

    def regen_bones(self, dt: float):
        for bone, data in self.bones.items():
            regen = BONES[bone]["regen"]
            data["stress"] = max(0.0, data["stress"] - regen * dt)

    def stress_pct(self, bone: str) -> float:
        return self.bones[bone]["stress"] / self.bones[bone]["max"]

    def move(self, dx, dy, sprinting: bool, dt: float, field_w: int, field_h: int) -> str | None:
        """Move player, apply stress, return injury bone name or None."""
        if self.slide_timer > 0 or self.jump_timer > 0:
            return None

        speed = 12.0 if sprinting else 7.0
        self.is_sprinting = sprinting

        if sprinting:
            self.stamina = max(0, self.stamina - self.SPRINT_STAMINA_COST * dt * 60)
            if self.stamina < 5:
                speed = 5.0  # exhausted

        magnitude = math.hypot(dx, dy)
        if magnitude > 0:
            ndx, ndy = dx / magnitude, dy / magnitude
            new_x = self.pos.x + ndx * speed * dt
            new_y = self.pos.y + ndy * speed * dt

            # Field boundaries
            new_x = max(1.0, min(field_w - 2.0, new_x))
            new_y = max(1.0, min(field_h - 2.0, new_y))

            moved = math.hypot(new_x - self.pos.x, new_y - self.pos.y)
            self.total_distance += moved
            self.pos.x, self.pos.y = new_x, new_y

            action = "sprint" if sprinting else "walk"
            return self.apply_stress(action)
        return None


class Ball:
    """The football / ball object."""

    def __init__(self, field_w, field_h):
        self.pos     = Vec2(field_w * 0.5, field_h * 0.5)
        self.vel     = Vec2(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3))
        self.owner   = None  # 'player', 'opponent_N', or None
        self.field_w = field_w
        self.field_h = field_h

    def update(self, dt: float):
        if self.owner:
            return
        friction = 0.92
        self.pos.x += self.vel.x
        self.pos.y += self.vel.y
        self.vel.x *= friction
        self.vel.y *= friction

        # Bounce off walls
        if self.pos.x <= 1 or self.pos.x >= self.field_w - 2:
            self.vel.x *= -0.8
            self.pos.x = max(1.0, min(self.field_w - 2.0, self.pos.x))
        if self.pos.y <= 1 or self.pos.y >= self.field_h - 2:
            self.vel.y *= -0.8
            self.pos.y = max(1.0, min(self.field_h - 2.0, self.pos.y))

    def kick(self, direction: Vec2, power: float):
        self.owner = None
        self.vel = direction * power


class Opponent:
    """AI-controlled opponent athlete."""

    def __init__(self, field_w, field_h, idx: int, difficulty: float):
        # Spread opponents around the right side
        self.pos = Vec2(
            field_w * random.uniform(0.4, 0.85),
            field_h * (0.1 + (idx * 0.8 / 9))
        )
        self.vel       = Vec2(0, 0)
        self.speed     = 4.5 + difficulty * 2.5
        self.has_ball  = False
        self.idx       = idx
        self.state     = "defend"   # defend | chase | shoot
        self.think_timer = 0.0
        self.field_w   = field_w
        self.field_h   = field_h

    def update(self, player: Player, ball: Ball, dt: float):
        self.think_timer -= dt
        if self.think_timer <= 0:
            self.think_timer = random.uniform(0.3, 0.8)
            self._decide(player, ball)

        # Move toward target
        dist_ball = self.pos.dist(ball.pos)
        if dist_ball < 1.5:
            self.has_ball = True
            ball.owner = f"opp_{self.idx}"

        if self.state == "chase":
            target = ball.pos
        elif self.state == "shoot":
            target = Vec2(2, self.field_h * 0.5)  # Aim at player goal
        else:
            # Defend: stay between ball and their goal
            target = Vec2(
                min(self.field_w - 5, ball.pos.x + 10),
                ball.pos.y
            )

        dx = target.x - self.pos.x
        dy = target.y - self.pos.y
        dist = math.hypot(dx, dy)
        if dist > 0.5:
            self.pos.x += (dx / dist) * self.speed * dt
            self.pos.y += (dy / dist) * self.speed * dt
        self.pos.x = max(1.0, min(self.field_w - 2.0, self.pos.x))
        self.pos.y = max(1.0, min(self.field_h - 2.0, self.pos.y))

    def _decide(self, player: Player, ball: Ball):
        dist_to_ball = self.pos.dist(ball.pos)
        if dist_to_ball < 15:
            self.state = "chase"
        elif self.has_ball:
            self.state = "shoot"
        else:
            self.state = "defend"


class Particle:
    """Visual effect particle."""
    def __init__(self, x, y, char, colour, life):
        self.x     = x
        self.y     = y
        self.char  = char
        self.colour = colour
        self.life  = life
        self.max_life = life
        self.vx    = random.uniform(-0.3, 0.3)
        self.vy    = random.uniform(-0.3, 0.3)

    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        self.life -= dt

    @property
    def alive(self): return self.life > 0


class Event:
    """Match event message."""
    def __init__(self, text: str, colour: int, duration: float = 2.5):
        self.text     = text
        self.colour   = colour
        self.life     = duration

    def update(self, dt): self.life -= dt
    @property
    def alive(self): return self.life > 0


# ═══════════════════════════════════════════════════════════════
# GAME STATE
# ═══════════════════════════════════════════════════════════════

class GameState:
    def __init__(self, difficulty_key: str, player_name: str, field_w: int, field_h: int):
        diff = DIFFICULTY[difficulty_key]
        self.difficulty_key = difficulty_key
        self.player_name    = player_name
        self.field_w        = field_w
        self.field_h        = field_h
        self.diff           = diff

        self.player    = Player(field_w, field_h)
        self.ball      = Ball(field_w, field_h)
        self.opponents = [
            Opponent(field_w, field_h, i, ["Rookie","Pro","Elite","Breakpoint"].index(difficulty_key) / 3.0)
            for i in range(diff["opponents"])
        ]
        self.particles  : list[Particle] = []
        self.events     : list[Event]    = []

        self.match_time  = float(diff["duration"])
        self.half_time   = self.match_time / 2
        self.elapsed     = 0.0
        self.halftime_done = False
        self.paused      = False
        self.game_over   = False
        self.game_over_reason = ""
        self.won         = False
        self.score_player    = 0
        self.score_opponent  = 0

        # Goal positions (centre of each goal)
        self.goal_y_top    = field_h // 2 - 3
        self.goal_y_bot    = field_h // 2 + 3
        self.player_goal_x = 0
        self.opp_goal_x    = field_w - 1

        # Injury events
        self.injury_events: list[str] = []

        self.last_tick = time.monotonic()

    def add_particles(self, x, y, char="*", colour=COL_BALL, count=6, life=0.8):
        for _ in range(count):
            self.particles.append(Particle(x, y, char, colour, life))

    def add_event(self, text: str, colour: int = COL_HUD, duration: float = 2.5):
        self.events.insert(0, Event(text, colour, duration))
        if len(self.events) > 5:
            self.events = self.events[:5]

    def check_goal(self) -> str | None:
        """Return 'player', 'opponent', or None."""
        bx, by = self.ball.pos.ix(), self.ball.pos.iy()
        # Opponent goal (right side)
        if bx >= self.field_w - 2 and self.goal_y_top <= by <= self.goal_y_bot:
            return "player"
        # Player goal (left side)
        if bx <= 1 and self.goal_y_top <= by <= self.goal_y_bot:
            return "opponent"
        return None

    def reset_ball(self):
        self.ball.pos = Vec2(self.field_w * 0.5, self.field_h * 0.5)
        self.ball.vel = Vec2(random.uniform(-1, 1), random.uniform(-0.5, 0.5))
        self.ball.owner = None
        self.player.has_ball = False
        for opp in self.opponents:
            opp.has_ball = False

    def apply_fracture(self, bone: str):
        """Handle a bone fracture event."""
        self.player.injury_log.append(bone)
        self.player.flash_timer = 0.8
        self.add_particles(
            self.player.pos.ix(), self.player.pos.iy(),
            "X", COL_DANGER, count=12, life=1.2
        )
        self.add_event(f"⚠ {bone.upper()} FRACTURE — STRESS LIMIT REACHED!", COL_DANGER, 4.0)
        # Weaken the bone permanently
        self.player.bones[bone]["max"] = max(
            20, self.player.bones[bone]["max"] * 0.55
        )
        self.player.bones[bone]["stress"] = self.player.bones[bone]["max"] * 0.7
        # If it's a load-bearing bone, game over
        critical = ["L.Knee", "R.Knee", "L.Ankle", "R.Ankle", "Lumbar"]
        if bone in critical:
            self.game_over = True
            self.game_over_reason = f"Career-ending {bone} fracture"

    def tick(self, dt: float, keys_pressed: set, key_just_pressed: set):
        if self.paused or self.game_over:
            return

        self.elapsed += dt

        # Halftime
        if not self.halftime_done and self.elapsed >= self.half_time:
            self.halftime_done = True
            self.add_event("HALF TIME — REST PERIOD  (30s stamina recovery)", COL_TITLE, 5.0)
            self.player.stamina = min(100, self.player.stamina + 35)
            self.reset_ball()

        # Full time
        if self.elapsed >= self.match_time:
            self.game_over = True
            self.won = (self.score_player > self.score_opponent)
            self.game_over_reason = "Final whistle"
            return

        # ── PLAYER INPUT ──────────────────────────────────────────────
        dx, dy = 0, 0
        sprinting = False

        if ord('w') in keys_pressed or curses.KEY_UP in keys_pressed:    dy -= 1
        if ord('s') in keys_pressed or curses.KEY_DOWN in keys_pressed:   dy += 1
        if ord('a') in keys_pressed or curses.KEY_LEFT in keys_pressed:   dx -= 1
        if ord('d') in keys_pressed or curses.KEY_RIGHT in keys_pressed:  dx += 1
        if ord(' ') in keys_pressed and self.player.stamina > 10:
            sprinting = True

        # Slide tackle
        if ord('z') in key_just_pressed and self.player.slide_timer <= 0:
            self.player.slide_timer = 0.5
            self.player.is_sliding = True
            fracture = self.player.apply_stress("slide")
            self.add_event("SLIDE TACKLE!", COL_WARN, 1.2)
            if fracture:
                self.apply_fracture(fracture)
            self.player.actions_taken["slides"] += 1

        # Jump / header
        if ord('x') in key_just_pressed and self.player.jump_timer <= 0:
            self.player.jump_timer = 0.35
            self.player.is_jumping = True
            fracture = self.player.apply_stress("jump")
            if fracture:
                self.apply_fracture(fracture)
            self.player.actions_taken["jumps"] += 1

        # Move player
        if dx != 0 or dy != 0:
            fracture = self.player.move(dx, dy, sprinting, dt, self.field_w, self.field_h)
            if fracture:
                self.apply_fracture(fracture)
            self.player.actions_taken["moves"] += 1

        # Timers
        if self.player.slide_timer > 0:
            self.player.slide_timer = max(0, self.player.slide_timer - dt)
            if self.player.slide_timer == 0:
                self.player.is_sliding = False
        if self.player.jump_timer > 0:
            self.player.jump_timer = max(0, self.player.jump_timer - dt)
            if self.player.jump_timer == 0:
                self.player.is_jumping = False
        if self.player.flash_timer > 0:
            self.player.flash_timer = max(0, self.player.flash_timer - dt)
        if self.player.invincible > 0:
            self.player.invincible = max(0, self.player.invincible - dt)

        # Stamina regen when not sprinting
        if not sprinting:
            self.player.stamina = min(100, self.player.stamina + Player.STAMINA_REGEN * dt)

        # Bone regen
        self.player.regen_bones(dt)

        # Combo timer
        if self.player.combo > 0:
            self.player.combo_timer -= dt
            if self.player.combo_timer <= 0:
                self.player.combo = 0

        # ── BALL PICKUP ──────────────────────────────────────────────
        if not self.ball.owner:
            dist = self.player.pos.dist(self.ball.pos)
            if dist < 2.0:
                self.ball.owner = "player"
                self.player.has_ball = True

        # Ball follows player if they have it
        if self.ball.owner == "player":
            offset_x = 1.5 if (dx >= 0 or dx == 0) else -1.5
            offset_y = 1.0 if (dy >= 0 or dy == 0) else -1.0
            self.ball.pos.x = self.player.pos.x + offset_x
            self.ball.pos.y = self.player.pos.y + offset_y

            # Auto-kick toward goal if near it
            dist_to_goal = abs(self.ball.pos.x - self.opp_goal_x)
            if dist_to_goal < 12 and (ord(' ') in key_just_pressed or ord('x') in key_just_pressed):
                direction = Vec2(1, random.uniform(-0.3, 0.3)).norm()
                power = 8.0 + (self.player.stamina / 100) * 4.0
                self.ball.kick(direction, power)
                self.player.has_ball = False
                self.player.actions_taken["shots"] += 1
                self.add_event("SHOT ON GOAL!", COL_WARN, 1.5)

        # ── BALL UPDATE ──────────────────────────────────────────────
        self.ball.update(dt)

        # ── GOAL CHECK ──────────────────────────────────────────────
        scorer = self.check_goal()
        if scorer == "player":
            self.score_player += 1
            multi = max(1, self.player.combo)
            pts = 100 * multi
            self.player.score += pts
            self.player.combo += 1
            self.player.combo_timer = 8.0
            self.add_particles(self.opp_goal_x, self.field_h // 2, "★", COL_TITLE, 20, 1.5)
            self.add_event(
                f"GOAL!!! {'×'+str(multi)+' COMBO ' if multi > 1 else ''}+{pts}pts",
                COL_TITLE, 4.0
            )
            self.player.actions_taken["goals"] += 1
            self.reset_ball()
        elif scorer == "opponent":
            self.score_opponent += 1
            self.player.combo = 0
            self.add_event("OPPONENT SCORES — defend harder!", COL_DANGER, 3.0)
            self.reset_ball()

        # ── OPPONENTS ──────────────────────────────────────────────
        for opp in self.opponents:
            opp.update(self.player, self.ball, dt)

            # Opponent takes ball
            if not self.ball.owner or self.ball.owner == "player":
                dist = opp.pos.dist(self.ball.pos)
                if dist < 1.8:
                    if self.ball.owner == "player":
                        self.player.has_ball = False
                        self.player.combo = 0
                        self.add_event("DISPOSSESSED!", COL_WARN, 1.5)
                    self.ball.owner = f"opp_{opp.idx}"
                    opp.has_ball = True

            # Opponent kicks ball
            if opp.has_ball and opp.state == "shoot":
                direction = Vec2(self.player_goal_x - opp.pos.x,
                                 self.field_h * 0.5 - opp.pos.y).norm()
                power = self.diff["ball_speed"] * 10
                self.ball.kick(direction, power)
                opp.has_ball = False
                if self.ball.owner == f"opp_{opp.idx}":
                    self.ball.owner = None

            # Ball follows opponent
            if self.ball.owner == f"opp_{opp.idx}":
                self.ball.pos.x = opp.pos.x - 1.2
                self.ball.pos.y = opp.pos.y

            # Collision with player
            if self.player.invincible <= 0:
                dist = opp.pos.dist(self.player.pos)
                if dist < 1.5:
                    self.player.invincible = 1.2
                    fracture = self.player.apply_stress("collision")
                    self.player.flash_timer = 0.4
                    self.add_particles(self.player.pos.ix(), self.player.pos.iy(),
                                       "!", COL_DANGER, 8, 0.8)
                    if fracture:
                        self.apply_fracture(fracture)
                    else:
                        self.add_event("COLLISION!", COL_DANGER, 1.0)

        # ── PARTICLES ──────────────────────────────────────────────
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        # ── EVENTS ──────────────────────────────────────────────────
        for e in self.events:
            e.update(dt)
        self.events = [e for e in self.events if e.alive]


# ═══════════════════════════════════════════════════════════════
# RENDERER
# ═══════════════════════════════════════════════════════════════

class Renderer:
    def __init__(self, screen: curses.window, field_w: int, field_h: int):
        self.screen   = screen
        self.field_w  = field_w
        self.field_h  = field_h
        self._init_colours()

    def _init_colours(self):
        curses.start_color()
        curses.use_default_colors()
        # (pair_index, fg, bg)
        pairs = [
            (COL_FIELD,      curses.COLOR_GREEN,   -1),
            (COL_PLAYER,     curses.COLOR_CYAN,    -1),
            (COL_BALL,       curses.COLOR_YELLOW,  -1),
            (COL_OPPONENT,   curses.COLOR_RED,     -1),
            (COL_GOAL,       curses.COLOR_WHITE,   -1),
            (COL_HUD,        curses.COLOR_CYAN,    -1),
            (COL_DANGER,     curses.COLOR_RED,     -1),
            (COL_WARN,       curses.COLOR_YELLOW,  -1),
            (COL_SAFE,       curses.COLOR_GREEN,   -1),
            (COL_TITLE,      curses.COLOR_YELLOW,  -1),
            (COL_WHITE,      curses.COLOR_WHITE,   -1),
            (COL_STRESS_LOW, curses.COLOR_GREEN,   -1),
            (COL_STRESS_MED, curses.COLOR_YELLOW,  -1),
            (COL_STRESS_HIGH,curses.COLOR_RED,     -1),
            (COL_FLASH,      curses.COLOR_WHITE,   curses.COLOR_RED),
        ]
        for idx, fg, bg in pairs:
            try:
                curses.init_pair(idx, fg, bg)
            except Exception:
                pass

    def _safe_addch(self, y, x, ch, attr=0):
        try:
            h, w = self.screen.getmaxyx()
            if 0 <= y < h and 0 <= x < w - 1:
                self.screen.addch(y, x, ch, attr)
        except Exception:
            pass

    def _safe_addstr(self, y, x, text, attr=0):
        try:
            h, w = self.screen.getmaxyx()
            if 0 <= y < h and 0 <= x < w:
                avail = w - x - 1
                if avail > 0:
                    self.screen.addstr(y, x, text[:avail], attr)
        except Exception:
            pass

    def draw_field(self, state: GameState):
        fw, fh = self.field_w, self.field_h
        field_attr = curses.color_pair(COL_FIELD)
        goal_attr  = curses.color_pair(COL_GOAL) | curses.A_BOLD

        # Top/bottom borders
        border_line = "+" + "─" * (fw - 2) + "+"
        self._safe_addstr(0, 0, border_line, field_attr)
        self._safe_addstr(fh - 1, 0, border_line, field_attr)

        # Side walls + field markings
        for row in range(1, fh - 1):
            self._safe_addch(row, 0,      "│", field_attr)
            self._safe_addch(row, fw - 1, "│", field_attr)

            # Centre line
            if row > 0 and row < fh - 1:
                self._safe_addch(row, fw // 2, "┊", curses.color_pair(COL_WHITE) | curses.A_DIM)

        # Centre circle (ASCII approximation)
        cx, cy = fw // 2, fh // 2
        circle_pts = [
            (cy - 3, cx), (cy + 3, cx),
            (cy - 2, cx - 2), (cy - 2, cx + 2),
            (cy + 2, cx - 2), (cy + 2, cx + 2),
            (cy,     cx - 4), (cy,     cx + 4),
        ]
        for (row, col) in circle_pts:
            self._safe_addch(row, col, "·", curses.color_pair(COL_WHITE) | curses.A_DIM)

        # Goals
        goal_top = state.goal_y_top
        goal_bot = state.goal_y_bot
        for row in range(goal_top, goal_bot + 1):
            self._safe_addch(row, 0,      "▌", goal_attr)
            self._safe_addch(row, fw - 1, "▐", goal_attr)

        # Penalty boxes
        for row in range(goal_top - 1, goal_bot + 2):
            self._safe_addch(row, 6,      "┆", curses.color_pair(COL_WHITE) | curses.A_DIM)
            self._safe_addch(row, fw - 7, "┆", curses.color_pair(COL_WHITE) | curses.A_DIM)

    def draw_player(self, state: GameState):
        p = state.player
        x, y = p.pos.ix(), p.pos.iy()

        if p.flash_timer > 0 and int(p.flash_timer * 8) % 2 == 0:
            attr = curses.color_pair(COL_FLASH) | curses.A_BOLD
        elif p.is_sliding:
            attr = curses.color_pair(COL_WARN) | curses.A_BOLD
        elif p.is_jumping:
            attr = curses.color_pair(COL_TITLE) | curses.A_BOLD
        elif p.is_sprinting:
            attr = curses.color_pair(COL_PLAYER) | curses.A_BOLD
        else:
            attr = curses.color_pair(COL_PLAYER) | curses.A_BOLD

        char = "⚡" if p.is_sprinting else ("▼" if p.is_sliding else "▲")
        # curses can't always do unicode, fallback
        try:
            self._safe_addstr(y, x, char, attr)
        except Exception:
            self._safe_addch(y, x, "@", attr)

    def draw_ball(self, state: GameState):
        bx, by = state.ball.pos.ix(), state.ball.pos.iy()
        if state.ball.owner == "player":
            attr = curses.color_pair(COL_TITLE) | curses.A_BOLD
        elif state.ball.owner and state.ball.owner.startswith("opp"):
            attr = curses.color_pair(COL_DANGER) | curses.A_BOLD
        else:
            attr = curses.color_pair(COL_BALL) | curses.A_BOLD
        self._safe_addch(by, bx, "O", attr)

    def draw_opponents(self, state: GameState):
        for opp in state.opponents:
            x, y = opp.pos.ix(), opp.pos.iy()
            attr = curses.color_pair(COL_OPPONENT) | curses.A_BOLD
            ch = "X" if opp.has_ball else "x"
            self._safe_addch(y, x, ch, attr)

    def draw_particles(self, state: GameState):
        for p in state.particles:
            x, y = int(p.x), int(p.y)
            alpha = p.life / p.max_life
            if alpha > 0.6:
                attr = curses.color_pair(p.colour) | curses.A_BOLD
            elif alpha > 0.3:
                attr = curses.color_pair(p.colour)
            else:
                attr = curses.color_pair(p.colour) | curses.A_DIM
            self._safe_addch(y, x, p.char, attr)

    def draw_hud(self, state: GameState, hud_y: int):
        p = state.player
        screen_w = self.screen.getmaxyx()[1]

        # ── ROW 0: separator
        self._safe_addstr(hud_y, 0, "═" * min(screen_w - 1, self.field_w),
                          curses.color_pair(COL_HUD) | curses.A_BOLD)

        # ── ROW 1: score + time
        time_left   = max(0, state.match_time - state.elapsed)
        mins        = int(time_left // 60)
        secs        = int(time_left % 60)
        half_label  = "2nd HALF" if state.elapsed >= state.half_time else "1st HALF"
        score_str   = f"  {state.player_name[:10]}  {state.score_player} : {state.score_opponent}  OPP"
        time_str    = f"  ⏱ {mins:02d}:{secs:02d}  {half_label}"
        pts_str     = f"  PTS: {p.score}"
        combo_str   = f"  COMBO ×{p.combo}" if p.combo > 1 else ""
        hud1 = score_str + time_str + pts_str + combo_str

        score_attr = curses.color_pair(COL_TITLE) | curses.A_BOLD
        self._safe_addstr(hud_y + 1, 0, hud1, score_attr)

        # ── ROW 2: stamina bar
        stam_pct = int(p.stamina)
        stam_bar_w = 20
        filled = int((stam_pct / 100) * stam_bar_w)
        stam_bar = "█" * filled + "░" * (stam_bar_w - filled)
        stam_col = COL_SAFE if stam_pct > 50 else (COL_WARN if stam_pct > 20 else COL_DANGER)
        self._safe_addstr(hud_y + 2, 2, f"STAMINA [{stam_bar}] {stam_pct:3d}%",
                          curses.color_pair(stam_col))

        # ── ROW 3-5: bone stress meters
        bones_per_row = 4
        bone_list = list(p.bones.items())
        row_offset = 0
        col_offset = 0
        for i, (bone, data) in enumerate(bone_list):
            ratio = data["stress"] / data["max"]
            bar_w = 8
            filled = int(ratio * bar_w)
            bar = "█" * filled + "░" * (bar_w - filled)
            if ratio >= 0.85:    col = COL_DANGER
            elif ratio >= 0.60:  col = COL_STRESS_HIGH
            elif ratio >= 0.35:  col = COL_STRESS_MED
            else:                col = COL_STRESS_LOW

            label = bone[:8].ljust(8)
            entry = f"{label}[{bar}]{int(ratio*100):3d}% "
            x_pos = 2 + col_offset * 26
            y_pos = hud_y + 3 + row_offset
            self._safe_addstr(y_pos, x_pos, entry, curses.color_pair(col))

            col_offset += 1
            if col_offset >= bones_per_row:
                col_offset = 0
                row_offset += 1

        # ── ROW 6: event feed
        if state.events:
            ev = state.events[0]
            self._safe_addstr(hud_y + 6, 2, f"▶ {ev.text[:screen_w - 6]}",
                              curses.color_pair(ev.colour) | curses.A_BOLD)

        # ── ROW 7: controls reminder
        ctrl = "  [WASD/↑↓←→] Move  [SPACE] Sprint  [Z] Slide  [X] Jump  [P] Pause  [Q] Quit"
        self._safe_addstr(hud_y + 7, 0, ctrl[:screen_w - 1],
                          curses.color_pair(COL_WHITE) | curses.A_DIM)

    def render(self, state: GameState):
        self.screen.erase()
        self.draw_field(state)
        self.draw_opponents(state)
        self.draw_ball(state)
        self.draw_player(state)
        self.draw_particles(state)
        self.draw_hud(state, self.field_h)
        self.screen.refresh()


# ═══════════════════════════════════════════════════════════════
# SCREEN HELPERS
# ═══════════════════════════════════════════════════════════════

def draw_centered(screen, y, text, attr=0):
    _, w = screen.getmaxyx()
    x = max(0, (w - len(text)) // 2)
    try:
        screen.addstr(y, x, text[:w - 1], attr)
    except Exception:
        pass

def wait_key(screen):
    screen.nodelay(False)
    screen.getch()
    screen.nodelay(True)


def title_screen(screen) -> tuple[str, str] | None:
    """Show title screen, return (player_name, difficulty_key) or None to quit."""
    curses.curs_set(0)
    screen.nodelay(False)
    h, w = screen.getmaxyx()

    banner = [
        "██████╗ ██████╗ ███████╗ █████╗ ██╗  ██╗██████╗  ██████╗ ██╗███╗   ██╗████████╗",
        "██╔══██╗██╔══██╗██╔════╝██╔══██╗██║ ██╔╝██╔══██╗██╔═══██╗██║████╗  ██║╚══██╔══╝",
        "██████╔╝██████╔╝█████╗  ███████║█████╔╝ ██████╔╝██║   ██║██║██╔██╗ ██║   ██║   ",
        "██╔══██╗██╔══██╗██╔══╝  ██╔══██║██╔═██╗ ██╔═══╝ ██║   ██║██║██║╚██╗██║   ██║   ",
        "██████╔╝██║  ██║███████╗██║  ██║██║  ██╗██║     ╚██████╔╝██║██║ ╚████║   ██║   ",
        "╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝   ",
    ]

    diff_keys = list(DIFFICULTY.keys())
    selected_diff = 0
    name = "ATHLETE"

    while True:
        screen.erase()

        # Banner
        start_y = max(1, (h - 20) // 2)
        title_attr = curses.color_pair(COL_TITLE) | curses.A_BOLD
        for i, line in enumerate(banner):
            x = max(0, (w - len(line)) // 2)
            try:
                screen.addstr(start_y + i, x, line[:w-1], title_attr)
            except Exception:
                pass

        y = start_y + 8
        draw_centered(screen, y,     "Real-time roguelike sports survival  ·  Permadeath  ·  Skeletal injury physics",
                      curses.color_pair(COL_WHITE) | curses.A_DIM)
        draw_centered(screen, y + 1, "Every move stresses your bones. Fracture a knee. Game over. Permanently.",
                      curses.color_pair(COL_WARN))

        y += 3
        draw_centered(screen, y, f"PLAYER NAME:  [ {name:<16} ]",
                      curses.color_pair(COL_HUD) | curses.A_BOLD)
        y += 1
        draw_centered(screen, y, "(Press E to edit name)",
                      curses.color_pair(COL_WHITE) | curses.A_DIM)

        y += 2
        draw_centered(screen, y, "── SELECT DIFFICULTY ──",
                      curses.color_pair(COL_HUD) | curses.A_BOLD)
        y += 1

        for i, dk in enumerate(diff_keys):
            d = DIFFICULTY[dk]
            label = f"  {dk:<12}  {d['duration']}s match  ·  {d['opponents']} opponents  "
            attr = (curses.color_pair(COL_TITLE) | curses.A_BOLD | curses.A_REVERSE
                    if i == selected_diff
                    else curses.color_pair(COL_WHITE))
            draw_centered(screen, y + i, label, attr)

        y += len(diff_keys) + 1
        draw_centered(screen, y,     "↑ / ↓  Select difficulty",
                      curses.color_pair(COL_WHITE) | curses.A_DIM)
        draw_centered(screen, y + 1, "ENTER  Start match",
                      curses.color_pair(COL_SAFE) | curses.A_BOLD)
        draw_centered(screen, y + 2, "H  High scores     Q  Quit",
                      curses.color_pair(COL_WHITE) | curses.A_DIM)

        screen.refresh()
        key = screen.getch()

        if key == curses.KEY_UP and selected_diff > 0:
            selected_diff -= 1
        elif key == curses.KEY_DOWN and selected_diff < len(diff_keys) - 1:
            selected_diff += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            return name, diff_keys[selected_diff]
        elif key == ord('q') or key == ord('Q'):
            return None
        elif key == ord('e') or key == ord('E'):
            name = edit_name(screen, name)
        elif key == ord('h') or key == ord('H'):
            show_high_scores(screen)


def edit_name(screen, current: str) -> str:
    h, w = screen.getmaxyx()
    prompt = "Enter name (max 16 chars, ENTER to confirm): "
    y = h // 2
    x = max(0, (w - len(prompt) - 18) // 2)
    curses.echo()
    curses.curs_set(1)
    try:
        screen.addstr(y, x, prompt, curses.color_pair(COL_HUD))
        screen.refresh()
        raw = screen.getstr(y, x + len(prompt), 16)
        name = raw.decode("utf-8", errors="ignore").strip()[:16] or current
    except Exception:
        name = current
    curses.noecho()
    curses.curs_set(0)
    return name.upper()


def show_high_scores(screen):
    scores = load_scores()
    screen.erase()
    h, w = screen.getmaxyx()
    draw_centered(screen, 2, "── HIGH SCORES ──", curses.color_pair(COL_TITLE) | curses.A_BOLD)
    if not scores:
        draw_centered(screen, 5, "No scores yet. Play a match!", curses.color_pair(COL_WHITE))
    else:
        for i, s in enumerate(scores[:15]):
            line = f"  {i+1:>2}.  {s.get('name','?'):<16}  {s.get('score',0):>7} pts  {s.get('difficulty','?'):<12}  {s.get('goals',0)}G  {s.get('date','')}"
            draw_centered(screen, 4 + i, line, curses.color_pair(COL_WHITE))
    draw_centered(screen, h - 2, "Press any key to return", curses.color_pair(COL_WHITE) | curses.A_DIM)
    screen.refresh()
    screen.nodelay(False)
    screen.getch()
    screen.nodelay(True)


def game_over_screen(screen, state: GameState):
    screen.nodelay(False)
    h, w = screen.getmaxyx()
    p = state.player
    won = state.won
    fracture = state.game_over_reason != "Final whistle"

    # Save score
    entry = {
        "name":       state.player_name,
        "score":      p.score,
        "difficulty": state.difficulty_key,
        "goals":      state.score_player,
        "date":       datetime.now().strftime("%d %b %Y"),
        "reason":     state.game_over_reason,
        "survived":   not fracture,
    }
    save_score(entry)

    for flash in range(6):
        screen.erase()
        if fracture:
            attr = curses.color_pair(COL_DANGER) | curses.A_BOLD
            if flash % 2 == 0:
                draw_centered(screen, h // 2 - 3, "█████  FRACTURE  █████", attr)
                draw_centered(screen, h // 2 - 2, f"  {state.game_over_reason.upper()}  ", attr)
                draw_centered(screen, h // 2 - 1, "PERMADEATH  —  CAREER OVER", attr)
        else:
            attr = curses.color_pair(COL_TITLE) | curses.A_BOLD
            result = "VICTORY" if won else "DEFEAT"
            draw_centered(screen, h // 2 - 3, f"FULL TIME  —  {result}", attr)
        screen.refresh()
        time.sleep(0.25)

    screen.erase()
    y = max(1, h // 2 - 8)
    draw_centered(screen, y,     "═" * 50, curses.color_pair(COL_HUD))
    if fracture:
        draw_centered(screen, y + 1, "  CAREER-ENDING INJURY  ", curses.color_pair(COL_DANGER) | curses.A_BOLD)
    else:
        result = "VICTORY" if won else "DEFEAT"
        draw_centered(screen, y + 1, f"  FINAL WHISTLE  —  {result}  ", curses.color_pair(COL_TITLE) | curses.A_BOLD)
    draw_centered(screen, y + 2, "═" * 50, curses.color_pair(COL_HUD))

    lines = [
        f"Player:          {state.player_name}",
        f"Difficulty:      {state.difficulty_key}",
        f"Result:          {state.score_player} – {state.score_opponent}",
        f"Total Score:     {p.score} pts",
        f"Best Combo:      ×{max(1, p.combo)}",
        f"Distance Run:    {p.total_distance:.0f}m",
        f"Shots on goal:   {p.actions_taken.get('shots', 0)}",
        f"Slides:          {p.actions_taken.get('slides', 0)}",
        f"Reason ended:    {state.game_over_reason}",
    ]
    for i, ln in enumerate(lines):
        draw_centered(screen, y + 4 + i, ln, curses.color_pair(COL_WHITE))

    if p.injury_log:
        draw_centered(screen, y + 4 + len(lines) + 1,
                      f"Fractures suffered: {', '.join(p.injury_log)}",
                      curses.color_pair(COL_DANGER))

    draw_centered(screen, h - 3, "Press R to play again  ·  Q to quit  ·  H for leaderboard",
                  curses.color_pair(COL_WHITE) | curses.A_DIM)
    screen.refresh()

    while True:
        key = screen.getch()
        if key in (ord('r'), ord('R')):
            return "retry"
        elif key in (ord('q'), ord('Q')):
            return "quit"
        elif key in (ord('h'), ord('H')):
            show_high_scores(screen)
            return "quit"


def pause_screen(screen):
    h, w = screen.getmaxyx()
    overlay_attr = curses.color_pair(COL_HUD) | curses.A_BOLD
    draw_centered(screen, h // 2 - 1, "  ── PAUSED ──  ", overlay_attr)
    draw_centered(screen, h // 2,     " P to resume · Q to quit ", curses.color_pair(COL_WHITE))
    screen.refresh()


# ═══════════════════════════════════════════════════════════════
# MAIN GAME LOOP
# ═══════════════════════════════════════════════════════════════

def run_game(screen, player_name: str, difficulty_key: str):
    curses.curs_set(0)
    screen.nodelay(True)
    screen.keypad(True)

    h, w = screen.getmaxyx()
    field_w = min(FIELD_W, w - 1)
    field_h = min(FIELD_H, h - HUD_H - 1)

    state    = GameState(difficulty_key, player_name, field_w, field_h)
    renderer = Renderer(screen, field_w, field_h)

    TARGET_FPS  = 30
    FRAME_TIME  = 1.0 / TARGET_FPS
    last_time   = time.monotonic()

    keys_held     = set()
    key_just_pressed = set()

    while True:
        now = time.monotonic()
        dt  = min(now - last_time, 0.1)   # cap at 100ms
        last_time = now

        # ── INPUT ──────────────────────────────────────────────
        key_just_pressed.clear()
        while True:
            key = screen.getch()
            if key == -1:
                break
            key_just_pressed.add(key)
            keys_held.add(key)

            if key == ord('q') or key == ord('Q'):
                return "quit"
            if key == ord('p') or key == ord('P'):
                state.paused = not state.paused

        # Simple key release simulation (held keys decay)
        # curses doesn't have true key-up events; we re-read each frame
        # Re-build held keys each frame from what's currently pressed
        keys_held = set(key_just_pressed)

        # ── UPDATE ─────────────────────────────────────────────
        if not state.game_over:
            state.tick(dt, keys_held, key_just_pressed)

        # ── RENDER ─────────────────────────────────────────────
        renderer.render(state)

        if state.paused and not state.game_over:
            pause_screen(screen)

        if state.game_over:
            result = game_over_screen(screen, state)
            return result

        # ── FRAME RATE ─────────────────────────────────────────
        elapsed_frame = time.monotonic() - now
        sleep_time = FRAME_TIME - elapsed_frame
        if sleep_time > 0:
            time.sleep(sleep_time)


# ═══════════════════════════════════════════════════════════════
# CURSES WRAPPER + ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main(screen):
    curses.curs_set(0)
    screen.keypad(True)

    # Init colours
    curses.start_color()
    curses.use_default_colors()
    pairs = [
        (COL_FIELD,      curses.COLOR_GREEN,   -1),
        (COL_PLAYER,     curses.COLOR_CYAN,    -1),
        (COL_BALL,       curses.COLOR_YELLOW,  -1),
        (COL_OPPONENT,   curses.COLOR_RED,     -1),
        (COL_GOAL,       curses.COLOR_WHITE,   -1),
        (COL_HUD,        curses.COLOR_CYAN,    -1),
        (COL_DANGER,     curses.COLOR_RED,     -1),
        (COL_WARN,       curses.COLOR_YELLOW,  -1),
        (COL_SAFE,       curses.COLOR_GREEN,   -1),
        (COL_TITLE,      curses.COLOR_YELLOW,  -1),
        (COL_WHITE,      curses.COLOR_WHITE,   -1),
        (COL_STRESS_LOW, curses.COLOR_GREEN,   -1),
        (COL_STRESS_MED, curses.COLOR_YELLOW,  -1),
        (COL_STRESS_HIGH,curses.COLOR_RED,     -1),
        (COL_FLASH,      curses.COLOR_WHITE,   curses.COLOR_RED),
    ]
    for idx, fg, bg in pairs:
        try:
            curses.init_pair(idx, fg, bg)
        except Exception:
            pass

    while True:
        result = title_screen(screen)
        if result is None:
            break
        player_name, difficulty = result

        while True:
            outcome = run_game(screen, player_name, difficulty)
            if outcome == "retry":
                continue
            break

    # Exit message
    screen.erase()
    h, w = screen.getmaxyx()
    draw_centered(screen, h // 2, "Thanks for playing BreakPoint.", curses.color_pair(COL_TITLE))
    draw_centered(screen, h // 2 + 1, "Built by Mark  |  OrthoAI  |  Python 3",
                  curses.color_pair(COL_WHITE) | curses.A_DIM)
    screen.refresh()
    time.sleep(1.5)


if __name__ == "__main__":
    # Check terminal size
    import shutil
    cols, rows = shutil.get_terminal_size()
    if cols < 75 or rows < 32:
        print(f"\n  BreakPoint needs at least 75×32 terminal.")
        print(f"  Your terminal: {cols}×{rows}")
        print(f"  Resize your terminal window and try again.\n")
        sys.exit(1)

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n  BreakPoint  |  Built by Mark  |  OrthoAI Project\n")
