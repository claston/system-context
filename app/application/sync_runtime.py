import threading
import time


class SyncRuntimeState:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._shutting_down = False
        self._active_jobs = 0

    def reset_startup(self) -> None:
        with self._condition:
            self._shutting_down = False

    def begin_shutdown(self) -> None:
        with self._condition:
            self._shutting_down = True
            self._condition.notify_all()

    def is_shutting_down(self) -> bool:
        with self._condition:
            return self._shutting_down

    def try_acquire_job_slot(self) -> bool:
        with self._condition:
            if self._shutting_down:
                return False
            self._active_jobs += 1
            return True

    def release_job_slot(self) -> None:
        with self._condition:
            if self._active_jobs > 0:
                self._active_jobs -= 1
            if self._active_jobs == 0:
                self._condition.notify_all()

    def wait_for_idle(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._condition:
            while self._active_jobs > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True
