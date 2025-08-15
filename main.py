import pgzero
import pgzrun
from pgzero.actor import Actor
from pgzero.rect import Rect
import math
import pygame

# Game configuration
WIDTH = 1550
HEIGHT = 840

TITLE = "Mario vs Bowser - 2D Fighting Game"
# Nudge the perceived ground a bit lower to sit on the grass edge
GROUND_NUDGE_PX = 12
FLOOR_Y = HEIGHT - 50 + GROUND_NUDGE_PX
# Additional per-character floor nudges to align feet with the grass/bush base
MARIO_FLOOR_OFFSET = -11
BOWSER_FLOOR_OFFSET = -11
ATTACK_HITSTUN_BUFFER_TICKS = 8  # extra ticks after attack ends
CHARGE_OFFSET_X = 80  # base pixels to the right (left if facing left)
CHARGE_OFFSET_Y = 7  # base pixels upward from Mario's center (positive is down)
FIREBALL_HITBOX_OFFSET_X = -77  # horizontal offset applied to fireball collision mask and debug outline
FIREBALL_HITBOX_OFFSET_Y = -4   # vertical offset applied to fireball collision mask and debug outline
MARIO_BOX_OFFSET_X = -91  # calibration: negative moves boxes left
MARIO_BOX_OFFSET_Y = -10  # calibration: negative moves boxes up
HAMMER_ACTIVE_START_RATIO = 0.5  # hammer becomes active in the later half of the swing
HAMMER_YELLOW_COLOR = (255, 255, 0, 255)
HAMMER_YELLOW_TOLERANCE = (80, 80, 80, 255)
HAMMER_HITBOX_OFFSET_X = -60  # calibration for hammer mask alignment (negative = left)
HAMMER_HITBOX_OFFSET_Y = -10  # calibration for hammer mask alignment (negative = up)

# Debug hitbox visualization (toggle by holding the '1' key)
DEBUG_SHOW_BOXES = False
_DEBUG_HOLD_TICKS = 180  # ~3 seconds at 60 FPS
_debug_ticks = 0
_debug_toggle_consumed = False
DEBUG_STOPTIME = False  # Debug-only stop-time toggle (freeze updates)
_stop_toggle_consumed = False
# Debug clock start ticks (set on first update once playing starts)
GAME_START_TICKS = None

# Game state
game_state = "menu"  # menu, playing, paused
current_player = "mario"  # mario, bowser

# Note: The blue background in sprites can be removed by editing the image files
# to make the blue background transparent, or by using image editing software
# to replace the blue with transparent pixels

# Background surface cache (scaled to cover the entire screen)
_background_surface = None
_background_pos = (0, 0)

