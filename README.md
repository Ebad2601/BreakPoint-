# BreakPoint

A real-time roguelike sports survival game built in Python 3 using the curses library — zero dependencies, runs in any terminal.

Every move stresses your athlete's bones across 7 skeletal regions in real-time. Sprint too hard and your hamstring goes. Take a bad tackle and your knee fractures. Fracture a load-bearing bone — it's permanent game over. Your career is done.

## How to run
```bash
python3 breakpoint.py
```

Requires Python 3.8+ and a terminal window at least 75 columns × 32 rows.

## Controls
| Key | Action |
|-----|--------|
| WASD / Arrow keys | Move |
| SPACE | Sprint (high bone stress) |
| Z | Slide tackle |
| X | Jump / header |
| P | Pause |
| Q | Quit |

## What this demonstrates
- Full-screen real-time game engine using Python curses at 30fps
- Opponent state-machine AI (defend / chase / shoot)
- Physics-based ball simulation with friction, bounce, and velocity
- Skeletal injury system: 7 bone regions, real-time stress accumulation
- Particle effect system, event feed, combo multiplier
- 4 difficulty levels with scaling opponent count and speed
- Permadeath — fracture a critical bone and the session ends permanently
- Persistent leaderboard saved to JSON

## Built by
Muhammad Ebadur Rahman Siddiqui  
OrthoAI Project · Pre-Medical Student · Karachi, Pakistan
