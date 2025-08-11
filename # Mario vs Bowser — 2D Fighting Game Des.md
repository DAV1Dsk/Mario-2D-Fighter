# Mario vs Bowser — 2D Fighting Game Design (Pygame Zero)

**Premise**

Bowser has kidnapped Princess Peach once again. The Mushroom Kingdom’s peace hangs in the balance, and a single brawl at Peach’s Castle will decide the day. Play as Mario or Bowser in a classic 2D arena—walk, run, jump, and attack to win and rescue (or recapture) the princess.

---

## Table of contents

1. Overview
2. Stage: Peach’s Castle
3. Characters
4. Core mechanics
5. Controls
6. Movement and physics
7. Attacks and movesets
8. Ultimate attacks
9. Animation & sprite notes
10. Audio & music
11. UI / HUD
12. Game modes
13. Victory conditions
14. Implementation notes & file structure (Pygame Zero)
15. Assets checklist
16. Legal / IP note

---

## 1. Overview

A lightweight 2D fighter built with **Pygame Zero** for simple Python-based game development. Designed for local 1v1 play on a single stage (Peach’s Castle). Built so additional characters and stages can be added later.

Target platform: Desktop (Windows, macOS, Linux) running Python 3 + Pygame Zero.

---

## 2. Stage: Peach’s Castle

**Layout:** Single flat platform with short raised ledges on both ends.

**Interactive elements:**

* Crumbling center tile.
* Background cannon firing harmless visuals.

**Visual style:** Castle interior with stained glass, banners, torches, and throne.

---

## 3. Characters

### Mario

* Agile, high jump, moderate attack damage.

### Bowser

* Slow, low jump, very high damage.

Core animations: idle, walk, run, jump (up/peak/fall/land), crouch, light attack, heavy attack, special, ultimate, hurt, knockout, win pose.

---

## 4. Core mechanics

* Health system (100 HP each).
* Optional stamina/meter for specials.
* Ultimate meter fills on damage dealt/received.
* Hitstun and knockback.
* Rectangle hitboxes.

---

## 5. Controls (keyboard default)

* Left / Right arrows: Move
* Down: Crouch
* Z: Light attack
* X: Heavy attack
* C: Special
* V: Ultimate attack (when meter full)
* Space: Jump
* Shift: Run

---

## 6. Movement and physics (suggested values)

* Gravity: 0.6 per frame
* Jump velocity: Mario 12, Bowser 9
* Walk speed: Mario 3, Bowser 2
* Run speed: Mario 5, Bowser 3

---

## 7. Attacks and movesets

**Mario**

* Light: Quick jab.
* Heavy: Shoulder bash.
* Special: Fireball.
* Air: Down stomp.

**Bowser**

* Light: Claw swipe.
* Heavy: Ground pound.
* Special: Fire breath.
* Air: Tail slam.

---

## 8. Ultimate attacks

**Mario — Super Star Barrage**

* **Visuals:** Mario glows with rainbow colors from a Super Star.
* **Execution:** Mario becomes invincible for 5 seconds, speed and jump height increase, and he unleashes rapid-fire punches and kicks.
* **Damage:** Light hits do small damage but come in rapid succession, overwhelming opponents.
* **Activation:** Press `V` when ultimate meter is full.

**Bowser — King Koopa’s Inferno Smash**

* **Visuals:** Bowser roars, flames engulf his body, and the ground shakes.
* **Execution:** He leaps into the air and slams down, creating a massive shockwave of fire across the stage.
* **Damage:** High base damage with huge knockback; can KO at mid-health.
* **Activation:** Press `V` when ultimate meter is full.

---

## 9. Animation & sprite notes

* Uniform frame sizes (64×64).
* Horizontal strips per animation.
* Separate effects spritesheet (fire, shockwave, sparkles).

---

## 10. Audio & music

* Looping castle theme.
* SFX: jump, land, attack, hit, KO, ultimate activation.

---

## 11. UI / HUD

* Health bars top-left and top-right.
* Ultimate meter under health bars.
* Optional timer.

---

## 12. Game modes

* Local 1v1
* CPU Battle (basic AI)
* Training mode

---

## 13. Victory conditions

* Reduce HP to 0
* Higher HP when timer ends

---

## 14. Implementation notes & file structure (Pygame Zero)

```
project-root/
  ├─ images/
  │   ├─ mario_spritesheet.png
  │   ├─ bowser_spritesheet.png
  │   └─ effects.png
  ├─ sounds/
  │   ├─ bgm_castle_loop.wav
  │   ├─ jump.wav
  │   ├─ hit.wav
  │   └─ ultimate.wav
  ├─ main.py
  ├─ characters.py
  ├─ stage.py
  ├─ config.py
  └─ README.md
```

* Use `Actor` objects for characters and projectiles.
* Update physics in `update()` function.
* Draw in `draw()` function.
* Manage input via `keyboard` object.
* Track ultimate meter state per character.

---

## 15. Assets checklist

* Mario spritesheet (64×64)
* Bowser spritesheet (64×64)
* Effects spritesheet
* Background art
* Audio files (including ultimate SFX)

---

## 16. Legal / IP note

This project references Nintendo characters for educational use only.

---
 