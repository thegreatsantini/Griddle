from griddle.backends.base import Backend


class Bot:
    def __init__(self, backend: Backend) -> None:
        self._backend = backend
        self._warnings = {}

    @property
    def busy(self) -> bool:
        """True while a grab or release is still finishing."""
        return self._backend.busy
    
    def drive(self, fwd: float, turn: float) -> None:
        """Tank drive. fwd and turn both clamp to -1.0 .. 1.0."""
        clamped_fwd = max(-1, min(1, fwd ))
        clamped_turn = max(-1, min(1, turn ))
        if clamped_fwd != fwd:
            self._warn_once("drive_fwd", f"drive() fwd clamped: {fwd} -> {clamped_fwd}")
        self._backend.drive(clamped_fwd,clamped_turn)
        
    def grab(self) -> None:
        """Close the gripper. Returns immediately; check `busy`."""
        self._backend.grab()
        
    def release(self) -> None:
        """Open the gripper. Returns immediately; check `busy`."""
        self._backend.release()
        
    def find_cube(self, color: str) -> object | None:
        """Look for a cube of `color`.

        Returns None if not visible, else an object with
        `x_offset` and `size`. Raises ValueError on a bad color.
        """       
        params = self._backend.find_cube(color)
        if (not params):
            return None
        else: 
            return {
            "x_offset" : params.x_offset,
            "size": params.size,
            }
            
    def detect_shown_color(self) -> str:
        """Read the color of a cube held up to the camera.""" 
        return self._backend.detect_shown_color()

    def _warn_once(self, key: str, message: str) -> None:
        """Emit `message` the first time `key` is seen. Private."""
        if key not in self._warnings:
            print(message)
            self._warnings[key] = message