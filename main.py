import pgzero
import pgzrun
from pgzero.actor import Actor
import math

# Game configuration
WIDTH = 800
HEIGHT = 600
TITLE = "Mario vs Bowser - 2D Fighting Game"

# Game state
game_state = "menu"  # menu, playing, paused
current_player = "mario"  # mario, bowser

class Mario:
    def __init__(self):
        self.x = 200
        self.y = HEIGHT - 100
        self.width = 64
        self.height = 64
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = True
        self.facing_right = True
        self.health = 100
        self.ultimate_meter = 0
        
        # Animation state
        self.current_animation = "stand"
        self.animation_frame = 0
        self.animation_timer = 0
        self.animation_speed = 8  # frames per animation update
        
        # Load stand animation frames
        self.stand_frames = [
            "stand1",
            "stand2", 
            "stand3"
        ]
        
        # Create actor for current frame
        self.actor = Actor(self.stand_frames[0])
        self.actor.pos = (self.x, self.y)
    
    def update(self):
        # Apply gravity
        if not self.on_ground:
            self.velocity_y += 0.6
        
        # Update position
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Ground collision
        if self.y >= HEIGHT - 100:  # Ground level
            self.y = HEIGHT - 100
            self.velocity_y = 0
            self.on_ground = True
        
        # Update animation
        self.animation_timer += 1
        if self.animation_timer >= self.animation_speed:
            self.animation_timer = 0
            self.animation_frame = (self.animation_frame + 1) % len(self.stand_frames)
            
            # Update actor image
            self.actor.image = self.stand_frames[self.animation_frame]
        
        # Update actor position
        self.actor.pos = (self.x, self.y)
        
        # Flip sprite based on facing direction
        self.actor.flip_x = not self.facing_right
    
    def draw(self):
        self.actor.draw()

# Create Mario instance
mario = Mario()

def update():
    if game_state == "playing":
        mario.update()

def draw():
    screen.fill((135, 206, 235))  # Sky blue background
    
    if game_state == "playing":
        # Draw ground
        screen.draw.filled_rect(Rect(0, HEIGHT - 50, WIDTH, 50), (34, 139, 34))
        
        # Draw Mario
        mario.draw()
        
        # Draw health bar
        screen.draw.filled_rect(Rect(50, 50, 200, 20), (255, 0, 0))
        screen.draw.filled_rect(Rect(50, 50, mario.health * 2, 20), (0, 255, 0))
        screen.draw.text("Mario HP: " + str(mario.health), (50, 30), color="white", fontsize=24)
    
    elif game_state == "menu":
        screen.draw.text("Mario vs Bowser", (WIDTH//2 - 150, HEIGHT//2 - 50), 
                        color="white", fontsize=48)
        screen.draw.text("Press SPACE to start", (WIDTH//2 - 120, HEIGHT//2 + 50), 
                        color="white", fontsize=24)

def on_key_down(key):
    global game_state
    
    if key == keys.SPACE and game_state == "menu":
        game_state = "playing"
    
    if game_state == "playing":
        if key == keys.LEFT:
            mario.velocity_x = -3
            mario.facing_right = False
        elif key == keys.RIGHT:
            mario.velocity_x = 3
            mario.facing_right = True
        elif key == keys.UP and mario.on_ground:
            mario.velocity_y = -12
            mario.on_ground = False

def on_key_up(key):
    if game_state == "playing":
        if key == keys.LEFT and mario.velocity_x < 0:
            mario.velocity_x = 0
        elif key == keys.RIGHT and mario.velocity_x > 0:
            mario.velocity_x = 0

pgzrun.go()
