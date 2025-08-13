import pgzero
import pgzrun
from pgzero.actor import Actor
from pgzero.rect import Rect
import math
import pygame

# Game configuration
WIDTH = 800
HEIGHT = 600
TITLE = "Mario vs Bowser - 2D Fighting Game"
# Nudge the perceived ground a bit lower to sit on the grass edge
GROUND_NUDGE_PX = 12
FLOOR_Y = HEIGHT - 50 + GROUND_NUDGE_PX
# Additional per-character floor nudge for Bowser to align with bush base
BOWSER_FLOOR_OFFSET = 10
ATTACK_HITSTUN_BUFFER_TICKS = 8  # extra ticks after attack ends
CHARGE_OFFSET_X = 80  # base pixels to the right (left if facing left)
CHARGE_OFFSET_Y = 7  # base pixels upward from Mario's center (positive is down)

# Debug hitbox visualization (toggle by holding the '1' key)
DEBUG_SHOW_BOXES = False
_DEBUG_HOLD_TICKS = 180  # ~3 seconds at 60 FPS
_debug_ticks = 0
_debug_toggle_consumed = False

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
        self.x = 200
        self.y = FLOOR_Y  # temporary; will be corrected after actor is created
        self.width = 64
        self.height = 64
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = True
        self.facing_right = True  # Mario faces right (towards Bowser)
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

        # Attack (hammer) animation sliced from spritesheet
        # Will be populated after image is loaded
        self.attack_frames = []
        self.is_attacking = False
        self.attack_frame_index = 0
        self.attack_timer = 0
        self.attack_speed = 4  # lower is faster
        self.attack_has_hit = False

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
        
        # Create actor for current frame
        self.actor = Actor(self.stand_frames[0])
        self.half_height = self.actor.height / 2
        self.half_width = self.actor.width / 2
        # Align feet to floor: center Y = floor Y - half sprite height
        self.y = FLOOR_Y - self.half_height
        self.actor.pos = (self.x, self.y)

        # Prepare hammer attack frames by slicing the spritesheet horizontally
        self._prepare_attack_frames()
        # Prepare special frames from spritesheet and split charge/release
        self._prepare_special_frames()
        # Prepare charge overlay frames
        self._prepare_charge_fx_frames()
    
    def update(self):
        # Apply gravity
        if not self.on_ground:
            self.velocity_y += 0.6
        
        # Update position
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Ground collision
        if self.y + self.half_height >= FLOOR_Y:  # Ground level aligned with background floor
            self.y = FLOOR_Y - self.half_height
            self.velocity_y = 0
            self.on_ground = True
        
        # Update animation
        if self.is_attacking and self.attack_frames and not self.is_special:
            self.attack_timer += 1
            if self.attack_timer >= self.attack_speed:
                self.attack_timer = 0
                self.attack_frame_index += 1
                if self.attack_frame_index >= len(self.attack_frames):
                    # End attack animation and remember a short buffer period
                    self.is_attacking = False
                    self.attack_frame_index = 0
                    self.attack_has_hit = False
                    # Signal global system to extend hitstun slightly after animation
                    self._attack_ended_tick = pygame.time.get_ticks()
                else:
                    # Keep playing attack
                    pass
        elif self.is_special and (self.special_charge_frames or self.special_release_frames):
            self.special_timer += 1
            if self.special_timer >= self.special_speed:
                self.special_timer = 0
                self.special_index += 1
                if self.special_phase == "charge":
                    if self.special_index >= len(self.special_charge_frames):
                        # move to release
                        self.special_phase = "release"
                        self.special_index = 0
                elif self.special_phase == "release":
                    if not self.special_has_fired and fireballs is not None:
                        # spawn one fireball at release start
                        self._spawn_fireball()
                        self.special_has_fired = True
                    if self.special_index >= len(self.special_release_frames):
                        # finish special
                        self._end_special()
            # Advance charge overlay frames to fit within charge duration
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
                
        # Pick current image (special overrides attack, which overrides stand)
        if self.is_special and (self.special_charge_frames or self.special_release_frames):
            frames = self.special_charge_frames if self.special_phase == "charge" else self.special_release_frames
            idx = max(0, min(self.special_index, len(frames) - 1))
            current_surface = frames[idx]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            self.actor._surf = current_surface
        elif self.is_attacking and self.attack_frames:
            current_surface = self.attack_frames[self.attack_frame_index]
            # Keep feet locked to floor while swapping frame height
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.half_width = current_surface.get_width() / 2
            self.y = feet_y - self.half_height
            # Swap actor surface to tightly-cropped frame
            self.actor._surf = current_surface
        else:
            self.actor.image = self.stand_frames[self.animation_frame]
            self.half_height = self.actor.height / 2
            self.half_width = self.actor.width / 2
        
        # Update actor position
        self.actor.pos = (self.x, self.y)
        
        # Flip sprite based on facing direction
        self.actor.flip_x = not self.facing_right
    
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
        per_frame_dx = [0, 2, 3, 4, 5, 6, 6, 6]
        per_frame_dy = [0, 0, 1, 1, 2, 2, 2, 2]
        idx = min(self.special_charge_fx_index, len(per_frame_dx) - 1)
        base_dx = CHARGE_OFFSET_X + per_frame_dx[idx]
        dx = base_dx if self.facing_right else -base_dx
        dy = CHARGE_OFFSET_Y + per_frame_dy[idx]
        return dx, dy

    def _spawn_fireball(self):
        direction = 1 if self.facing_right else -1
        # Spawn exactly where the charge overlay ended (cached position)
        if self.charge_fx_x is not None and self.charge_fx_y is not None:
            spawn_x = self.charge_fx_x
            spawn_y = self.charge_fx_y
        else:
            # Fallback near hands
            x_off, y_off = self._compute_charge_offsets()
            spawn_x = self.x + x_off
            spawn_y = self.y + y_off
        fireballs.append(Fireball(spawn_x, spawn_y, direction))

    def _end_special(self):
        self.is_special = False
        self.special_phase = "idle"
        self.special_index = 0
        self.special_timer = 0
        self.special_has_fired = False

    def get_hurtbox(self):
        # Rectangle centered on the actor using current frame dimensions
        width = int(self.half_width * 2)
        height = int(self.half_height * 2)
        x = int(self.x - width / 2)
        y = int(self.y - height / 2)
        return Rect(x, y, width, height)

    def get_tight_hurtbox(self):
        # Tight bounding rect from current visible surface
        surf = self.actor._surf if hasattr(self.actor, '_surf') else None
        if surf is None:
            return self.get_hurtbox()
        try:
            bg = surf.get_at((0, 0))
            tmp = surf.convert()
            tmp.set_colorkey(bg)
            m = pygame.mask.from_surface(tmp)
            r = m.get_bounding_rect()
            top_left_x = int(self.x - surf.get_width() / 2) + r.x
            top_left_y = int(self.y - surf.get_height() / 2) + r.y
            return Rect(top_left_x, top_left_y, r.w, r.h)
        except Exception:
            return self.get_hurtbox()

    def get_attack_hitbox(self):
        if not (self.is_attacking and self.attack_frames):
            return None
        # Create a hitbox extending slightly in front of Mario
        width = int(self.half_width * 0.9)
        height = int(self.half_height * 0.8)
        forward = self.half_width * 0.6
        center_x = self.x + (forward if self.facing_right else -forward)
        x = int(center_x - width / 2)
        y = int(self.y - height / 2)
        return Rect(x, y, width, height)

