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

- **SPACE**: Start game
- **Mario (Left side)**:
  - **LEFT/RIGHT**: Move Mario
  - **UP**: Jump (when on ground)
- **Bowser (Right side)**:
  - **A/D**: Move Bowser
  - **W**: Jump (when on ground)

**Note**: Both characters start facing each other in a classic fighting game stance.

## Current Features

- Mario stand animation (3 frames)
- Bowser stand animation (7 frames)
- Peach's Castle background
- Character shadows for better visibility
- Castle-themed health bars (gold for Mario, orange-red for Bowser)
- Basic physics (gravity, ground collision)
- Health bar display for both characters
- Menu system
- Dual character controls (Arrow keys for Mario, WASD for Bowser)

## File Structure

```
├── main.py              # Main game file
├── images/              # Game sprites
│   ├── stand1.png       # Mario stand frame 1
│   ├── stand2.png       # Mario stand frame 2
│   ├── stand3.png       # Mario stand frame 3
│   ├── bowser_stand 1.png  # Bowser stand frame 1
│   ├── bowser_stand 2.png  # Bowser stand frame 2
│   ├── bowser_stand 3.png  # Bowser stand frame 3
│   ├── bowser_stand 4.png  # Bowser stand frame 4
│   ├── bowser_stand 5.png  # Bowser stand frame 5
│   ├── bowser_stand 6.png  # Bowser stand frame 6
│   ├── bowser_stand 7.png  # Bowser stand frame 7
│   └── peachs_castle.png  # Castle background
├── sounds/              # Audio files (to be added)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Development Status

- ✅ Mario stand animation implemented
- ✅ Bowser stand animation implemented
- ✅ Basic physics system
- ✅ Game structure
- ✅ Dual character controls
- ✅ Peach's Castle background
- 🔄 Sprite transparency (blue background removal needed)
- 🔄 Fighting mechanics (planned)
- 🔄 Sound effects (planned)

## Notes

**Sprite Background Issue**: The Mario and Bowser sprites currently have blue backgrounds that may clash with the castle background. To fix this:
1. Open the sprite images in an image editor (GIMP, Photoshop, etc.)
2. Select the blue background areas
3. Make them transparent
4. Save as PNG with transparency
