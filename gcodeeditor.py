import pygame
import sys
import math


WINDOW_SIZE = (1000, 600)
SCALE = 5.0             
GRID_SPACING_MM = 10    
SNAP_DIST = 15         
FEED_TRAVEL = 800.0
FEED_DRAW = 400.0


BG_COLOR = (30, 30, 35)
GRID_COLOR = (50, 50, 60)
LINE_COLOR = (0, 255, 100)
GHOST_COLOR = (100, 100, 100)
UI_TEXT_COLOR = (200, 200, 200)
SNAP_COLOR = (255, 50, 50)

pygame.init()
screen = pygame.display.set_mode(WINDOW_SIZE)
pygame.display.set_caption("2D Plotter CAD")
font = pygame.font.SysFont("consolas", 16)


lines = [] 
current_start = None

def draw_grid():
    screen.fill(BG_COLOR)
    pixel_spacing = int(GRID_SPACING_MM * SCALE)
    for x in range(0, WINDOW_SIZE[0], pixel_spacing):
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, WINDOW_SIZE[1]))
    for y in range(0, WINDOW_SIZE[1], pixel_spacing):
        pygame.draw.line(screen, GRID_COLOR, (0, y), (WINDOW_SIZE[0], y))

def screen_to_machine(px, py):
    real_x = px / SCALE
    real_y = (WINDOW_SIZE[1] - py) / SCALE
    return real_x, real_y

def get_snapped_mouse():
    mx, my = pygame.mouse.get_pos()
    
    # Check snapping to existing endpoints
    for p1, p2 in lines:
        if math.hypot(mx - p1[0], my - p1[1]) < SNAP_DIST:
            return p1, True
        if math.hypot(mx - p2[0], my - p2[1]) < SNAP_DIST:
            return p2, True
            
    # Snap to grid intersections
    grid_px = int(GRID_SPACING_MM * SCALE)
    snapped_x = round(mx / grid_px) * grid_px
    snapped_y = round(my / grid_px) * grid_px
    if math.hypot(mx - snapped_x, my - snapped_y) < SNAP_DIST:
        return (snapped_x, snapped_y), True
        
    return (mx, my), False

def apply_shift_constraint(start, target):
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    angle = math.atan2(dy, dx)
    length = math.hypot(dx, dy)
    
    # Lock to 0, 45, 90, 135, 180, 225, 270, 315 degrees
    snapped_angle = round(angle / (math.pi / 4)) * (math.pi / 4)
    
    nx = start[0] + math.cos(snapped_angle) * length
    ny = start[1] + math.sin(snapped_angle) * length
    return nx, ny

def export_gcode():
    filename = "cad_drawing.gcode"
    with open(filename, 'w') as f:
        f.write("G21 ; Set units to mm\n")
        f.write("G90 ; Absolute positioning\n")
        f.write("M5  ; Ensure pen is up\n")
        
        last_end = None
        for p1, p2 in lines:
            m_p1x, m_p1y = screen_to_machine(*p1)
            m_p2x, m_p2y = screen_to_machine(*p2)
            
            # Smart optimization: Only lift the pen if the new line doesn't connect to the old one
            if p1 != last_end:
                f.write("M5\n")
                f.write(f"G1 X{m_p1x:.3f} Y{m_p1y:.3f} F{FEED_TRAVEL}\n")
                f.write("M3\n")
                
            f.write(f"G1 X{m_p2x:.3f} Y{m_p2y:.3f} F{FEED_DRAW}\n")
            last_end = p2
            
        f.write("M5\n")
        f.write(f"G1 X0 Y0 F{FEED_TRAVEL} ; Return to home\n")
        f.write("M2  ; End of program\n")
    print(f"Successfully exported {filename}!")

running = True
while running:
    draw_grid()
    target_pos, is_snapped = get_snapped_mouse()
    
    # 1. Handle Shift Constraint
    if current_start:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            target_pos = apply_shift_constraint(current_start, target_pos)

    # 2. Draw existing lines
    for p1, p2 in lines:
        pygame.draw.line(screen, LINE_COLOR, p1, p2, 2)
        pygame.draw.circle(screen, LINE_COLOR, p1, 3)
        pygame.draw.circle(screen, LINE_COLOR, p2, 3)

    # 3. Draw active drafting line
    if current_start:
        pygame.draw.line(screen, GHOST_COLOR, current_start, target_pos, 2)
        pygame.draw.circle(screen, LINE_COLOR, current_start, 4)

    # 4. Draw Cursor & Snapping Indicator
    if is_snapped and not current_start:
        pygame.draw.circle(screen, SNAP_COLOR, (int(target_pos[0]), int(target_pos[1])), 6, 2)
    else:
        pygame.draw.circle(screen, UI_TEXT_COLOR, (int(target_pos[0]), int(target_pos[1])), 4)

    # 5. Render Metric Telemetry UI
    real_mx, real_my = screen_to_machine(*target_pos)
    ui_text = f"X: {real_mx:.1f} mm | Y: {real_my:.1f} mm"
    text_surface = font.render(ui_text, True, UI_TEXT_COLOR)
    
    # Position text near cursor
    screen.blit(text_surface, (target_pos[0] + 15, target_pos[1] - 25))

    pygame.display.flip()

    # 6. Event Handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: 
                if current_start is None:
                    # Click 1: Start line segment
                    current_start = target_pos
                else:
                    # Click 2: End line segment
                    lines.append((current_start, target_pos))
                    current_start = None
                    
            elif event.button == 3: 
                # Right click: Cancel active line
                current_start = None
                
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s:
                export_gcode()
            elif event.key == pygame.K_c:
                lines = []
                current_start = None
                print("Canvas cleared.")

pygame.quit()
sys.exit()