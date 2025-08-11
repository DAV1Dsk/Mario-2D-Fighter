# Mario vs Bowser - 2D Fighting Game

A 2D fighting game built with Pygame Zero featuring Mario and Bowser.

## Setup

1. Install Python 3.7 or higher
2. Create and activate a virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the Game

Make sure your virtual environment is activated, then run:
```
pgzrun main.py
```

## Controls

- **SPACE**: Start game / Jump
- **LEFT/RIGHT**: Move Mario
- **UP**: Jump (when on ground)

## Current Features

- Mario stand animation (3 frames)
- Basic physics (gravity, ground collision)
- Health bar display
- Menu system

## File Structure

```
├── main.py              # Main game file
├── images/              # Game sprites
│   ├── stand1.png       # Mario stand frame 1
│   ├── stand2.png       # Mario stand frame 2
│   └── stand3.png       # Mario stand frame 3
├── sounds/              # Audio files (to be added)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Development Status

- ✅ Mario stand animation implemented
- ✅ Basic physics system
- ✅ Game structure
- 🔄 Bowser character (planned)
- 🔄 Fighting mechanics (planned)
- 🔄 Sound effects (planned)