def _prepare_background():
    global _background_surface, _background_pos
    if _background_surface is not None:
        return
    # Load original image
    original = pygame.image.load("images/peachs_castle.png").convert()
    img_w, img_h = original.get_width(), original.get_height()
    # Scale proportionally to cover the screen (cover), cropping if necessary
    scale = max(WIDTH / img_w, HEIGHT / img_h)
    new_size = (max(1, int(img_w * scale)), max(1, int(img_h * scale)))
    _background_surface = pygame.transform.smoothscale(original, new_size)
    # Center the image with possible letterboxing
    _background_pos = ((WIDTH - new_size[0]) // 2, (HEIGHT - new_size[1]) // 2)

class Mario:
    def __init__(self):
        # Store original spawn coordinates as reference points
        self.spawn_x = 450
        self.spawn_y = FLOOR_Y
        self.x = 450
        self.y = FLOOR_Y  # temporary; will be corrected after actor is created
        self.width = 64
        self.height = 64
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = True
        self.facing_right = True  # Mario faces right (towards Bowser)
        self.health = 500
        self.ultimate_meter = 0
        
        # Animation state
        self.current_animation = "stand"
        self.animation_frame = 0
        self.animation_timer = 0
        self.animation_speed = 12  # frames per animation update (higher = slower)
        
        # Load stand animation frames
        self.stand_frames = [
            "mario_stand1",
            "mario_stand2"
        ]
        # Preprocessed/cropped stand surfaces (one sprite per frame)
        self.stand_surfaces = []

        # Attack (hammer) animation sliced from spritesheet
        # Will be populated after image is loaded
        self.attack_frames = []
        self.is_attacking = False
        self.attack_frame_index = 0
        self.attack_timer = 0
        self.attack_speed = 4  # lower is faster
        self.attack_has_hit = False
        # Vertical anchor during attack to prevent Y jitter across varying frame heights
        self.attack_anchor_feet_y = None
        self.attack_lock_vertical = False

        # Special (fireball) state and frames
        self.is_special = False
        self.special_phase = "idle"  # idle | charge | release
        self.special_timer = 0
        self.special_index = 0
        self.special_speed = 5
        self.special_has_fired = False
        self.special_charge_frames = []
        self.special_release_frames = []
        # Fireball charge overlay frames (sliced from spritesheet)
        self.special_charge_fx_frames = []
        self.special_charge_fx_index = 0
        self.special_charge_fx_timer = 0
        self.special_charge_fx_speed = 3
        self.special_charge_fx_actor = Actor("mario_fireball_charge")
        self.charge_fx_x = None
        self.charge_fx_y = None
        self.special_charge_timer = 0  # Timer for automatic charging
        self.special_charge_duration = 150  # 2.5 seconds at 60 FPS
        self.special_charge_tail_loop = False  # After first full cycle, loop last few frames
        self.special_charge_tail_start = 0  # Computed based on frames
        # Track which side Bowser is on to update facing only when crossing sides
        self._last_bowser_side = None  # -1 if Bowser is left of Mario, +1 if right

        # Block state
        self.is_blocking = False
        self.block_frames = []
        self.block_index = 0
        self.block_timer = 0
        self.block_speed = 6
        
        # Hitstun and hit animation (similar to Bowser)
        self.is_in_hitstun = False
        self.hitstun_timer = 0
        self.hitstun_duration = 20
        self.hitstun_linger = 10
        self.hit_frames = []
        self.hit_anim_timer = 0
        self.hit_anim_speed = 5
        self.hit_anim_index = 0
        self.is_playing_hit = False
        
        # Create actor for current frame
        self.actor = Actor(self.stand_frames[0])
        self.half_height = self.actor.height / 2
        self.half_width = self.actor.width / 2
        # Align feet to Mario's floor
        mario_floor = FLOOR_Y + MARIO_FLOOR_OFFSET
        self.y = mario_floor - self.half_height
        self.actor.pos = (self.x, self.y)

        # Prepare tightly-cropped stand frames and apply the first one
        self._prepare_stand_frames()
        if self.stand_surfaces:
            first = self.stand_surfaces[0]
            self.actor._surf = first
            # Update actor dimensions to match first frame
            self.half_height = first.get_height() / 2
            self.half_width = first.get_width() / 2
            self.actor.width = first.get_width()
            self.actor.height = first.get_height()
            self.y = mario_floor - self.half_height
            self.actor.pos = (self.x, self.y)

        # Prepare attack/special frames
        self._prepare_attack_frames()
        self._prepare_special_frames()
        self._prepare_charge_fx_frames()
        self._prepare_block_frames()
        self._prepare_hit_frames()
    
    def update(self):
        # If in hitstun, process only hitstun/hit animation and skip flameblast logic
        if self.is_in_hitstun:
            # Existing hitstun/hit animation logic
            # (copy from current update, or just let the rest of update handle hitstun)
            # Return early to skip flameblast state machine
            # (rest of update will handle hitstun animation, gravity, etc.)
            return
        # ... rest of update logic ...
        # Apply gravity
        if not self.on_ground:
            self.velocity_y += 0.6
        
        # Update position
        if self.is_in_hitstun:
            # Lock horizontal during hitstun
            self.velocity_x = 0
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Always face Bowser every frame
        try:
            self.facing_right = (bowser.x >= self.x)
        except Exception:
            pass

        # Ground collision
        mario_floor = FLOOR_Y + MARIO_FLOOR_OFFSET
        if self.y + self.half_height >= mario_floor:  # Ground level aligned with background floor + offset
            self.y = mario_floor - self.half_height
            self.velocity_y = 0
            self.on_ground = True
        
        # Update animation
        if self.is_blocking and self.block_frames:
            # Advance to last frame, then hold
            self.block_timer += 1
            if self.block_timer >= self.block_speed:
                self.block_timer = 0
                if self.block_index < len(self.block_frames) - 1:
                    self.block_index += 1
        elif self.is_attacking and self.attack_frames:
            self.attack_timer += 1
            if self.attack_timer >= self.attack_speed:
                self.attack_timer = 0
                self.attack_frame_index += 1
                if self.attack_frame_index >= len(self.attack_frames):
                    # End attack animation
                    self.is_attacking = False
                    self.attack_frame_index = 0
                    self.attack_has_hit = False
                    # Clear vertical lock once the attack ends
                    self.attack_lock_vertical = False
                    self.attack_anchor_feet_y = None
                else:
                    # Keep playing attack
                    pass
        elif self.is_special and (self.special_charge_frames or self.special_release_frames):
            self.special_timer += 1
            if self.special_timer >= self.special_speed:
                self.special_timer = 0
                self.special_index += 1
                if self.special_phase == "charge":
                    if not self.special_charge_tail_loop:
                        if self.special_index < len(self.special_charge_frames) - 1:
                            # Continue advancing through charge frames
                            pass
                        else:
                            # Completed one full cycle; switch to tail loop of last 3 frames
                            self.special_charge_tail_loop = True
                            self.special_charge_tail_start = max(0, len(self.special_charge_frames) - 3)
                            self.special_index = self.special_charge_tail_start
                    else:
                        # Loop within the last 3 frames
                        if self.special_index >= len(self.special_charge_frames) - 1:
                            self.special_index = self.special_charge_tail_start
                elif self.special_phase == "release":
                    if not self.special_has_fired and fireballs is not None:
                        # spawn one fireball at release start
                        self._spawn_fireball()
                        self.special_has_fired = True
                    if self.special_index >= len(self.special_release_frames):
                        # finish special
                        self._end_special()
            
            # Automatic charge timing - transition to release after 2.5 seconds
            if self.special_phase == "charge":
                self.special_charge_timer += 1
                if self.special_charge_timer >= self.special_charge_duration:
                    # Force transition to release phase
                    self.special_phase = "release"
                    self.special_index = 0
                    self.special_charge_timer = 0
            
            # Advance charge overlay frames to fit within charge duration
            # Note: Charge animation now loops the last 3 frames after completing one full cycle
            if self.special_phase == "charge" and self.special_charge_fx_frames:
                self.special_charge_fx_timer += 1
                if self.special_charge_fx_timer >= self.special_charge_fx_speed:
                    self.special_charge_fx_timer = 0
                    if self.special_charge_fx_index < len(self.special_charge_fx_frames) - 1:
                        self.special_charge_fx_index += 1
                # Update cached overlay position so draw and spawn share the exact point
                x_off, y_off = self._compute_charge_offsets()
                self.charge_fx_x = self.x + x_off
                self.charge_fx_y = self.y + y_off
        else:
            self.animation_timer += 1
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0
                self.animation_frame = (self.animation_frame + 1) % len(self.stand_frames)
                
        # Pick current image: block > hit > special > attack > stand
        if self.is_blocking and self.block_frames:
            current_surface = self.block_frames[self.block_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            if not self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
            # Match actor dimensions
            self.actor.width = current_surface.get_width()
            self.actor.height = current_surface.get_height()
        elif self.is_playing_hit and self.hit_frames:
            current_surface = self.hit_frames[self.hit_anim_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            if not self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
        elif self.is_special and (self.special_charge_frames or self.special_release_frames):
            frames = self.special_charge_frames if self.special_phase == "charge" else self.special_release_frames
            idx = max(0, min(self.special_index, len(frames) - 1))
            current_surface = frames[idx]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            if not self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
            # Update actor dimensions to match current frame (like Bowser does)
            self.actor.width = current_surface.get_width()
            self.actor.height = current_surface.get_height()
        elif self.is_playing_hit and self.hit_frames:
            self.hit_anim_timer += 1
            if self.hit_anim_timer >= self.hit_anim_speed:
                self.hit_anim_timer = 0
                if self.hit_anim_index < len(self.hit_frames) - 1:
                    self.hit_anim_index += 1
        elif self.is_attacking and self.attack_frames and not self.is_special and not self.is_blocking:
            current_surface = self.attack_frames[self.attack_frame_index]
            # On first attack frame, record feet anchor and enable vertical lock
            if not self.attack_lock_vertical:
                self.attack_anchor_feet_y = self.y + self.half_height
                self.attack_lock_vertical = True
            # Keep feet locked to the stored anchor while swapping frame height
            feet_y = self.attack_anchor_feet_y if self.attack_anchor_feet_y is not None else (self.y + self.half_height)
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            # Swap actor surface to tightly-cropped frame with orientation
            surf = current_surface
            if not self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
            # Update actor dimensions to match current frame (like Bowser does)
            self.actor.width = current_surface.get_width()
            self.actor.height = current_surface.get_height()
        else:
            if self.stand_surfaces:
                current_surface = self.stand_surfaces[self.animation_frame]
                feet_y = self.y + self.half_height
                self.half_height = current_surface.get_height() / 2
                self.half_width = current_surface.get_width() / 2
                self.y = feet_y - self.half_height
                surf = current_surface
                if not self.facing_right:
                    surf = pygame.transform.flip(surf, True, False)
                self.actor._surf = surf
                # Update actor dimensions to match current frame (like Bowser does)
                self.actor.width = current_surface.get_width()
                self.actor.height = current_surface.get_height()
            else:
                self.actor.image = self.stand_frames[self.animation_frame]
                self.half_height = self.actor.height / 2
                self.half_width = self.actor.width / 2
        
        # If attack vertical lock is active, keep feet anchored at attack start
        if self.is_attacking and self.attack_lock_vertical and self.attack_anchor_feet_y is not None:
            # Cancel any vertical drift and stick feet to the stored anchor
            self.velocity_y = 0
            self.y = self.attack_anchor_feet_y - self.half_height
        
        # Restore Y position after attack ends and ensure proper ground positioning
        if not self.is_attacking and hasattr(self, '_pre_attack_y'):
            self.y = self._pre_attack_y
            del self._pre_attack_y
            # Ensure Mario is properly positioned on the ground after restoration
            mario_floor = FLOOR_Y + MARIO_FLOOR_OFFSET
            if self.y + self.half_height >= mario_floor:
                self.y = mario_floor - self.half_height
                self.velocity_y = 0
                self.on_ground = True
        
        # Update actor position
        self.actor.pos = (self.x, self.y)
        
        # We already oriented surfaces directly; do not flip again
        self.actor.flip_x = False
        
        # Hitstun tick & linger
        if self.is_in_hitstun:
            self.hitstun_timer -= 1
            if self.hitstun_timer <= 0:
                self.is_in_hitstun = False
                self._start_hit_linger()
        else:
            if self.is_playing_hit:
                if getattr(self, '_hit_linger_timer', 0) > 0:
                    self._hit_linger_timer -= 1
                else:
                    self.is_playing_hit = False

    def start_hitstun_anim(self, duration=None):
        if self.hit_frames:
            self.is_playing_hit = True
            self.hit_anim_index = 0
            self.hit_anim_timer = 0
            # Use custom duration if provided, otherwise use default
            self._hit_linger_timer = duration if duration is not None else self.hitstun_linger

    def _start_hit_linger(self):
        self._hit_linger_timer = self.hitstun_linger
    
    def draw(self):
        # Draw Mario base sprite first
        self.actor.draw()
        # Then overlay the charge effect on top of Mario's hands
        if self.is_special and self.special_phase == "charge" and self.special_charge_fx_frames:
            fx_surf = self.special_charge_fx_frames[self.special_charge_fx_index]
            self.special_charge_fx_actor._surf = fx_surf
            # Use cached position to ensure draw and spawn match exactly
            if self.charge_fx_x is None or self.charge_fx_y is None:
                x_off, y_off = self._compute_charge_offsets()
                self.charge_fx_x = self.x + x_off
                self.charge_fx_y = self.y + y_off
            self.special_charge_fx_actor.pos = (self.charge_fx_x, self.charge_fx_y)
            self.special_charge_fx_actor.flip_x = not self.facing_right
            self.special_charge_fx_actor.draw()

    def _prepare_attack_frames(self):
        try:
            sheet = pygame.image.load("images/mario_hammer_attack.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)  # treat background as transparent
            sheet_w, sheet_h = sheet.get_width(), sheet.get_height()

            # Determine columns that contain non-background pixels
            non_bg_cols = []
            for x in range(sheet_w):
                col_has_sprite = False
                for y in range(sheet_h):
                    if sheet.get_at((x, y)) != bg:
                        col_has_sprite = True
                        break
                non_bg_cols.append(col_has_sprite)

            # Find contiguous ranges of sprite columns (these are frames)
            ranges = []
            in_run = False
            run_start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    run_start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((run_start, x - 1))
            if in_run:
                ranges.append((run_start, sheet_w - 1))

            frames = []
            for x0, x1 in ranges:
                # Compute tight vertical bounds for this frame
                min_y = sheet_h
                max_y = 0
                for x in range(x0, x1 + 1):
                    for y in range(sheet_h):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y:
                                min_y = y
                            if y > max_y:
                                max_y = y
                if min_y > max_y:
                    continue
                rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                frames.append(frame.convert_alpha())

            # Fallback to equal-width slicing if detection failed
            if not frames:
                frame_w = sheet_h
                if frame_w > 0:
                    num_frames = max(1, sheet_w // frame_w)
                    for i in range(num_frames):
                        rect = pygame.Rect(i * frame_w, 0, frame_w, sheet_h)
                        frame = pygame.Surface((frame_w, sheet_h), pygame.SRCALPHA)
                        frame.blit(sheet, (0, 0), rect)
                        frames.append(frame)

            self.attack_frames = frames
        except Exception:
            self.attack_frames = []

    def _prepare_hit_frames(self):
        try:
            sheet = pygame.image.load("images/mario_hit.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Detect non-background column runs across the sheet
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)
            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))
            frames = []
            for x0, x1 in ranges:
                # Tight vertical crop for this frame slice
                min_y, max_y = sh, 0
                for x in range(x0, x1 + 1):
                    for y in range(sh):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y: min_y = y
                            if y > max_y: max_y = y
                if min_y <= max_y:
                    rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    # Further crop to largest connected component to strip lingering pixels
                    try:
                        tmp = frame.convert()
                        tmp.set_colorkey(tmp.get_at((0, 0)))
                        mask = pygame.mask.from_surface(tmp)
                        w, h = frame.get_width(), frame.get_height()
                        visited = set()
                        largest_bounds = None
                        largest_size = 0
                        for ix in range(w):
                            for iy in range(h):
                                if mask.get_at((ix, iy)) and (ix, iy) not in visited:
                                    stack = [(ix, iy)]
                                    visited.add((ix, iy))
                                    minx = maxx = ix
                                    miny = maxy = iy
                                    size = 0
                                    while stack:
                                        cx, cy = stack.pop()
                                        size += 1
                                        if cx < minx: minx = cx
                                        if cx > maxx: maxx = cx
                                        if cy < miny: miny = cy
                                        if cy > maxy: maxy = cy
                                        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                                            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and mask.get_at((nx, ny)):
                                                visited.add((nx, ny))
                                                stack.append((nx, ny))
                                    if size > largest_size:
                                        largest_size = size
                                        largest_bounds = (minx, miny, maxx, maxy)
                        if largest_bounds:
                            xA, yA, xB, yB = largest_bounds
                            rect2 = pygame.Rect(xA, yA, xB - xA + 1, yB - yA + 1)
                            tight = pygame.Surface((rect2.width, rect2.height), pygame.SRCALPHA)
                            tight.blit(frame, (0, 0), rect2)
                            frames.append(tight.convert_alpha())
                        else:
                            frames.append(frame.convert_alpha())
                    except Exception:
                        frames.append(frame.convert_alpha())
            self.hit_frames = frames
        except Exception:
            self.hit_frames = []

    def _prepare_stand_frames(self):
        """Prepare stand animation frames and set the actor's _surf attribute"""
        frames = []
        for name in self.stand_frames:
            try:
                surf = pygame.image.load(f"images/{name}.png").convert()
                # Treat background color as transparent to isolate sprites in sheets with solid BG
                bg = surf.get_at((0, 0))
                surf.set_colorkey(bg)
                mask = pygame.mask.from_surface(surf)
                w, h = surf.get_width(), surf.get_height()
                visited = set()
                largest_bounds = None
                largest_size = 0
                # Connected-components over mask to find the single largest sprite cluster
                for x in range(w):
                    for y in range(h):
                        if mask.get_at((x, y)) and (x, y) not in visited:
                            stack = [(x, y)]
                            visited.add((x, y))
                            minx = maxx = x
                            miny = maxy = y
                            size = 0
                            while stack:
                                cx, cy = stack.pop()
                                size += 1
                                if cx < minx: minx = cx
                                if cx > maxx: maxx = cx
                                if cy < miny: miny = cy
                                if cy > maxy: maxy = cy
                                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and mask.get_at((nx, ny)):
                                        visited.add((nx, ny))
                                        stack.append((nx, ny))
                            if size > largest_size:
                                largest_size = size
                                largest_bounds = (minx, miny, maxx, maxy)
                if largest_bounds:
                    x0, y0, x1, y1 = largest_bounds
                    rect = pygame.Rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(surf, (0, 0), rect)
                    frames.append(frame.convert_alpha())
                else:
                    # Fallback: keep as-is with alpha
                    frames.append(surf.convert_alpha())
            except Exception:
                try:
                    frames.append(pygame.image.load(f"images/{name}.png").convert_alpha())
                except Exception:
                    # Skip missing or invalid frames silently
                    pass
        
        # Store the frames and set the actor's _surf attribute
        self.stand_surfaces = frames
        if frames:
            first = frames[0]
            self.actor._surf = first
            # Update actor dimensions to match first frame
            self.actor.width = first.get_width()
            self.actor.height = first.get_height()
            self.half_width = self.actor.width / 2
            self.half_height = self.actor.height / 2
    
    def _prepare_special_frames(self):
        try:
            sheet = pygame.image.load("images/mario_special.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Tight slice by non-bg column runs (same approach as hammer)
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)
            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))
            frames = []
            for x0, x1 in ranges:
                min_y, max_y = sh, 0
                for x in range(x0, x1 + 1):
                    for y in range(sh):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y: min_y = y
                            if y > max_y: max_y = y
                if min_y <= max_y:
                    rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    frames.append(frame.convert_alpha())
            # Fallback to square slicing if needed
            if not frames:
                fw = sh if sh > 0 else sw
                if fw > 0:
                    count = max(1, sw // fw)
                    for i in range(count):
                        rect = pygame.Rect(i * fw, 0, fw, sh)
                        frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                        frame.blit(sheet, (0, 0), rect)
                        frames.append(frame.convert_alpha())
            # Split into phases: first 6 charge, next 5 release
            self.special_charge_frames = frames[:6]
            self.special_release_frames = frames[6:11]
        except Exception:
            self.special_charge_frames = []
            self.special_release_frames = []

    def _prepare_charge_fx_frames(self):
        try:
            sheet = pygame.image.load("images/mario_fireball_charge.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Tight crop each frame by scanning non-background columns and rows
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)
            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))
            frames = []
            for x0, x1 in ranges:
                min_y, max_y = sh, 0
                for x in range(x0, x1 + 1):
                    for y in range(sh):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y: min_y = y
                            if y > max_y: max_y = y
                if min_y <= max_y:
                    rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    frames.append(frame.convert_alpha())
            # Fallback to square slicing if needed
            if not frames:
                fw = sh if sh > 0 else sw
                if fw > 0:
                    count = max(1, sw // fw)
                    for i in range(count):
                        rect = pygame.Rect(i * fw, 0, fw, sh)
                        frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                        frame.blit(sheet, (0, 0), rect)
                        frames.append(frame.convert_alpha())
            self.special_charge_fx_frames = frames
        except Exception:
            self.special_charge_fx_frames = []

    def _compute_charge_offsets(self):
        # Per-frame fine offsets to better center in gloves
        # Tune so the FX sits on Mario's right-hand white glove
        # Nudge more to glove center
        per_frame_dx = [10, 12, 13, 14, 14, 15, 15, 15]
        per_frame_dy = [-1, -1, 0, 0, 1, 1, 1, 1]
        idx = min(self.special_charge_fx_index, len(per_frame_dx) - 1)
        base_dx = CHARGE_OFFSET_X + per_frame_dx[idx]
        dx = base_dx if self.facing_right else -base_dx
        dy = CHARGE_OFFSET_Y + per_frame_dy[idx]
        # Global nudge: move right and up on screen (current left-facing kept as-is)
        dx += 80
        # When facing right, pull 75px left to be closer to glove center
        if self.facing_right:
            dx -= 155
        dy -= 10
        return dx, dy

    def _prepare_block_frames(self):
        try:
            sheet = pygame.image.load("images/mario_block.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Detect non-background columns to find per-frame horizontal slices
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)
            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))
            frames = []
            for x0, x1 in ranges:
                # Tight vertical crop for this frame
                min_y, max_y = sh, 0
                for x in range(x0, x1 + 1):
                    for y in range(sh):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y: min_y = y
                            if y > max_y: max_y = y
                if min_y <= max_y:
                    rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    # Further crop to the largest connected component to remove lingering parts
                    try:
                        tmp = frame.convert()
                        tmp.set_colorkey(tmp.get_at((0, 0)))
                        mask = pygame.mask.from_surface(tmp)
                        w, h = frame.get_width(), frame.get_height()
                        visited = set()
                        largest_bounds = None
                        largest_size = 0
                        for ix in range(w):
                            for iy in range(h):
                                if mask.get_at((ix, iy)) and (ix, iy) not in visited:
                                    stack = [(ix, iy)]
                                    visited.add((ix, iy))
                                    minx = maxx = ix
                                    miny = maxy = iy
                                    size = 0
                                    while stack:
                                        cx, cy = stack.pop()
                                        size += 1
                                        if cx < minx: minx = cx
                                        if cx > maxx: maxx = cx
                                        if cy < miny: miny = cy
                                        if cy > maxy: maxy = cy
                                        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                                            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and mask.get_at((nx, ny)):
                                                visited.add((nx, ny))
                                                stack.append((nx, ny))
                                    if size > largest_size:
                                        largest_size = size
                                        largest_bounds = (minx, miny, maxx, maxy)
                        if largest_bounds:
                            xA, yA, xB, yB = largest_bounds
                            rect2 = pygame.Rect(xA, yA, xB - xA + 1, yB - yA + 1)
                            tight = pygame.Surface((rect2.width, rect2.height), pygame.SRCALPHA)
                            tight.blit(frame, (0, 0), rect2)
                            frames.append(tight.convert_alpha())
                        else:
                            frames.append(frame.convert_alpha())
                    except Exception:
                        frames.append(frame.convert_alpha())
            # Fallback to square slices
            if not frames:
                fw = sh if sh > 0 else sw
                if fw > 0:
                    count = max(1, sw // fw)
                    for i in range(count):
                        rect = pygame.Rect(i * fw, 0, fw, sh)
                        frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                        frame.blit(sheet, (0, 0), rect)
                        frames.append(frame.convert_alpha())
            self.block_frames = frames
        except Exception:
            self.block_frames = []

    def _spawn_fireball(self):
        direction = 1 if self.facing_right else -1
        # TEMP: Spawn at Mario's exact center for both collision and visual
        spawn_x = self.x
        spawn_y = self.y
        fireballs.append(Fireball(spawn_x, spawn_y, direction, self.facing_right))
        # ---
        # Original logic (commented out for test):
        # if self.charge_fx_x is not None and self.charge_fx_y is not None:
        #     spawn_x = self.charge_fx_x
        #     spawn_y = self.charge_fx_y
        # else:
        #     x_off, y_off = self._compute_charge_offsets()
        #     spawn_x = self.x + x_off
        #     spawn_y = self.y + y_off
        # fireballs.append(Fireball(spawn_x, spawn_y, direction, self.facing_right))

    def _end_special(self):
        self.is_special = False
        self.special_phase = "idle"
        self.special_index = 0
        self.special_timer = 0
        self.special_has_fired = False
        self.special_charge_timer = 0  # Reset charge timer
        self.special_charge_tail_loop = False  # Reset charge tail loop
        self.special_charge_tail_start = 0  # Reset charge tail start

    def get_hurtbox(self):
        # Use spawn coordinates as reference point for consistent positioning
        width = self.actor.width
        height = self.actor.height
        # Calculate offset from spawn position
        offset_x = self.x - self.spawn_x
        offset_y = self.y - self.spawn_y
        # While blocking, nudge hurtbox in the direction Mario is facing for glove-forward stance
        if self.is_blocking:
            if self.facing_right:
                block_dx = 80  # 20 + 20 additional pixels right when blocking right
            else:
                block_dx = -40  # 20 pixels left when blocking left
        else:
            block_dx = 0
        # Apply offset to spawn-based positioning plus calibration
        x = int(self.spawn_x - width / 2 + offset_x + MARIO_BOX_OFFSET_X + block_dx)
        y = int(self.spawn_y - height / 2 + offset_y + MARIO_BOX_OFFSET_Y)
        return Rect(x, y, width, height)

    def get_mask(self):
        # Build a mask for visible pixels; remove near-background colors
        # Use the same approach as Bowser for consistency
        surf = self.actor._surf if hasattr(self.actor, '_surf') else None
        if surf is None:
            # Fallback to actor's current image if _surf is not available
            try:
                return pygame.mask.from_surface(self.actor._surf if hasattr(self.actor, '_surf') else self.actor.image)
            except Exception:
                # If all else fails, create a simple rectangular mask
                return pygame.mask.Mask((self.actor.width, self.actor.height), True)
        try:
            bg = surf.get_at((0, 0))
            # Full mask (may include background)
            mask_full = pygame.mask.from_surface(surf)
            # Background mask using color threshold tolerance
            tol = (30, 30, 30, 255)
            mask_bg = pygame.mask.from_threshold(surf, bg, tol)
            # Subtract background from full to get silhouette
            mask_full.erase(mask_bg)
            return mask_full
        except Exception:
            # If processing fails, return a simple mask from the surface
            try:
                return pygame.mask.from_surface(surf)
            except Exception:
                # Ultimate fallback: create a simple rectangular mask
                return pygame.mask.Mask((surf.get_width(), surf.get_height()), True)

    def get_tight_hurtbox(self):
        # Tight bounding rect from current visible surface
        surf = self.actor._surf if hasattr(self.actor, '_surf') else None
        if surf is None:
            return self.get_hurtbox()
        try:
            # Use spawn coordinates as reference point for consistent positioning
            m = self.get_mask()
            r = m.get_bounding_rect()
            # Calculate offset from spawn position
            offset_x = self.x - self.spawn_x
            offset_y = self.y - self.spawn_y
            if self.is_blocking:
                if self.facing_right:
                    block_dx = 80  # 20 + 20 additional pixels right when blocking right
                else:
                    block_dx = -40  # 20 pixels left when blocking left
            else:
                block_dx = 0
            # Apply offset to spawn-based positioning plus calibration
            top_left_x = int(self.spawn_x - surf.get_width() / 2 + offset_x + MARIO_BOX_OFFSET_X + block_dx) + r.x
            top_left_y = int(self.spawn_y - surf.get_height() / 2 + offset_y + MARIO_BOX_OFFSET_Y) + r.y
            return Rect(top_left_x, top_left_y, r.w, r.h)
        except Exception:
            return self.get_hurtbox()

    def get_attack_mask(self):
        # Pixel-perfect hammer hitbox: only yellow pixels, active in later swing
        if not (self.is_attacking and self.attack_frames):
            return None
        active_start = int(max(0, min(1, HAMMER_ACTIVE_START_RATIO)) * len(self.attack_frames))
        if self.attack_frame_index < active_start:
            return None
        try:
            raw = self.attack_frames[self.attack_frame_index]
            # Build oriented surface explicitly (do not rely on actor flip)
            surf = raw if self.facing_right else pygame.transform.flip(raw, True, False)
            # Build mask from yellow pixels (hammer head)
            mask = pygame.mask.from_threshold(surf, HAMMER_YELLOW_COLOR, HAMMER_YELLOW_TOLERANCE)
            if mask.count() == 0:
                # Fallback to full surface if detection fails
                mask = pygame.mask.from_surface(surf)
            # Position base depending on facing so mask stays on correct side
            if self.facing_right:
                base_x = int(self.x - surf.get_width() / 2 + HAMMER_HITBOX_OFFSET_X + 130)  # Move 120px right when facing right
            else:
                # Mirror anchoring horizontally around center
                base_x = int(self.x - surf.get_width() / 2 - HAMMER_HITBOX_OFFSET_X)
            # Shift hammer hitbox 151px to the left on screen
            base_x -= 151
            base_y = int(self.y - surf.get_height() / 2 + HAMMER_HITBOX_OFFSET_Y)
            return (mask, base_x, base_y)
        except Exception:
            return None

    def get_attack_hitbox(self):
        if not (self.is_attacking and self.attack_frames):
            return None
        # Create a hitbox extending in front of Mario based on current frame dimensions
        current_surface = self.attack_frames[self.attack_frame_index]
        frame_width = current_surface.get_width()
        frame_height = current_surface.get_height()
        width = int(frame_width * 0.8)
        height = int(frame_height * 0.7)
        forward = frame_width * 0.5
        # Compute center relative to current position; mirror horizontally by facing
        center_x = self.x + (forward if self.facing_right else -forward) + MARIO_BOX_OFFSET_X
        x = int(center_x - width / 2)
        y = int(self.y - height / 2 + MARIO_BOX_OFFSET_Y)
        return Rect(x, y, width, height)

class Bowser:
    def __init__(self):
        self.x = 850  # Start on the right side, opposite to Mario
        self.y = FLOOR_Y  # temporary; will be corrected after actor is created
        self.width = 64
        self.height = 64
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = True
        self.facing_right = False  # Bowser starts facing left (toward Mario)
        self.health = 500
        self.ultimate_meter = 0
        # Hitstun state
        self.is_in_hitstun = False
        self.hitstun_timer = 0
        self.hitstun_duration = 20
        self.hitstun_linger = 10  # extra frames to keep hit anim after hitstun
        # Hit animation (sliced from spritesheet)
        self.hit_frames = []
        self.hit_anim_timer = 0
        self.hit_anim_speed = 5
        self.hit_anim_index = 0
        self.is_playing_hit = False
        
        # Animation state
        self.current_animation = "stand"
        self.animation_frame = 0
        self.animation_timer = 0
        self.animation_speed = 12  # frames per animation update (higher = slower)
        
        # Create actor for current frame (stand images)
        self.stand_frames = ["bowser_stand1", "bowser_stand2"]
        self.stand_surfaces = []  # Will be populated by _prepare_stand_frames()
        self.actor = Actor(self.stand_frames[0])
        self.half_height = self.actor.height / 2
        self.half_width = self.actor.width / 2
        bowser_floor = FLOOR_Y + BOWSER_FLOOR_OFFSET
        self.y = bowser_floor - self.half_height
        self.actor.pos = (self.x, self.y)
        
        # Attack (punch) animation frames
        self.punch_frames = []
        self.punch_frames_right = []
        self.punch_frames_left = []
        self.is_attacking = False
        self.attack_frame_index = 0
        self.attack_timer = 0
        self.attack_speed = 10  # lower is faster (higher = slower)
        self.attack_has_hit = False
        
        # New flameblast attack system
        self.is_flameblasting = False
        self.flameblast_phase = "idle"  # idle | charge | release | stream
        self.flameblast_timer = 0
        self.flameblast_index = 0
        self.flameblast_speed = 4
        self.flameblast_charge_frames = []
        self.flameblast_release_frames = []
        self.flameblast_stream_frames = []
        self.flameblast_stream_duration = 60  # 1 second at 60 FPS
        self.flameblast_stream_timer = 0
        self.flameblast_has_hit = False
        # Lock Bowser's movement during stream phase
        self.flame_lock_movement = False
        # Add charging state variables
        self.is_charging = False
        self.charge_start_time = 0
        self.min_charge_time = 30  # Minimum frames to hold before release is allowed
        self.charge_tail_loop = False  # After first full cycle, loop last 3 frames
        self.charge_tail_start = 0  # Computed based on frames
        self.flameblast_charge_timer = 0  # Timer for automatic charging
        self.flameblast_charge_duration = 90  # 1.5 seconds at 60 FPS
        # Separate flame stream actor and animation timers (so Bowser stays visible)
        self.flame_stream_actor = Actor("flameblast")
        self.flame_fx_timer = 0
        self.flame_fx_speed = 3
        self.flame_fx_index = 0
        self.flame_left = 0
        self.flame_top = 0
        # Periodic damage while Mario is in the flame
        self._flame_collide_ticks = 0
        self.flame_damage_interval = 12  # 0.2 seconds at 60 FPS
        # Track which side Mario is on to update facing only when crossing sides
        self._last_mario_side = None  # -1 if Mario is left of Bowser, +1 if right
        
        # Block state
        self.is_blocking = False
        self.block_frames = []
        self.block_index = 0
        self.block_timer = 0
        self.block_speed = 6
        
        # Prepare animation frames
        self._prepare_stand_frames()
        self._prepare_hit_frames()
        self._prepare_punch_frames()
        self._prepare_flameblast_frames()
        self._prepare_block_frames()
    
    def _prepare_stand_frames(self):
        """Prepare stand animation frames and set the actor's _surf attribute"""
        frames = []
        for name in self.stand_frames:
            try:
                surf = pygame.image.load(f"images/{name}.png").convert()
                # Treat background color as transparent to isolate sprites in sheets with solid BG
                bg = surf.get_at((0, 0))
                surf.set_colorkey(bg)
                mask = pygame.mask.from_surface(surf)
                w, h = surf.get_width(), surf.get_height()
                visited = set()
                largest_bounds = None
                largest_size = 0
                # Connected-components over mask to find the single largest sprite cluster
                for x in range(w):
                    for y in range(h):
                        if mask.get_at((x, y)) and (x, y) not in visited:
                            stack = [(x, y)]
                            visited.add((x, y))
                            minx = maxx = x
                            miny = maxy = y
                            size = 0
                            while stack:
                                cx, cy = stack.pop()
                                size += 1
                                if cx < minx: minx = cx
                                if cx > maxx: maxx = cx
                                if cy < miny: miny = cy
                                if cy > maxy: maxy = cy
                                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and mask.get_at((nx, ny)):
                                        visited.add((nx, ny))
                                        stack.append((nx, ny))
                            if size > largest_size:
                                largest_size = size
                                largest_bounds = (minx, miny, maxx, maxy)
                if largest_bounds:
                    x0, y0, x1, y1 = largest_bounds
                    rect = pygame.Rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(surf, (0, 0), rect)
                    frames.append(frame.convert_alpha())
                else:
                    # Fallback: keep as-is with alpha
                    frames.append(surf.convert_alpha())
            except Exception:
                try:
                    frames.append(pygame.image.load(f"images/{name}.png").convert_alpha())
                except Exception:
                    # Skip missing or invalid frames silently
                    pass
        
        # Store the frames and set the actor's _surf attribute
        self.stand_surfaces = frames
        if frames:
            first = frames[0]
            self.actor._surf = first
            # Update actor dimensions to match first frame
            self.actor.width = first.get_width()
            self.actor.height = first.get_height()
            self.half_width = self.actor.width / 2
            self.half_height = self.actor.height / 2
    
    def update(self):
        # If in hitstun, skip only flameblast state machine logic, but run the rest of update
        skip_flameblast = self.is_in_hitstun
        # ... rest of update logic ...
        # Apply gravity
        if not self.on_ground:
            self.velocity_y += 0.6
        
        # Update position
        if not self.is_in_hitstun and not (self.is_flameblasting and self.flameblast_phase == "stream" and self.flame_lock_movement):
            self.x += self.velocity_x
        else:
            # Hard-lock horizontal movement during flame stream
            if self.is_flameblasting and self.flameblast_phase == "stream" and self.flame_lock_movement:
                self.velocity_x = 0
        self.y += self.velocity_y
        
        # Ground collision (Bowser uses slightly lower floor)
        bowser_floor = FLOOR_Y + BOWSER_FLOOR_OFFSET
        if self.y + self.half_height >= bowser_floor:
            self.y = bowser_floor - self.half_height
            self.velocity_y = 0
            self.on_ground = True
        
        # Always face Mario every frame
        try:
            self.facing_right = (mario.x >= self.x)
        except Exception:
            pass
        
        # Update animation state machines: block > hit > flameblast > attack > stand
        if self.is_blocking and self.block_frames:
            self.block_timer += 1
            if self.block_timer >= self.block_speed:
                self.block_timer = 0
                if self.block_index < len(self.block_frames) - 1:
                    self.block_index += 1
        elif self.is_playing_hit and self.hit_frames:
            self.hit_anim_timer += 1
            if self.hit_anim_timer >= self.hit_anim_speed:
                self.hit_anim_timer = 0
                if self.hit_anim_index < len(self.hit_frames) - 1:
                    self.hit_anim_index += 1
        elif self.is_charging and self.flameblast_charge_frames:
            # Update charge time and animation
            self.charge_start_time += 1
            self.flameblast_timer += 1
            if self.flameblast_timer >= self.flameblast_speed:
                self.flameblast_timer = 0
                if not self.charge_tail_loop:
                    if self.flameblast_index < len(self.flameblast_charge_frames) - 1:
                        self.flameblast_index += 1
                    else:
                        # Completed one full cycle; switch to tail loop of last 3 frames
                        self.charge_tail_loop = True
                        self.charge_tail_start = max(0, len(self.flameblast_charge_frames) - 3)
                        self.flameblast_index = self.charge_tail_start
                else:
                    # Loop within the last 3 frames
                    self.flameblast_index += 1
                    if self.flameblast_index >= len(self.flameblast_charge_frames):
                        self.flameblast_index = self.charge_tail_start
            
            # Automatic charge timing - transition to flameblast after 1.5 seconds
            self.flameblast_charge_timer += 1
            if self.flameblast_charge_timer >= self.flameblast_charge_duration:
                # Force transition to flameblast phase
                self.is_charging = False
                self.is_flameblasting = True
                self.flameblast_phase = "charge"
                self.flameblast_index = 0
                self.flameblast_timer = 0
                self.flameblast_charge_timer = 0
        elif not skip_flameblast and self.is_flameblasting and (self.flameblast_charge_frames or self.flameblast_release_frames or self.flameblast_stream_frames) and not self.is_blocking:
            self.flameblast_timer += 1
            if self.flameblast_timer >= self.flameblast_speed:
                self.flameblast_timer = 0
                if self.flameblast_phase == "charge":
                    if self.flameblast_index < len(self.flameblast_charge_frames) - 1:
                        self.flameblast_index += 1
                    else:
                        # Move to release phase
                        self.flameblast_phase = "release"
                        self.flameblast_index = 0
                elif self.flameblast_phase == "release":
                    if self.flameblast_index < len(self.flameblast_release_frames) - 1:
                        self.flameblast_index += 1
                    else:
                        # Move to stream phase
                        self.flameblast_phase = "stream"
                        self.flameblast_index = 1  # Start from 2nd sprite as requested
                        self.flameblast_stream_timer = 0
                elif self.flameblast_phase == "stream":
                    # Hold the 2nd release sprite for the body; animate flame FX
                    self.flameblast_stream_timer += 1
                    self.flame_fx_timer += 1
                    # Slow down the flame FX slightly
                    if self.flame_fx_timer >= max(1, self.flame_fx_speed + 1):
                        self.flame_fx_timer = 0
                        if self.flameblast_stream_frames:
                            self.flame_fx_index = (self.flame_fx_index + 1) % len(self.flameblast_stream_frames)
                    if self.flameblast_stream_timer >= self.flameblast_stream_duration:
                        # End flameblast attack immediately after stream phase
                        self._end_flameblast()
        elif self.is_attacking and self.punch_frames:
            self.attack_timer += 1
            if self.attack_timer >= self.attack_speed:
                self.attack_timer = 0
                self.attack_frame_index += 1
                if self.attack_frame_index >= len(self.punch_frames):
                    self.is_attacking = False
                    self.attack_frame_index = 0
                    self.attack_has_hit = False
        else:
            self.animation_timer += 1
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0
                self.animation_frame = (self.animation_frame + 1) % len(self.stand_frames)
        
        # Handle walking animation when moving
        if (self.velocity_x != 0 and not self.is_in_hitstun and 
            not self.is_flameblasting and
            not self.is_charging and not self.is_attacking and not self.is_blocking and not self.is_playing_hit):
            # Advance walk animation
            self.animation_timer += 1
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0
                self.animation_frame = (self.animation_frame + 1) % len(self.stand_frames)
        
        # Pick current image: block > hit > flameblast > attack > stand
        if self.is_blocking and self.block_frames:
            current_surface = self.block_frames[self.block_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            # Bowser base sprites assumed left-facing → flip when facing right
            if self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
        elif self.is_playing_hit and self.hit_frames:
            current_surface = self.hit_frames[self.hit_anim_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            if self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
        elif self.is_charging and self.flameblast_charge_frames:
            current_surface = self.flameblast_charge_frames[self.flameblast_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            if self.facing_right:
                surf = pygame.transform.flip(surf, True, False)
            self.actor._surf = surf
        elif self.is_flameblasting and (self.flameblast_charge_frames or self.flameblast_release_frames or self.flameblast_stream_frames) and self.flameblast_phase != "idle":
            if self.flameblast_phase == "charge" and self.flameblast_charge_frames:
                current_surface = self.flameblast_charge_frames[self.flameblast_index]
            elif self.flameblast_phase == "release" and self.flameblast_release_frames:
                current_surface = self.flameblast_release_frames[self.flameblast_index]
            elif self.flameblast_phase == "stream" and (self.flameblast_stream_frames or True):
                # Keep Bowser's body on the 2nd release frame during stream per spec
                if self.flameblast_release_frames:
                    current_surface = self.flameblast_release_frames[min(1, len(self.flameblast_release_frames)-1)]
                else:
                    current_surface = self.stand_frames[self.animation_frame]
                # Compute mouth/edge anchor using current body mask edge
                body_surf = current_surface
                feet_y = self.y + self.half_height
                self.half_height = body_surf.get_height() / 2
                self.half_width = body_surf.get_width() / 2
                self.y = feet_y - body_surf.get_height() / 2
                surf = body_surf
                if self.facing_right:
                    surf = pygame.transform.flip(surf, True, False)
                self.actor._surf = surf
                # Recompute actor pos for body
                self.actor.pos = (self.x, self.y)
                # Determine last detectable pixel edge and offset flame 10px inward
                try:
                    tmp = body_surf.convert()
                    tmp.set_colorkey(tmp.get_at((0, 0)))
                    m = pygame.mask.from_surface(tmp)
                    r = m.get_bounding_rect()
                    base_x = int(self.x - body_surf.get_width() / 2)
                    base_y = int(self.y - body_surf.get_height() / 2)
                    if self.facing_right:
                        last_x = r.right - 1  # rightmost local pixel
                        anchor_x = base_x + last_x - 10
                    else:
                        first_x = r.left  # leftmost local pixel
                        anchor_x = base_x + first_x + 10
                    anchor_y = base_y + r.y + int(r.h * 0.35)  # approx mouth height
                    self.flame_left = anchor_x
                    self.flame_top = anchor_y
                except Exception:
                    self.flame_left = int(self.x)
                    self.flame_top = int(self.y)
                # Skip normal body surf assignment below; already set
                current_surface = None
            else:
                # Fallback to stand frames if flameblast frames aren't loaded
                # Load stand frame and orient based on facing
                name = self.stand_frames[self.animation_frame]
                try:
                    current_surface = pygame.image.load(f"images/{name}.png").convert_alpha()
                except Exception:
                    current_surface = None
                if current_surface is not None:
                    feet_y = self.y + self.half_height
                    self.half_height = current_surface.get_height() / 2
                    self.half_width = current_surface.get_width() / 2
                    self.y = feet_y - self.half_height
                    surf = current_surface
                    if self.facing_right:
                        surf = pygame.transform.flip(surf, True, False)
                    self.actor._surf = surf
                return
            
            if current_surface is not None:
                feet_y = self.y + self.half_height
                self.half_height = current_surface.get_height() / 2
                self.half_width = current_surface.get_width() / 2
                self.y = feet_y - self.half_height
                self.actor._surf = current_surface
        elif self.is_flameblasting and self.flameblast_phase == "idle":
            # Safety check: if flameblast is marked as active but phase is idle, force reset
            self.is_flameblasting = False
            self.is_charging = False
            self.flameblast_phase = "idle"
            # Fall through to stand frames
        elif self.is_attacking and (self.punch_frames_left or self.punch_frames) and not self.is_blocking:
            # Use directional punch frames (left raw, right flipped)
            if self.punch_frames_left:
                directional_frames = self.punch_frames_right if self.facing_right else self.punch_frames_left
                current_surface = directional_frames[self.attack_frame_index]
            else:
                current_surface = self.punch_frames[self.attack_frame_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            surf = current_surface
            # punch frames are already oriented via directional selection; do not flip here
            self.actor._surf = surf
        else:
            # Keep Bowser's feet anchored when swapping back to stand frames
            feet_y = self.y + self.half_height
            # Use stand image surface so we can control flip explicitly
            name = self.stand_frames[self.animation_frame]
            try:
                base = pygame.image.load(f"images/{name}.png").convert_alpha()
            except Exception:
                base = None
            if base is not None:
                self.half_height = base.get_height() / 2
                self.half_width = base.get_width() / 2
                self.y = feet_y - self.half_height
                surf = base
                if self.facing_right:
                    surf = pygame.transform.flip(surf, True, False)
                self.actor._surf = surf
            else:
                # fallback to actor.image path
                self.actor.image = self.stand_frames[self.animation_frame]
                self.half_height = self.actor.height / 2
                self.half_width = self.actor.width / 2
            self.y = feet_y - self.half_height
        # Update actor position
        self.actor.pos = (self.x, self.y)
        
        # We oriented surfaces directly; do not flip again
        self.actor.flip_x = False

        # Tick hitstun
        if self.is_in_hitstun:
            self.hitstun_timer -= 1
            if self.hitstun_timer <= 0:
                self.is_in_hitstun = False
                # keep hit animation lingering briefly
                self._start_hit_linger()
        else:
            # Tick hit linger
            if self.is_playing_hit:
                if self._hit_linger_timer > 0:
                    self._hit_linger_timer -= 1
                else:
                    self.is_playing_hit = False

    def draw(self):
        self.actor.draw()
        # Draw flame stream FX separately so Bowser remains visible
        if self.is_flameblasting and self.flameblast_phase == "stream":
            # Pick current flame FX frame; if unavailable, fallback to base image surface
            fx_surf = None
            if self.flameblast_stream_frames:
                fx_surf = self.flameblast_stream_frames[self.flame_fx_index % len(self.flameblast_stream_frames)]
            else:
                try:
                    fx_surf = pygame.image.load("images/flameblast.png").convert_alpha()
                except Exception:
                    try:
                        fx_surf = pygame.image.load("images/flaneblast.png").convert_alpha()
                    except Exception:
                        fx_surf = None
            if fx_surf is not None:
                # Orient flame to face Bowser's direction
                if self.facing_right:
                    fx_surf = pygame.transform.flip(fx_surf, True, False)
                w, h = fx_surf.get_width(), fx_surf.get_height()
                if self.facing_right:
                    left = self.flame_left + 10  # small nudge right for mouth alignment
                else:
                    left = self.flame_left - w - 20  # shift 20px further left when facing left
                top = self.flame_top - h // 2 - 5
                # Blit directly to screen for reliability
                screen.surface.blit(fx_surf, (left, top))

    def get_hurtbox(self):
        width = self.actor.width
        height = self.actor.height
        x = int(self.x - width / 2)
        y = int(self.y - height / 2)
        return Rect(x, y, width, height)

    def get_tight_hurtbox(self):
        # Tight bounding rect from current visible surface
        surf = self.actor._surf
        try:
            m = self.get_mask()
            r = m.get_bounding_rect()
            top_left_x = int(self.x - surf.get_width() / 2) + r.x
            top_left_y = int(self.y - surf.get_height() / 2) + r.y
            return Rect(top_left_x, top_left_y, r.w, r.h)
        except Exception:
            return self.get_hurtbox()

    def get_mask(self):
        # Build a mask for visible pixels; remove near-background colors
        surf = self.actor._surf
        try:
            bg = surf.get_at((0, 0))
            # Full mask (may include background)
            mask_full = pygame.mask.from_surface(surf)
            # Background mask using color threshold tolerance
            tol = (30, 30, 30, 255)
            mask_bg = pygame.mask.from_threshold(surf, bg, tol)
            # Subtract background from full to get silhouette
            mask_full.erase(mask_bg)
            return mask_full
        except Exception:
            # If processing fails, return a simple mask from the surface
            try:
                return pygame.mask.from_surface(surf)
            except Exception:
                # Ultimate fallback: create a simple rectangular mask
                return pygame.mask.Mask((surf.get_width(), surf.get_height()), True)

    def start_hitstun_anim(self, duration=None):
        if self.hit_frames:
            self.is_playing_hit = True
            self.hit_anim_index = 0
            self.hit_anim_timer = 0
            # Use custom duration if provided, otherwise use default
            self._hit_linger_timer = duration if duration is not None else self.hitstun_linger

    def _start_hit_linger(self):
        # called when leaving hitstun; ensure animation lingers a bit
        self._hit_linger_timer = self.hitstun_linger

    def _prepare_hit_frames(self):
        try:
            sheet = pygame.image.load("images/bowser_hit.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Assume horizontal strip; use square frames based on height
            fw = sh if sh > 0 else sw
            frames = []
            if fw > 0:
                count = max(1, sw // fw)
                for i in range(count):
                    rect = pygame.Rect(i * fw, 0, fw, sh)
                    frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    frames.append(frame.convert_alpha())
            self.hit_frames = frames
        except Exception:
            self.hit_frames = []

    def _prepare_punch_frames(self):
        try:
            sheet = pygame.image.load("images/bowser_punch.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Detect non-background column runs across the sheet
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)
            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))

            frames = []
            for x0, x1 in ranges:
                # Tight vertical bounds for this horizontal slice
                min_y, max_y = sh, 0
                for x in range(x0, x1 + 1):
                    for y in range(sh):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y: min_y = y
                            if y > max_y: max_y = y
                if min_y > max_y:
                    continue
                rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                tight = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                tight.blit(sheet, (0, 0), rect)
                # Further crop to largest connected component to remove lingering parts
                try:
                    tmp = tight.convert()
                    tmp.set_colorkey(tmp.get_at((0, 0)))
                    mask = pygame.mask.from_surface(tmp)
                    w, h = tight.get_width(), tight.get_height()
                    visited = set()
                    largest_bounds = None
                    largest_size = 0
                    for ix in range(w):
                        for iy in range(h):
                            if mask.get_at((ix, iy)) and (ix, iy) not in visited:
                                stack = [(ix, iy)]
                                visited.add((ix, iy))
                                minx = maxx = ix
                                miny = maxy = iy
                                size = 0
                                while stack:
                                    cx, cy = stack.pop()
                                    size += 1
                                    if cx < minx: minx = cx
                                    if cx > maxx: maxx = cx
                                    if cy < miny: miny = cy
                                    if cy > maxy: maxy = cy
                                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and mask.get_at((nx, ny)):
                                            visited.add((nx, ny))
                                            stack.append((nx, ny))
                                if size > largest_size:
                                    largest_size = size
                                    largest_bounds = (minx, miny, maxx, maxy)
                    if largest_bounds:
                        xA, yA, xB, yB = largest_bounds
                        rect2 = pygame.Rect(xA, yA, xB - xA + 1, yB - yA + 1)
                        frame = pygame.Surface((rect2.width, rect2.height), pygame.SRCALPHA)
                        frame.blit(tight, (0, 0), rect2)
                        frames.append(frame.convert_alpha())
                    else:
                        frames.append(tight.convert_alpha())
                except Exception:
                    frames.append(tight.convert_alpha())

            # Fallback to equal-width slicing if nothing detected
            if not frames:
                fw = sh if sh > 0 else sw
                if fw > 0:
                    count = max(1, sw // fw)
                    for i in range(count):
                        rect = pygame.Rect(i * fw, 0, fw, sh)
                        frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                        frame.blit(sheet, (0, 0), rect)
                        frames.append(frame.convert_alpha())
            # Sheet is LEFT-facing by default: keep left as base and generate right by flipping
            self.punch_frames = frames
            try:
                self.punch_frames_left = [f.convert_alpha() for f in frames]
                self.punch_frames_right = [pygame.transform.flip(f, True, False) for f in frames]
            except Exception:
                self.punch_frames_right = []
                self.punch_frames_left = []
        except Exception:
            self.punch_frames = []

    def _prepare_flameblast_frames(self):
        try:
            # Load charge frames
            charge_sheet = pygame.image.load("images/bowser_flameblast_charge.png").convert()
            charge_bg = charge_sheet.get_at((0, 0))
            charge_sheet.set_colorkey(charge_bg)
            charge_sw, charge_sh = charge_sheet.get_width(), charge_sheet.get_height()
            
            # Load release frames
            release_sheet = pygame.image.load("images/bowser_flameblast_release.png").convert()
            release_bg = release_sheet.get_at((0, 0))
            release_sheet.set_colorkey(release_bg)
            release_sw, release_sh = release_sheet.get_width(), release_sheet.get_height()
            
            # Load stream frames (try flaneblast first, then flameblast)
            try:
                stream_sheet = pygame.image.load("images/flaneblast.png").convert_alpha()
            except Exception:
                stream_sheet = pygame.image.load("images/flameblast.png").convert_alpha()
            # Use alpha-based slicing (no reliance on BG color)
            self.flameblast_stream_frames = self._slice_sheet_small_alpha(stream_sheet)
            
            # Process charge frames with tight cropping to remove lingering parts
            self.flameblast_charge_frames = self._slice_sheet_tight(charge_sheet, charge_bg)
            
            # Process release frames
            self.flameblast_release_frames = self._slice_sheet(release_sheet, release_bg)
            
        except Exception as e:
            print(f"Error loading flameblast frames: {e}")
            self.flameblast_charge_frames = []
            self.flameblast_release_frames = []
            self.flameblast_stream_frames = []
    
    def _slice_sheet_tight(self, sheet, bg_color):
        """Helper method to slice a spritesheet into tightly cropped frames with no lingering parts"""
        sw, sh = sheet.get_width(), sheet.get_height()
        
        # Detect non-background column runs across the whole sheet
        non_bg_cols = []
        for x in range(sw):
            col_has = False
            for y in range(sh):
                if sheet.get_at((x, y)) != bg_color:
                    col_has = True
                    break
            non_bg_cols.append(col_has)
        
        ranges = []
        in_run = False
        start = 0
        for x, has in enumerate(non_bg_cols):
            if has and not in_run:
                in_run = True
                start = x
            elif not has and in_run:
                in_run = False
                ranges.append((start, x - 1))
        if in_run:
            ranges.append((start, sw - 1))
        
        frames = []
        for x0, x1 in ranges:
            # Find tight vertical bounds for this frame slice
            min_y, max_y = sh, 0
            for x in range(x0, x1 + 1):
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg_color:
                        if y < min_y: min_y = y
                        if y > max_y: max_y = y
            if min_y <= max_y:
                rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                
                # Further crop to largest connected component to remove lingering parts
                try:
                    tmp = frame.convert()
                    tmp.set_colorkey(tmp.get_at((0, 0)))
                    mask = pygame.mask.from_surface(tmp)
                    w, h = frame.get_width(), frame.get_height()
                    visited = set()
                    largest_bounds = None
                    largest_size = 0
                    for ix in range(w):
                        for iy in range(h):
                            if mask.get_at((ix, iy)) and (ix, iy) not in visited:
                                stack = [(ix, iy)]
                                visited.add((ix, iy))
                                minx = maxx = ix
                                miny = maxy = iy
                                size = 0
                                while stack:
                                    cx, cy = stack.pop()
                                    size += 1
                                    if cx < minx: minx = cx
                                    if cx > maxx: maxx = cx
                                    if cy < miny: miny = cy
                                    if cy > maxy: maxy = cy
                                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and mask.get_at((nx, ny)):
                                            visited.add((nx, ny))
                                            stack.append((nx, ny))
                                    if size > largest_size:
                                        largest_size = size
                                        largest_bounds = (minx, miny, maxx, maxy)
                    if largest_bounds:
                        xA, yA, xB, yB = largest_bounds
                        rect2 = pygame.Rect(xA, yA, xB - xA + 1, yB - yA + 1)
                        tight_frame = pygame.Surface((rect2.width, rect2.height), pygame.SRCALPHA)
                        tight_frame.blit(frame, (0, 0), rect2)
                        frames.append(tight_frame.convert_alpha())
                    else:
                        frames.append(frame.convert_alpha())
                except Exception:
                    frames.append(frame.convert_alpha())
        
        # Fallback: attempt square slicing if tight detection failed
        if not frames:
            fw = sh if sh > 0 else sw
            count = max(1, sw // fw) if fw > 0 else 1
            for i in range(count):
                rect = pygame.Rect(i * fw, 0, fw, sh)
                frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                frames.append(frame.convert_alpha())
        
        return frames
    
    def _slice_sheet_small_alpha(self, sheet):
        """Slice horizontally by detecting columns with any alpha > 0 and tightly crop each frame, then scale down."""
        sw, sh = sheet.get_width(), sheet.get_height()
        # Detect columns with any visible pixel (alpha > 0)
        non_empty_cols = []
        for x in range(sw):
            col_has = False
            for y in range(sh):
                if sheet.get_at((x, y)).a > 0:
                    col_has = True
                    break
            non_empty_cols.append(col_has)
        ranges = []
        in_run = False
        start = 0
        for x, has in enumerate(non_empty_cols):
            if has and not in_run:
                in_run = True
                start = x
            elif not has and in_run:
                in_run = False
                ranges.append((start, x - 1))
        if in_run:
            ranges.append((start, sw - 1))
        frames = []
        for x0, x1 in ranges:
            min_y, max_y = sh, 0
            for x in range(x0, x1 + 1):
                for y in range(sh):
                    if sheet.get_at((x, y)).a > 0:
                        if y < min_y: min_y = y
                        if y > max_y: max_y = y
            if min_y <= max_y:
                rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                # Scale down to about half Mario's height
                target_height = 32
                if frame.get_height() > 0:
                    scale = target_height / frame.get_height()
                    new_w = max(1, int(frame.get_width() * scale))
                    new_h = max(1, int(frame.get_height() * scale))
                    frames.append(pygame.transform.smoothscale(frame, (new_w, new_h)).convert_alpha())
                else:
                    frames.append(frame.convert_alpha())
        if not frames:
            frames = [sheet.convert_alpha()]
        return frames

    def get_attack_hitbox(self):
        if not (self.is_attacking and self.punch_frames):
            return None
        # Create a hitbox extending in front of Bowser
        width = int(self.half_width * 1.0)
        height = int(self.half_height * 0.8)
        forward = self.half_width * 0.7
        center_x = self.x + (forward if self.facing_right else -forward)
        x = int(center_x - width / 2)
        y = int(self.y - height / 2) - 20
        return Rect(x, y, width, height)
    
    def get_flameblast_hitbox(self):
        if not (self.is_flameblasting and self.flameblast_phase == "stream"):
            return None
        # Create a hitbox extending in front of Bowser for the flame stream
        width = int(self.half_width * 2.0)  # Wider than punch
        height = int(self.half_height * 0.6)  # Taller than punch
        
        # Offset 10 pixels to the left of Bowser's last detectable pixel
        if self.facing_right:
            # When facing right, offset 10 pixels to the left (negative)
            forward = self.half_width * 1.5 - 10
        else:
            # When facing left, offset 10 pixels to the right (positive)
            forward = -(self.half_width * 1.5 - 10)
            
        center_x = self.x + forward
        x = int(center_x - width / 2)
        # Nudge the hitbox 35px further right when facing right
        if self.facing_right:
            x += 35
        else:
            # When facing left, shift 20px further left
            x -= 20
        # Extend the left edge 40px further to the left without moving the right edge
        x -= 40
        width += 40
        y = int(self.y - height / 2)
        return Rect(x, y, width, height)

    def _slice_sheet(self, sheet, bg_color):
        """Slice a sheet into frames by detecting contiguous non-background column runs with tight vertical crop."""
        sw, sh = sheet.get_width(), sheet.get_height()
        non_bg_cols = []
        for x in range(sw):
            col_has = False
            for y in range(sh):
                if sheet.get_at((x, y)) != bg_color:
                    col_has = True
                    break
            non_bg_cols.append(col_has)
        ranges = []
        in_run = False
        start = 0
        for x, has in enumerate(non_bg_cols):
            if has and not in_run:
                in_run = True
                start = x
            elif not has and in_run:
                in_run = False
                ranges.append((start, x - 1))
        if in_run:
            ranges.append((start, sw - 1))
        frames = []
        for x0, x1 in ranges:
            min_y, max_y = sh, 0
            for x in range(x0, x1 + 1):
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg_color:
                        if y < min_y: min_y = y
                        if y > max_y: max_y = y
            if min_y <= max_y:
                rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                frames.append(frame.convert_alpha())
        # Fallback to square slicing if detection failed
        if not frames:
            fw = sh if sh > 0 else sw
            if fw > 0:
                count = max(1, sw // fw)
                for i in range(count):
                    rect = pygame.Rect(i * fw, 0, fw, sh)
                    frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    frames.append(frame.convert_alpha())
        return frames

    def _prepare_block_frames(self):
        try:
            sheet = pygame.image.load("images/bowser_block.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()
            # Detect contiguous non-background column runs (per-frame slices)
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)
            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))
            frames = []
            for x0, x1 in ranges:
                # Use full sheet height to avoid over-cropping; ensures full sprite visible
                rect = pygame.Rect(x0, 0, (x1 - x0 + 1), sh)
                frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                frames.append(frame.convert_alpha())
            # Fallback to square slices if detection failed
            if not frames:
                fw = sh if sh > 0 else sw
                if fw > 0:
                    count = max(1, sw // fw)
                    for i in range(count):
                        rect = pygame.Rect(i * fw, 0, fw, sh)
                        frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                        frame.blit(sheet, (0, 0), rect)
                        frames.append(frame.convert_alpha())
            # Apply requested reversed order
            self.block_frames = list(reversed(frames))
        except Exception:
            self.block_frames = []

    # --- Flameblast helpers ---
    def _end_flameblast(self):
        # Common teardown when stream ends or is canceled
        self.is_flameblasting = False
        self.is_charging = False
        self.charge_start_time = 0
        self.charge_tail_loop = False
        self.flameblast_phase = "idle"
        self.flameblast_index = 0
        self.flameblast_timer = 0
        self.flameblast_stream_timer = 0
        self.flame_fx_timer = 0
        self.flame_fx_index = 0
        self.flameblast_has_hit = False
        self.flame_lock_movement = False
        self.flameblast_charge_timer = 0  # Reset charge timer
        # Force Bowser into normal/idle state
        self.current_animation = "stand"
        self.animation_frame = 0
        self.animation_timer = 0
        self.is_attacking = False
        self.attack_frame_index = 0
        self.attack_timer = 0
        self.attack_has_hit = False
        self.is_blocking = False
        self.is_playing_hit = False

# Create Mario and Bowser instances
mario = Mario()
bowser = Bowser()

# Fireball projectile list
fireballs = []

class Fireball:
    def __init__(self, x, y, direction, mario_facing_right):
        self.x = x  # Collision position (for hitbox)
        self.y = y  # Collision position (for hitbox)
        self.direction = direction
        self.speed = 5
        self.alive = True
        
        # Frames for fireball animation (loop)
        self.frames = []
        self.index = 0
        self.timer = 0
        self.speed_ticks = 4
        self.actor = Actor("mario_fireball")
        self._prepare_frames()  # Frames are automatically scaled to 3x size
        
        # Calculate hitbox position (for collision detection)
        first = self.frames[0]
        self.left = int(self.x - first.get_width() / 2)
        self.top = int(self.y - first.get_height() / 2)
        
        # Visual position matches collision position exactly
        self.visual_x = self.x
        self.visual_y = self.y
        self.actor.pos = (self.visual_x, self.visual_y)
        
        self.actor.flip_x = False
        # Precompute outlines for each frame (for debug superimposition)
        self.outlines = [m.outline() for m in self.masks] if hasattr(self, 'masks') else []
        self.current_outline = None

    def _prepare_frames(self):
        try:
            sheet = pygame.image.load("images/mario_fireball.png").convert()
            bg = sheet.get_at((0, 0))
            sheet.set_colorkey(bg)
            sw, sh = sheet.get_width(), sheet.get_height()

            # Detect non-background column runs across the whole sheet
            non_bg_cols = []
            for x in range(sw):
                col_has = False
                for y in range(sh):
                    if sheet.get_at((x, y)) != bg:
                        col_has = True
                        break
                non_bg_cols.append(col_has)

            ranges = []
            in_run = False
            start = 0
            for x, has in enumerate(non_bg_cols):
                if has and not in_run:
                    in_run = True
                    start = x
                elif not has and in_run:
                    in_run = False
                    ranges.append((start, x - 1))
            if in_run:
                ranges.append((start, sw - 1))

            tight_frames = []
            for x0, x1 in ranges:
                # Find tight vertical bounds for this frame slice
                min_y, max_y = sh, 0
                for x in range(x0, x1 + 1):
                    for y in range(sh):
                        if sheet.get_at((x, y)) != bg:
                            if y < min_y:
                                min_y = y
                            if y > max_y:
                                max_y = y
                if min_y <= max_y:
                    rect = pygame.Rect(x0, min_y, (x1 - x0 + 1), (max_y - min_y + 1))
                    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    tight_frames.append(frame.convert_alpha())

            # Fallback: attempt square slicing if tight detection failed
            if not tight_frames:
                fw = sh if sh > 0 else sw
                count = max(1, sw // fw) if fw > 0 else 1
                for i in range(count):
                    rect = pygame.Rect(i * fw, 0, fw, sh)
                    frame = pygame.Surface((fw, sh), pygame.SRCALPHA)
                    frame.blit(sheet, (0, 0), rect)
                    tight_frames.append(frame.convert_alpha())

            # Scale all frames to 3x size
            scaled_frames = []
            for frame in tight_frames:
                # Scale frame to 3x size using smooth scaling
                scaled_width = frame.get_width() * 3
                scaled_height = frame.get_height() * 3
                scaled_frame = pygame.transform.smoothscale(frame, (scaled_width, scaled_height))
                scaled_frames.append(scaled_frame)
            
            self.frames = scaled_frames if scaled_frames else [self.actor._surf]
            # Build per-frame masks for pixel-perfect collision from scaled frames
            self.masks = [pygame.mask.from_surface(s) for s in self.frames]
        except Exception:
            self.frames = [self.actor._surf]
            self.masks = [pygame.mask.from_surface(self.actor._surf)]

    def get_hitbox(self):
        # Tight bounding rect from current visual surface anchored at top-left
        surf = self.actor._surf
        w, h = surf.get_width(), surf.get_height()
        return Rect(self.left, self.top, w, h)

    def update(self):
        if not self.alive:
            return
        # Move collision position horizontally
        self.x += self.speed * self.direction
        
        # Visual position matches collision position exactly
        self.visual_x = self.x
        self.visual_y = self.y
        
        # Animate
        self.timer += 1
        if self.timer >= self.speed_ticks:
            self.timer = 0
            self.index = (self.index + 1) % len(self.frames)
        # Select current frame and apply flip for direction
        current = self.frames[self.index]
        if self.direction < 0:
            current = pygame.transform.flip(current, True, False)
        # Update collision anchor for current frame size (using collision position)
        self.left = int(self.x - current.get_width() / 2)
        self.top = int(self.y - current.get_height() / 2)
        # Update visuals and mask to match exactly
        self.actor._surf = current
        # Update visual position to match collision position exactly
        self.actor.pos = (self.visual_x, self.visual_y)
        self.actor.flip_x = False  # we already flipped the surface
        self.current_mask = pygame.mask.from_surface(current)
        # Compute current outline (debug) aligned to current frame orientation
        try:
            base_outline = self.outlines[self.index] if self.outlines else self.current_mask.outline()
            if self.direction < 0:
                w = current.get_width()
                self.current_outline = [(w - 1 - px, py) for (px, py) in base_outline]
            else:
                self.current_outline = list(base_outline)
        except Exception:
            self.current_outline = None

        # Despawn off screen
        if self.left + current.get_width() < -50 or self.left > WIDTH + 50:
            self.alive = False

    def draw(self):
        if self.alive:
            # Draw the current frame centered at (self.x, self.y)
            current = self.frames[self.index]
            if self.direction < 0:
                current = pygame.transform.flip(current, True, False)
            frame_w, frame_h = current.get_width(), current.get_height()
            screen.blit(current, (int(self.x - frame_w // 2), int(self.y - frame_h // 2)))
            # Draw a debug dot at the intended center only in debug mode
            if DEBUG_SHOW_BOXES:
                screen.draw.filled_circle((int(self.x), int(self.y)), 5, (255, 0, 0))
            # Superimpose hitbox outline on the sprite for exact visual match (debug)
            if DEBUG_SHOW_BOXES and self.current_mask:
                pts = [(self.left + px, self.top + py) for (px, py) in self.current_mask.outline()]
                for i in range(1, len(pts)):
                    screen.draw.line(pts[i-1], pts[i], (255, 0, 0))

def update():
    global DEBUG_SHOW_BOXES, _debug_ticks, _debug_toggle_consumed, DEBUG_STOPTIME, _stop_toggle_consumed, GAME_START_TICKS
    # Initialize debug clock start
    if GAME_START_TICKS is None:
        GAME_START_TICKS = pygame.time.get_ticks()
    # Handle '1' key hold to toggle debug boxes (Pygame Zero style)
    if hasattr(keyboard, 'K_1') and keyboard.K_1:
        _debug_ticks += 1
        if _debug_ticks >= _DEBUG_HOLD_TICKS and not _debug_toggle_consumed:
            DEBUG_SHOW_BOXES = not DEBUG_SHOW_BOXES
            _debug_toggle_consumed = True
    else:
        _debug_ticks = 0
        _debug_toggle_consumed = False
    # Handle '2' key press to toggle stop-time, but only when debug boxes are shown
    if DEBUG_SHOW_BOXES and hasattr(keyboard, 'K_2') and keyboard.K_2 and not _stop_toggle_consumed:
        DEBUG_STOPTIME = not DEBUG_STOPTIME
        _stop_toggle_consumed = True
    if not (hasattr(keyboard, 'K_2') and keyboard.K_2):
        _stop_toggle_consumed = False
    # Apply stop-time only in debug mode: freeze updates when ON
    if DEBUG_SHOW_BOXES and DEBUG_STOPTIME:
        return
    
    if game_state == "playing":
        # Mario update
        mario.update()
        
        # Bowser update
        bowser.update()
        
        # Mario hammer attack collision against Bowser
        if mario.is_attacking and mario.attack_frame_index < len(mario.attack_frames) and not mario.attack_has_hit:
            atk_info = mario.get_attack_mask()
            if atk_info is not None:
                amask, ax, ay = atk_info
                bowser_hitbox = bowser.get_hurtbox()
                if bowser_hitbox:
                    # Convert hitbox to mask for pixel-perfect collision
                    bowser_surf = bowser.actor._surf if hasattr(bowser.actor, '_surf') else bowser.actor.image
                    bowser_mask = pygame.mask.from_surface(bowser_surf)
                    # Calculate offset between attack mask and bowser surface
                    offset_x = int(ax - (bowser.x - bowser_surf.get_width() / 2))
                    offset_y = int(ay - (bowser.y - bowser_surf.get_height() / 2))
                    if amask.overlap(bowser_mask, (offset_x, offset_y)):
                        print(f"[DEBUG] Mario hammer hit Bowser!")
                        mario.attack_has_hit = True
                        # Check if Bowser is charging flameblast for double damage
                        if bowser.is_charging and bowser.is_flameblasting and bowser.flameblast_phase == "charge":
                            print(f"[DEBUG] Double damage for interrupting flameblast charge!")
                            bowser.health -= 40  # Double damage
                            bowser.start_hitstun_anim(60)  # Double hitstun
                            bowser._end_flameblast()  # End flameblast early
                        else:
                            bowser.health -= 20
                            bowser.start_hitstun_anim(30)
                        bowser.is_blocking = False  # Force out of block state
        
        # Bowser punch attack collision against Mario
        if bowser.is_attacking and bowser.attack_frame_index < len(bowser.punch_frames) and not bowser.attack_has_hit:
            atk_info = bowser.get_attack_hitbox()
            if atk_info is not None:
                mario_hitbox = mario.get_hurtbox()
                if mario_hitbox and atk_info.colliderect(mario_hitbox):
                    print(f"[DEBUG] Bowser punch hit Mario!")
                    bowser.attack_has_hit = True
                    # Check if Mario is charging fireball for double damage
                    if mario.is_special and mario.special_phase == "charge":
                        print(f"[DEBUG] Double damage for interrupting fireball charge!")
                        mario.health -= 30  # Double damage
                        mario.start_hitstun_anim(60)  # Double hitstun
                        mario._end_special()  # End fireball early
                    else:
                        mario.health -= 15
                        mario.start_hitstun_anim(30)
        
        # Mario vs Bowser flameblast collision
        bowser_flameblast_hitbox = bowser.get_flameblast_hitbox()
        if bowser_flameblast_hitbox and bowser.is_flameblasting and bowser.flameblast_phase == "stream":
            mario_hitbox = mario.get_hurtbox()
            if mario_hitbox and bowser_flameblast_hitbox.colliderect(mario_hitbox):
                if not mario.is_blocking:
                    print(f"[DEBUG] Mario hit by flameblast!")
                    # Apply continuous damage at 7.5 HP per second (assuming 60 FPS)
                    mario.health -= (7.5 / 60.0)
                    mario.start_hitstun_anim(45)
        
        # Fireball vs Bowser collision
        for fb in fireballs[:]:  # Copy list to avoid modification during iteration
            bowser_hitbox = bowser.get_hurtbox()
            if bowser_hitbox and fb.get_hitbox().colliderect(bowser_hitbox):
                print(f"[DEBUG] Fireball hit Bowser!")
                fireballs.remove(fb)
                if not bowser.is_blocking:
                    bowser.health -= 15
                    bowser.start_hitstun_anim(30)
                else:
                    # Force Bowser out of block state and apply damage
                    bowser.is_blocking = False
                    bowser.health -= 15
                    bowser.start_hitstun_anim(30)
                break
        
        # Fireball vs flameblast collision
        for fb in fireballs[:]:
            bowser_flameblast_hitbox = bowser.get_flameblast_hitbox()
            if bowser_flameblast_hitbox and bowser.is_flameblasting and bowser.flameblast_phase == "stream":
                if fb.get_hitbox().colliderect(bowser_flameblast_hitbox):
                    print(f"[DEBUG] Fireball vs flameblast collision!")
                    fireballs.remove(fb)
                    bowser._end_flameblast()
                    break
        
        # Update fireballs
        for fb in fireballs[:]:
            fb.update()
            if not fb.alive:
                fireballs.remove(fb)

def draw():
    # Draw Peach's Castle background scaled to cover the whole screen
    _prepare_background()
    screen.surface.blit(_background_surface, _background_pos)
    
    if game_state == "playing":
        
        # Draw characters with equal layering using depth sort by feet position
        draw_list = [
            (mario.y + mario.half_height, mario),
            (bowser.y + bowser.half_height, bowser),
        ]
        for _, character in sorted(draw_list, key=lambda item: item[0]):
            character.draw()
            if DEBUG_SHOW_BOXES:
                # Draw Bowser's pixel-perfect mask outline in debug mode
                if isinstance(character, Bowser):
                    # Get the current surface, fallback to actor.image if _surf is not set
                    surf = getattr(character.actor, '_surf', None)
                    if surf is None:
                        surf = character.actor.image
                    mask = character.get_mask()
                    outline = mask.outline()
                    base_x = int(character.x - surf.get_width() / 2)
                    base_y = int(character.y - surf.get_height() / 2)
                    pts = [(base_x + px, base_y + py) for (px, py) in outline]
                    for i in range(1, len(pts)):
                        screen.draw.line(pts[i-1], pts[i], (0, 255, 0))
                else:
                    # Use pixel-perfect mask outline for Mario too, exactly like Bowser
                    # Get the current surface, fallback to actor.image if _surf is not set
                    surf = getattr(character.actor, '_surf', None)
                    if surf is None:
                        surf = character.actor.image
                    mask = character.get_mask()
                    outline = mask.outline()
                    # Apply Mario calibration offsets so debug outline matches adjusted hurtbox
                    base_x = int(character.x - surf.get_width() / 2 + (MARIO_BOX_OFFSET_X if isinstance(character, Mario) else 0))
                    base_y = int(character.y - surf.get_height() / 2 + (MARIO_BOX_OFFSET_Y if isinstance(character, Mario) else 0))
                    pts = [(base_x + px, base_y + py) for (px, py) in outline]
                    for i in range(1, len(pts)):
                        screen.draw.line(pts[i-1], pts[i], (0, 255, 0))
        if DEBUG_SHOW_BOXES:
            # Draw Mario hammer mask outline when active; no rectangle fallback
            atk_info = mario.get_attack_mask()
            if atk_info is not None:
                amask, ax, ay = atk_info
                pts = [(ax + px, ay + py) for (px, py) in amask.outline()]
                for i in range(1, len(pts)):
                    screen.draw.line(pts[i-1], pts[i], (255, 0, 0))
            batk = bowser.get_attack_hitbox() if hasattr(bowser, 'get_attack_hitbox') else None
            if batk:
                screen.draw.rect(batk, (255, 128, 0))
            fbatk = bowser.get_flameblast_hitbox() if hasattr(bowser, 'get_flameblast_hitbox') else None
            if fbatk and bowser.flameblast_phase == "stream":
                screen.draw.rect(fbatk, (255, 0, 255)) # Purple for flameblast

            # Debug clock (top-center): mm:ss.t since game start
            if GAME_START_TICKS is not None:
                elapsed_ms = max(0, pygame.time.get_ticks() - GAME_START_TICKS)
                minutes = elapsed_ms // 60000
                seconds = (elapsed_ms // 1000) % 60
                tenths = (elapsed_ms // 100) % 10
                clock_str = f"{minutes:02d}:{seconds:02d}.{tenths}"
                screen.draw.text(clock_str, center=(WIDTH // 2, 20), color="white", fontsize=28, owidth=1, ocolor="black")
        # Draw projectiles on same plane
        for fb in fireballs:
            fb.draw()
            # screen.draw.rect(fb.get_hitbox(), (255, 0, 0))
        
        # Draw Mario health bar with castle-themed colors (integer-only display)
        mario_hp_int = max(0, int(mario.health))
        screen.draw.filled_rect(Rect(50, 50, 160, 16), (139, 69, 19))  # Brown background
        screen.draw.filled_rect(Rect(50, 50, int(mario_hp_int * (160/500)), 16), (255, 215, 0))  # Gold health scaled to 500 max
        screen.draw.text("Mario HP: " + str(mario_hp_int), (50, 30), color="white", fontsize=24)
        
        # Draw Bowser health bar with castle-themed colors (integer-only display)
        bowser_hp_int = max(0, int(bowser.health))
        screen.draw.filled_rect(Rect(WIDTH - 210, 50, 160, 16), (139, 69, 19))  # Brown background
        screen.draw.filled_rect(Rect(WIDTH - 210, 50, int(bowser_hp_int * (160/500)), 16), (255, 69, 0))  # Orange-red health scaled to 500 max
        screen.draw.text("Bowser HP: " + str(bowser_hp_int), (WIDTH - 210, 30), color="white", fontsize=24)
    
    elif game_state == "menu":
        # Add semi-transparent overlay for better text readability
        screen.draw.filled_rect(Rect(0, 0, WIDTH, HEIGHT), (0, 0, 0, 100))
        screen.draw.text("Mario vs Bowser", (WIDTH//2 - 150, HEIGHT//2 - 50), 
                        color="white", fontsize=48)
        screen.draw.text("Press SPACE to start", (WIDTH//2 - 120, HEIGHT//2 + 50), 
                        color="white", fontsize=24)
    
    

def on_key_down(key):
    global game_state
    
    if key == keys.SPACE and game_state == "menu":
        game_state = "playing"
    
    if game_state == "playing":
        # Mario controls (WASD keys)
        if mario.is_in_hitstun:
            return
        if key == keys.A:
            mario.velocity_x = -3
            mario.facing_right = False
        elif key == keys.D:
            mario.velocity_x = 3
            mario.facing_right = True
        elif key == keys.W and mario.on_ground and not mario.is_playing_hit:
            mario.velocity_y = -12
            mario.on_ground = False
        elif key == keys.Z and not mario.is_blocking:
            # Trigger Mario hammer attack
            mario.is_attacking = True
            mario.attack_frame_index = 0
            mario.attack_timer = 0
            mario.attack_has_hit = False
        elif key == keys.X and not mario.is_blocking and not mario.is_special:
            # Trigger Mario special (charge then fireball) - automatic charging for 2.5 seconds
            mario.is_special = True
            mario.special_phase = "charge"
            mario.special_index = 0
            mario.special_timer = 0
            mario.special_has_fired = False
            mario.special_charge_fx_index = 0
            mario.special_charge_fx_timer = 0
            mario.special_charge_timer = 0  # Reset charge timer
            mario.special_charge_tail_loop = False  # Reset charge tail loop
            mario.special_charge_tail_start = 0  # Reset charge tail start
        elif key == keys.C:
            # Mario block (hold)
            mario.is_blocking = True
            mario.block_index = 0
            mario.block_timer = 0
        
        # Bowser controls (Arrow keys)
        if bowser.is_in_hitstun:
            pass
        elif key == keys.LEFT:
            bowser.velocity_x = -3
            bowser.facing_right = False
        elif key == keys.RIGHT:
            bowser.velocity_x = 3
            bowser.facing_right = True
        elif key == keys.UP and bowser.on_ground:
            bowser.velocity_y = -9  # Bowser jumps lower than Mario
            bowser.on_ground = False
        elif key == keys.PERIOD and not bowser.is_in_hitstun and not bowser.is_flameblasting and not bowser.is_blocking and not bowser.is_charging:  # . key for flameblast charge
            # Start charging phase - automatic charging for 1.5 seconds
            bowser.is_charging = True
            bowser.charge_start_time = 0
            bowser.flameblast_index = 0
            bowser.flameblast_timer = 0
            bowser.charge_tail_loop = False
            bowser.flameblast_charge_timer = 0  # Reset charge timer
        elif ((getattr(keys, 'SLASH', None) is not None and key == keys.SLASH) or
              (hasattr(pygame, 'K_SLASH') and key == pygame.K_SLASH)) and not bowser.is_in_hitstun and not bowser.is_blocking:  # '/' key for Bowser punch
            bowser.is_attacking = True
            bowser.attack_frame_index = 0
            bowser.attack_timer = 0
            bowser.attack_has_hit = False
        elif key == keys.COMMA and not bowser.is_in_hitstun and not bowser.is_flameblasting and not bowser.is_blocking and not bowser.is_charging:  # , key for Bowser block
            bowser.is_blocking = True
            bowser.block_index = 0
            bowser.block_timer = 0
        # Bowser flameblast stream cancel
        elif key == keys.PERIOD and bowser.is_flameblasting and bowser.flameblast_phase == "stream":
            # Cancel the stream early by pressing PERIOD again
            bowser._end_flameblast()

def on_key_up(key):
    if game_state == "playing":
        # Mario controls (WASD)
        if mario.is_in_hitstun:
            pass
        elif key == keys.A and mario.velocity_x < 0:
            mario.velocity_x = 0
        elif key == keys.D and mario.velocity_x > 0:
            mario.velocity_x = 0
        elif key == keys.C:
            # Release Mario block
            mario.is_blocking = False
            mario.block_index = 0
            mario.block_timer = 0
        
        # Bowser controls (Arrow keys)
        elif bowser.is_in_hitstun:
            pass
        elif key == keys.LEFT and bowser.velocity_x < 0:
            bowser.velocity_x = 0
        elif key == keys.RIGHT and bowser.velocity_x > 0:
            bowser.velocity_x = 0
        elif key == keys.COMMA:
            # Release Bowser block
            bowser.is_blocking = False
            bowser.block_index = 0
            bowser.block_timer = 0
        # Bowser flameblast stream cancel
        elif key == keys.PERIOD and bowser.is_flameblasting and bowser.flameblast_phase == "stream":
            # Cancel the stream early by pressing PERIOD again
            bowser._end_flameblast()

pgzrun.go()
