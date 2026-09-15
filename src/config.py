from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
POTATO_SCALE=.26
POTATO_COUNT=126
BOX_TARGET=18
BOX_MIN=15
BOX_MAX=20
BOX_COUNT=6
PHYSICS_HZ=240
CACHE_FPS=30
WATER_PARTICLES=2592
BELT_SPEED=.30
ROLL_RADIUS=.0095
ROLL_PITCH=.020
DECK_Z=1.50
FILL=(7.95,0.,1.143)
BOX_SIZE=(.30,.22,.18)
PALLET=(8.17,-1.02,.62)

def carton_target(remaining,cartons):
    """Balance the known demonstration batch within the requested pack range."""
    target=remaining//cartons
    if cartons>1:
        # Reserve room for two coasting potatoes at each later stop, so the
        # final carton can still contain at least fifteen.
        target=min(target,remaining-(BOX_MIN+2)*(cartons-1))
    if not BOX_MIN<=target<=BOX_MAX:
        raise ValueError(f'Cannot balance {remaining} potatoes across {cartons} cartons')
    return target
