__author__ = 'davidc'


# Render constants bitmask
RENDER_STANDARD=0
RENDER_OUTLINES=1
RENDER_SELECTED=2
RENDER_FORCE_FG=4


# Hints for efficient rendering
RENDER_HINT_NORMAL = 0
RENDER_HINT_ONCE = 1 # Geometry will be drawn once, so don't save
                     # Usually used for 'live' overlays
