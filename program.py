import pygame
import serial
import time
import sys
import math

# ==========================================
# CONFIGURATION
# ==========================================
SERIAL_PORT = 'COM7'      # Change this to your Arduino's COM port
BAUD_RATE = 115200
GCODE_FILE = 'output.gcode' # Change to your exported Inkscape file

# Pygame Window Settings
WINDOW_SIZE = (1400, 800)
SCALE = 5.0  # Pixels per millimeter
OFFSET_X, OFFSET_Y = 50, 50 # Margin

# Colors
BG_COLOR = (20, 20, 25)
TEXT_COLOR = (200, 200, 200)
PATH_COLOR = (0, 255, 100)
PEN_UP_COLOR = (255, 50, 50)
PEN_DOWN_COLOR = (50, 200, 255)

# ==========================================
# INITIALIZATION
# ==========================================
pygame.init()
screen = pygame.display.set_mode(WINDOW_SIZE)
pygame.display.set_caption("2D Plotter Visualizer")
font = pygame.font.SysFont("consolas", 18)

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)
    time.sleep(2) # Wait for Arduino to reset
except Exception as e:
    print(f"Error opening serial port: {e}")
    sys.exit()


try:
    with open(GCODE_FILE, 'r') as f:
        raw_lines = f.readlines()
        gcode_lines = []
        for line in raw_lines:
            clean_line = line.strip().upper()
            # Now it checks the uppercase version, catching your 'g1' and 'm3'
            if clean_line.startswith(('G0', 'G1', 'M3', 'M5')):
                gcode_lines.append(clean_line)
                
except Exception as e:
    print(f"Error reading file: {e}")
    sys.exit()

# ==========================================
# STATE VARIABLES
# ==========================================
current_gcode_idx = 0
total_lines = len(gcode_lines)
waiting_for_ok = False

arduino_x, arduino_y = 0.0, 0.0
arduino_state = "Idle"
pen_is_down = False

# Store drawing paths: list of line segments
completed_paths = []
current_path = []

last_status_req = time.time()
serial_buffer = ""

def world_to_screen(x, y):
    """ Converts millimeters to screen pixels (Inverts Y so positive is up) """
    screen_x = OFFSET_X + (x * SCALE)
    screen_y = OFFSET_Y + (y * SCALE)
    return (int(screen_x), int(screen_y))

# ==========================================
# MAIN LOOP
# ==========================================
clock = pygame.time.Clock()
running = True

while running:
    current_time = time.time()
    
    # 1. Handle Pygame Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 2. Read Serial Data
    while ser.in_waiting > 0:
        char = ser.read().decode('utf-8', errors='ignore')
        if char == '\n':
            line = serial_buffer.strip()
            serial_buffer = ""
            
            # Check for acknowledgment
            if line == "ok":
                waiting_for_ok = False
            
            # Parse real-time coordinates: <Run|MPos:12.345,67.890,0.000|FS:0,0>
            elif line.startswith("<"):
                try:
                    arduino_state = line.split('|')[0][1:]
                    mpos_str = line.split('MPos:')[1].split('|')[0]
                    coords = mpos_str.split(',')
                    new_x = float(coords[0])
                    new_y = float(coords[1])
                    
                    # Update paths if pen is down and moved significantly
                    if pen_is_down and (abs(new_x - arduino_x) > 0.1 or abs(new_y - arduino_y) > 0.1):
                        current_path.append(world_to_screen(new_x, new_y))
                        
                    arduino_x, arduino_y = new_x, new_y
                except IndexError:
                    pass
        else:
            serial_buffer += char

    # 3. Send G-code (Lock-step: wait for 'ok' before sending next)
    if not waiting_for_ok and current_gcode_idx < total_lines:
        cmd = gcode_lines[current_gcode_idx]
        ser.write((cmd + '\n').encode('utf-8'))
        
        # Track pen state virtually
        if cmd.startswith("M3"):
            pen_is_down = True
            current_path = [world_to_screen(arduino_x, arduino_y)]
        elif cmd.startswith("M5"):
            pen_is_down = False
            if len(current_path) > 1:
                completed_paths.append(current_path)
            current_path = []
            
        waiting_for_ok = True
        current_gcode_idx += 1

    # 4. Request Status Update (20Hz)
    if current_time - last_status_req > 0.05:
        ser.write('?\n'.encode('utf-8'))
        last_status_req = current_time

    # 5. Render Pygame Visuals
    screen.fill(BG_COLOR)

    # Draw completed paths
    for path in completed_paths:
        if len(path) > 1:
            pygame.draw.lines(screen, PATH_COLOR, False, path, 2)
            
    # Draw active path
    if len(current_path) > 1:
        pygame.draw.lines(screen, PATH_COLOR, False, current_path, 2)

    # Draw Pen Head
    pen_pos = world_to_screen(arduino_x, arduino_y)
    p_color = PEN_DOWN_COLOR if pen_is_down else PEN_UP_COLOR
    pygame.draw.circle(screen, p_color, pen_pos, 6)
    if not pen_is_down:
        pygame.draw.circle(screen, BG_COLOR, pen_pos, 4) # Hollow if up

    # Render Telemetry UI
    progress = (current_gcode_idx / total_lines) * 100 if total_lines > 0 else 0
    ui_texts = [
        f"STATUS:   {arduino_state}",
        f"PROGRESS: {current_gcode_idx} / {total_lines} ({progress:.1f}%)",
        f"X POS:    {arduino_x:.3f} mm",
        f"Y POS:    {arduino_y:.3f} mm",
        f"PEN:      {'DOWN (Drawing)' if pen_is_down else 'UP (Hovering)'}"
    ]
    
    for i, text in enumerate(ui_texts):
        text_surface = font.render(text, True, TEXT_COLOR)
        screen.blit(text_surface, (10, 10 + (i * 25)))

    pygame.display.flip()
    clock.tick(60)

ser.close()
pygame.quit()