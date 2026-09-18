"""Board-level constants: outline, keepouts, block regions."""

BOARD_W = 110.0
BOARD_H = 48.0

# Outline of the card, clockwise, y downward. Shaped after a Founders-Edition
# style add-in card: chamfered bracket corner, stepped top edge on the far end,
# and a protruding PCIe card edge along the bottom.
OUTLINE = [
    (3.0, 0.0),
    (66.0, 0.0),
    (72.0, 6.0),
    (106.0, 6.0),
    (110.0, 10.0),
    (110.0, 41.0),
    (107.0, 44.0),
    (64.0, 44.0),
    (64.0, 48.0),
    (10.0, 48.0),
    (10.0, 44.0),
    (0.0, 44.0),
    (0.0, 3.0),
]

MOUNT_HOLES = [(6.2, 4.2), (6.2, 40.2), (103.6, 9.4), (103.6, 40.6)]
MOUNT_DRILL = 2.2
MOUNT_RING = 1.9  # gold annulus outer radius

# PCIe-style gold edge fingers.
# Copper must keep 0.5 mm from the board edge, and the card-edge protrusion
# ends at y = 48, so the fingers stop at 47.4 and start clear of the notch.
FINGER_Y0 = 43.9
FINGER_Y1 = 47.4
FINGER_GROUPS = [(12.6, 21.4), (25.6, 61.4)]
FINGER_PITCH = 1.0
FINGER_W = 0.7

# GPU package
GPU_CX, GPU_CY = 38.0, 24.0
GPU_SUB = 20.0          # substrate edge length
GPU_DIE = 8.4           # flip-chip die window

# GDDR6X module body
MEM_W, MEM_H = 6.6, 5.6

FRONT_MEM = [
    (24.0, 9.0), (32.0, 9.0), (40.0, 9.0), (48.0, 9.0),
    (24.0, 39.0), (32.0, 39.0), (40.0, 39.0), (48.0, 39.0),
    (20.2, 19.0), (20.2, 29.0),
    (55.8, 19.0), (55.8, 29.0),
]

BACK_MEM = [
    # Top row sits ABOVE the skyline band (band starts at y = 11.6); the
    # left column sits to its LEFT (band starts at x = 15). The right flank
    # is not available: the band runs to x = 81 and the QR keepout begins at
    # x = 82.
    (18.0, 6.6), (26.0, 6.6), (34.0, 6.6), (42.0, 6.6),
    (50.0, 6.6), (58.0, 6.6), (66.0, 6.6),
    (9.0, 14.5), (9.0, 21.5), (9.0, 28.5),
]

# Quiet branding area (front) / QR area (back).
# Starts below the 12VHPWR connector (which ends at y = 12.8).
QUIET_X0, QUIET_X1 = 82.5, 108.5
QUIET_Y0, QUIET_Y1 = 14.0, 43.0

# Hard keepout for the QR code on the back side. Nothing but the QR artwork
# may be placed inside this rectangle.
QR_KEEPOUT = (83.0, 11.5, 109.0, 37.5)   # x0, y0, x1, y1
QR_CENTER = (96.0, 24.5)
QR_TARGET_SIZE = 23.0                    # incl. quiet zone

# Berlin skyline band on the back side
SKY_X0, SKY_X1 = 16.0, 80.0
SKY_BASE = 39.2
SKY_TOP = 12.6

VRM_X0, VRM_X1 = 60.0, 80.0
