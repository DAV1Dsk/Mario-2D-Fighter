import pgzero
import pgzrun
from pgzero.actor import Actor
import math
import pygame

# Game configuration
WIDTH = 800
HEIGHT = 600
TITLE = "Mario vs Bowser - 2D Fighting Game"

# Game state
game_state = "menu"  # menu, playing, paused
current_player = "mario"  # mario, bowser

class Fireball:
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction  # 1 for right, -1 for left
        self.velocity_x = 8 * direction
        self.velocity_y = -2  # Slight upward arc
        self.width = 32
        self.height = 32
        self.active = True
        
        # Animation state
        self.animation_frame = 0
        self.animation_timer = 0
        self.animation_speed = 4
        
        # Fireball animation frames (we'll create these)
        self.frames = ["fireball1", "fireball2", "fireball3", "fireball4"]
        
        # Create actor
        self.actor = Actor(self.frames[0])
        self.actor.pos = (self.x, self.y)
        
        # Outline-based hitbox points (relative to center)
        # These points define the fireball's actual shape for collision
        self.hitbox_points = [
            (-8, -12), (-12, -8), (-14, 0), (-12, 8), (-8, 12),
            (8, 12), (12, 8), (14, 0), (12, -8), (8, -12)
        ]
    
    def update(self):
        if not self.active:
            return
            
        # Apply physics
        self.velocity_y += 0.3  # Gravity effect
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Update animation
        self.animation_timer += 1
        if self.animation_timer >= self.animation_speed:
            self.animation_timer = 0
            self.animation_frame = (self.animation_frame + 1) % len(self.frames)
            self.actor.image = self.frames[self.animation_frame]
        
        # Update actor position
        self.actor.pos = (self.x, self.y)
        
        # Remove if off screen
        if self.x < -50 or self.x > WIDTH + 50 or self.y > HEIGHT + 50:
            self.active = False
    
    def get_hitbox_points(self):
        """Returns the actual hitbox points in world coordinates"""
        return [(self.x + px, self.y + py) for px, py in self.hitbox_points]
    
    def check_collision_with_point(self, px, py):
        """Check if a point is inside the fireball's outline"""
        # Use point-in-polygon algorithm for the fireball outline
        hitbox = self.get_hitbox_points()
        n = len(hitbox)
        inside = False
        
        p1x, p1y = hitbox[0]
        for i in range(1, n + 1):
            p2x, p2y = hitbox[i % n]
            if py > min(p1y, p2y):
                if py <= max(p1y, p2y):
                    if px <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or px <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def check_collision_with_rect(self, rx, ry, rw, rh):
        """Check collision with a rectangular area using outline detection"""
        # Check if any corner of the rectangle is inside the fireball
        corners = [
            (rx - rw//2, ry - rh//2),
            (rx + rw//2, ry - rh//2),
            (rx + rw//2, ry + rh//2),
            (rx - rw//2, ry + rh//2)
        ]
        
        for cx, cy in corners:
            if self.check_collision_with_point(cx, cy):
                return True
        
        # Also check if fireball center is inside the rectangle
        if (rx - rw//2 <= self.x <= rx + rw//2 and 
            ry - rh//2 <= self.y <= ry + rh//2):
            return True
            
        return False
    
    def draw(self):
        if self.active:
            self.actor.draw()
            
            # Debug: Draw hitbox outline (remove this in final version)
            if game_state == "playing":
                hitbox = self.get_hitbox_points()
                if len(hitbox) > 2:
                    pygame.draw.polygon(screen.surface, (255, 255, 0), hitbox, 2)

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
        
        # Fireball system
        self.fireballs = []
        self.fireball_cooldown = 0
        
        # Load stand animation frames
        self.stand_frames = [
            "stand1",
            "stand2", 
            "stand3"
        ]
        
        # Create actor for current frame
        self.actor = Actor(self.stand_frames[0])
        self.actor.pos = (self.x, self.y)
    
    def shoot_fireball(self):
        """Shoot a fireball in the direction Mario is facing"""
        if self.fireball_cooldown <= 0:
            direction = 1 if self.facing_right else -1
            offset_x = 30 if self.facing_right else -30
            fireball = Fireball(self.x + offset_x, self.y - 10, direction)
            self.fireballs.append(fireball)
            self.fireball_cooldown = 30  # 30 frames cooldown
    
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
        
        # Update fireball cooldown
        if self.fireball_cooldown > 0:
            self.fireball_cooldown -= 1
        
        # Update fireballs
        for fireball in self.fireballs[:]:  # Use slice copy for safe removal
            fireball.update()
            if not fireball.active:
                self.fireballs.remove(fireball)
        
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
        
        # Draw fireballs
        for fireball in self.fireballs:
            fireball.draw()

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
        
        # Draw fireball cooldown indicator
        if mario.fireball_cooldown > 0:
            screen.draw.text(f"Fireball: {mario.fireball_cooldown}", (50, 90), color="white", fontsize=16)
        else:
            screen.draw.text("Fireball: READY (Z)", (50, 90), color="white", fontsize=16)
    
    elif game_state == "menu":
        screen.draw.text("Mario vs Bowser", (WIDTH//2 - 150, HEIGHT//2 - 50), 
                        color="white", fontsize=48)
        screen.draw.text("Press SPACE to start", (WIDTH//2 - 120, HEIGHT//2 + 50), 
                        color="white", fontsize=24)
        screen.draw.text("Z = Fireball", (WIDTH//2 - 60, HEIGHT//2 + 100), 
                        color="white", fontsize=18)

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
        elif key == keys.Z:  # Fireball attack
            mario.shoot_fireball()

def on_key_up(key):
    if game_state == "playing":
        if key == keys.LEFT and mario.velocity_x < 0:
            mario.velocity_x = 0
        elif key == keys.RIGHT and mario.velocity_x > 0:
            mario.velocity_x = 0

pgzrun.go()
