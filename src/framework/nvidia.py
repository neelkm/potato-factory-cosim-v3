"""Import the unchanged, pinned NVIDIA reference package."""
from pathlib import Path
import sys
VENDOR=Path(__file__).resolve().parents[2]/'vendor/nvidia_cosim'
if str(VENDOR) not in sys.path:sys.path.insert(0,str(VENDOR))
from cosim import load_topology,WavefrontScheduler,Simulation,CouplingMode
from cosim.core.scheduler import SerialExecutor
from cosim.core.handoff import HandoffPolicy,HandoffZone
from cosim.core.partition import ReplicaRouter,SlotPool