class Bowser:
    def __init__(self):
        self.x = 600  # Start on the right side, opposite to Mario
        self.y = FLOOR_Y  # temporary; will be corrected after actor is created
        self.width = 64
        self.height = 64
        self.velocity_x = 0
        self.velocity_y = 0
        self.on_ground = True
        self.facing_right = True  # Bowser faces right (towards Mario)
        self.health = 100
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
        self.animation_speed = 8  # frames per animation update
        
        # Load stand animation frames (7 frames for Bowser)
        self.stand_frames = [
            "bowser_stand 1",
            "bowser_stand 2", 
            "bowser_stand 3",
            "bowser_stand 4",
            "bowser_stand 5",
            "bowser_stand 6",
            "bowser_stand 7"
        ]
        
        # Create actor for current frame
        self.actor = Actor(self.stand_frames[0])
        self.half_height = self.actor.height / 2
        # Align feet to floor (Bowser slightly lower to match bush base)
        bowser_floor = FLOOR_Y + BOWSER_FLOOR_OFFSET
        self.y = bowser_floor - self.half_height
        self.actor.pos = (self.x, self.y)
        # Prepare hit frames
        self._prepare_hit_frames()
    
    def update(self):
        # Apply gravity
        if not self.on_ground:
            self.velocity_y += 0.6
        
        # Update position
        if not self.is_in_hitstun:
            self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Ground collision (Bowser uses slightly lower floor)
        bowser_floor = FLOOR_Y + BOWSER_FLOOR_OFFSET
        if self.y + self.half_height >= bowser_floor:
            self.y = bowser_floor - self.half_height
            self.velocity_y = 0
            self.on_ground = True
        
        # Update animation (choose between stand loop and hit anim)
        if self.is_playing_hit and self.hit_frames:
            self.hit_anim_timer += 1
            if self.hit_anim_timer >= self.hit_anim_speed:
                self.hit_anim_timer = 0
                if self.hit_anim_index < len(self.hit_frames) - 1:
                    self.hit_anim_index += 1
        else:
            self.animation_timer += 1
            if self.animation_timer >= self.animation_speed:
                self.animation_timer = 0
                self.animation_frame = (self.animation_frame + 1) % len(self.stand_frames)
            
            # Update actor image and cached half height
            self.actor.image = self.stand_frames[self.animation_frame]
            self.half_height = self.actor.height / 2
        
        # Pick current image (hit anim overrides stand)
        if self.is_playing_hit and self.hit_frames:
            current_surface = self.hit_frames[self.hit_anim_index]
            feet_y = self.y + self.half_height
            self.half_height = current_surface.get_height() / 2
            self.y = feet_y - self.half_height
            self.actor._surf = current_surface
        else:
            self.actor.image = self.stand_frames[self.animation_frame]
            self.half_height = self.actor.height / 2
        # Update actor position
        self.actor.pos = (self.x, self.y)
        
        # Flip sprite based on facing direction
        self.actor.flip_x = not self.facing_right

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
            return pygame.mask.from_surface(surf)

    def start_hitstun_anim(self):
        if self.hit_frames:
            self.is_playing_hit = True
            self.hit_anim_index = 0
            self.hit_anim_timer = 0
            self._hit_linger_timer = self.hitstun_linger

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

