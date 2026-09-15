"""Keep the terminal belt clear while the upstream gate holds the queue."""
class TerminalBeltDrive:
    def __init__(self, speed=.9, acceleration=1.08, clear_seconds=.8):
        self.maximum_speed=speed;self.speed=speed
        self.acceleration=acceleration;self.clear_seconds=clear_seconds

    def update(self, dt, *, ready, gripped, packing_elapsed=None):
        clearing=packing_elapsed is None or packing_elapsed<self.clear_seconds
        target=self.maximum_speed if ready and not gripped and clearing else 0.
        step=self.acceleration*dt
        self.speed+=max(-step,min(step,target-self.speed))
        return self.speed