# Create Mario and Bowser instances
mario = Mario()
bowser = Bowser()

# Fireball projectile list
fireballs = []

class Fireball:
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction
        self.speed = 5
        self.alive = True
        # Frames for fireball animation (loop)
        self.frames = []
        self.index = 0
        self.timer = 0
        self.speed_ticks = 4
        self.actor = Actor("mario_fireball")
        self._prepare_frames()
        # Anchor by top-left to keep sprite and hitbox perfectly aligned across varying frame sizes
        first = self.frames[0]
        self.left = int(self.x - first.get_width() / 2)
        self.top = int(self.y - first.get_height() / 2)
        self.actor.pos = (self.left + first.get_width() / 2, self.top + first.get_height() / 2)
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

            self.frames = tight_frames if tight_frames else [self.actor._surf]
            # Build per-frame masks for pixel-perfect collision
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
        # Move anchor horizontally
        self.left += self.speed * self.direction
        # Animate
        self.timer += 1
        if self.timer >= self.speed_ticks:
            self.timer = 0
            self.index = (self.index + 1) % len(self.frames)
        # Select current frame and apply flip for direction
        current = self.frames[self.index]
        if self.direction < 0:
            current = pygame.transform.flip(current, True, False)
        # Update visuals and mask to match exactly
        self.actor._surf = current
        # Recompute center from anchor to avoid drift when frame sizes vary
        self.actor.pos = (self.left + current.get_width() / 2, self.top + current.get_height() / 2)
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
            self.actor.draw()
            # Superimpose hitbox outline on the sprite for exact visual match (debug)
            if DEBUG_SHOW_BOXES and self.current_outline:
                base_x = int(self.x - self.actor._surf.get_width() / 2)
                base_y = int(self.y - self.actor._surf.get_height() / 2)
                pts = [(base_x + px, base_y + py) for (px, py) in self.current_outline]
                # Draw as a polyline
                for i in range(1, len(pts)):
                    screen.draw.line(pts[i-1], pts[i], (255, 0, 0))

def update():
    if game_state == "playing":
        global DEBUG_SHOW_BOXES, _debug_ticks, _debug_toggle_consumed
        # Handle '1' key hold to toggle debug boxes
        if keyboard.K_1:
            _debug_ticks += 1
            if _debug_ticks >= _DEBUG_HOLD_TICKS and not _debug_toggle_consumed:
                DEBUG_SHOW_BOXES = not DEBUG_SHOW_BOXES
                _debug_toggle_consumed = True
        else:
            _debug_ticks = 0
            _debug_toggle_consumed = False
        mario.update()
        bowser.update()
        # Update fireballs
        for fb in fireballs:
            fb.update()
        # Resolve attack collision once per attack instance
        hitbox = mario.get_attack_hitbox()
        if hitbox and not mario.attack_has_hit:
            if hitbox.colliderect(bowser.get_hurtbox()):
                # Apply damage and hitstun
                bowser.health = max(0, bowser.health - 5)
                bowser.is_in_hitstun = True
                # Extend hitstun by a small buffer beyond the remaining attack duration
                # Convert buffer from ms to ticks approximated via animation speed steps (~60 FPS)
                bowser.hitstun_timer = bowser.hitstun_duration + ATTACK_HITSTUN_BUFFER_TICKS
                # Start hit animation
                bowser.start_hitstun_anim()
                mario.attack_has_hit = True

        # Fireball collisions vs Bowser (pixel-perfect using masks)
        for fb in fireballs:
            if not fb.alive:
                continue
            # Pixel-perfect overlap first (tightest test)
            fb_mask = fb.current_mask if hasattr(fb, 'current_mask') else fb.masks[fb.index]
            bowser_mask = bowser.get_mask()
            # Use current frame surfaces; align by anchored top-left for fireball
            bow_w, bow_h = bowser.actor._surf.get_width(), bowser.actor._surf.get_height()
            offset_x = int((bowser.x - bow_w / 2) - fb.left)
            offset_y = int((bowser.y - bow_h / 2) - fb.top)
            # Use outline-only mask if available, else fallback to surface mask
            fb_outline_mask = getattr(fb, 'collision_mask', fb_mask)
            if fb_outline_mask.overlap(bowser_mask, (offset_x, offset_y)):
                fb.alive = False
                bowser.health = max(0, bowser.health - 5)
                bowser.is_in_hitstun = True
                bowser.hitstun_timer = bowser.hitstun_duration + ATTACK_HITSTUN_BUFFER_TICKS
                bowser.start_hitstun_anim()

        # Remove dead fireballs
        fireballs[:] = [fb for fb in fireballs if fb.alive]

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
                hb = character.get_hurtbox()
                screen.draw.rect(hb, (0, 255, 0))
        if DEBUG_SHOW_BOXES:
            atk = mario.get_attack_hitbox()
            if atk:
                screen.draw.rect(atk, (255, 0, 0))
        # Draw projectiles on same plane
        for fb in fireballs:
            fb.draw()
            if DEBUG_SHOW_BOXES and fb.alive:
                screen.draw.rect(fb.get_hitbox(), (255, 0, 0))
        
        # Draw Mario health bar with castle-themed colors
        screen.draw.filled_rect(Rect(50, 50, 200, 20), (139, 69, 19))  # Brown background
        screen.draw.filled_rect(Rect(50, 50, mario.health * 2, 20), (255, 215, 0))  # Gold health
        screen.draw.text("Mario HP: " + str(mario.health), (50, 30), color="white", fontsize=24)
        
        # Draw Bowser health bar with castle-themed colors
        screen.draw.filled_rect(Rect(WIDTH - 250, 50, 200, 20), (139, 69, 19))  # Brown background
        screen.draw.filled_rect(Rect(WIDTH - 250, 50, bowser.health * 2, 20), (255, 69, 0))  # Orange-red health
        screen.draw.text("Bowser HP: " + str(bowser.health), (WIDTH - 250, 30), color="white", fontsize=24)
    
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
        # Mario controls (Arrow keys)
        if key == keys.LEFT:
            mario.velocity_x = -3
            mario.facing_right = False
        elif key == keys.RIGHT:
            mario.velocity_x = 3
            mario.facing_right = True
        elif key == keys.UP and mario.on_ground:
            mario.velocity_y = -12
            mario.on_ground = False
        elif key == keys.Z:
            # Trigger Mario hammer attack
            mario.is_attacking = True
            mario.attack_frame_index = 0
            mario.attack_timer = 0
        elif key == keys.X:
            # Trigger Mario special (charge then fireball)
            mario.is_special = True
            mario.special_phase = "charge"
            mario.special_index = 0
            mario.special_timer = 0
            mario.special_has_fired = False
            mario.special_charge_fx_index = 0
            mario.special_charge_fx_timer = 0
        
        # Bowser controls (WASD) – disabled during hitstun
        elif key == keys.A and not bowser.is_in_hitstun:  # A key for left
            bowser.velocity_x = -2  # Bowser is slower than Mario
            bowser.facing_right = False
        elif key == keys.D and not bowser.is_in_hitstun:  # D key for right
            bowser.velocity_x = 2   # Bowser is slower than Mario
            bowser.facing_right = True
        elif key == keys.W and bowser.on_ground and not bowser.is_in_hitstun:  # W key for jump
            bowser.velocity_y = -9  # Bowser jumps lower than Mario
            bowser.on_ground = False

def on_key_up(key):
    if game_state == "playing":
        # Mario controls
        if key == keys.LEFT and mario.velocity_x < 0:
            mario.velocity_x = 0
        elif key == keys.RIGHT and mario.velocity_x > 0:
            mario.velocity_x = 0
        
        # Bowser controls
        elif key == keys.A and bowser.velocity_x < 0:
            bowser.velocity_x = 0
        elif key == keys.D and bowser.velocity_x > 0:
            bowser.velocity_x = 0

pgzrun.go()
