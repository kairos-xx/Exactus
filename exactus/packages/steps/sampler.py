# Copyright (c) 2026
"""Sample process-tree CPU, memory and disk I/O while a step log is open.

The sampler runs on a daemon thread and reports one ``cpu=… rss=… …``
field string per interval through a callback, so the step log can write
it as a ``~sample`` line next to the step lines.  Everything is measured
for the current process and all of its descendants, which is where the
checks, compilers and test runners spend their time.
"""

from __future__ import annotations

from threading import Event, Thread
from time import monotonic
from typing import TYPE_CHECKING, Final, final

from psutil import Error as PsutilError
from psutil import Process, disk_io_counters

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Protocol
if TYPE_CHECKING:

    class _IoCounters(Protocol):
        """Per-process I/O counters offered on platforms that support them.

        Attributes:
            read_bytes: Lifetime bytes read by the process.
            write_bytes: Lifetime bytes written by the process.

        """

        read_bytes: Final[int]
        write_bytes: Final[int]

    class _CpuTimes(Protocol):
        """CPU times tuple offered by ``Process.cpu_times``.

        Attributes:
            user: Seconds spent in user mode.
            system: Seconds spent in kernel mode.

        """

        user: Final[float]
        system: Final[float]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        mib: Grouped module constant.

    """

    mib: Final[float] = 1024.0 * 1024.0


@final
class ResourceSampler:
    """Emit periodic resource usage fields for the process tree.

    Attributes:
        interval: Seconds between samples.

    """

    def __init__(
        self,
        *,
        emit: Callable[[str], None],
        interval: float,
    ) -> None:
        """Prepare a stopped sampler.

        Args:
            emit: Receives one space-separated ``key=value`` string per
                sample.
            interval: Seconds between samples; must be positive.

        """
        self.interval: float = interval
        self._emit: Callable[[str], None] = emit
        self._stop: Event = Event()
        self._thread: Thread | None = None
        self._cpu: dict[int, float] = {}
        self._io: dict[int, tuple[int, int]] = {}
        self._system: tuple[int, int] | None = None
        self._last: float = monotonic()

    def start(self) -> None:
        """Begin sampling on a daemon thread."""
        self._last = monotonic()
        self._thread = Thread(
            target=self._run,
            name="exactus-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop sampling and wait for the thread to finish."""
        self._stop.set()
        thread: Thread | None = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        """Sample until stopped."""
        while not self._stop.wait(timeout=self.interval):
            try:
                self._emit(self._sample())
            except (PsutilError, OSError):
                continue

    def _sample(self) -> str:
        """Measure the process tree once.

        Returns:
            Space-separated ``key=value`` fields for one sample.

        """
        now: float = monotonic()
        wall: float = max(now - self._last, 1e-06)
        self._last = now
        processes: list[Process] = [Process()]
        processes.extend(processes[0].children(recursive=True))
        cpu_delta: float = 0.0
        rss: int = 0
        threads: int = 0
        read: int = 0
        write: int = 0
        per_process_io: bool = True
        seen: set[int] = set()
        for process in processes:
            io_counters: Callable[[], _IoCounters] | None = getattr(
                process,
                "io_counters",
                None,
            )
            try:
                times: _CpuTimes = process.cpu_times()
                total: float = times.user + times.system
                cpu_delta += max(0.0, total - self._cpu.get(process.pid, 0.0))
                self._cpu[process.pid] = total
                rss += process.memory_info().rss
                threads += process.num_threads()
                seen.add(process.pid)
                if io_counters is None:
                    per_process_io = False
                else:
                    counters: _IoCounters = io_counters()
                    before: tuple[int, int] = self._io.get(process.pid, (0, 0))
                    read += max(0, counters.read_bytes - before[0])
                    write += max(0, counters.write_bytes - before[1])
                    self._io[process.pid] = (
                        counters.read_bytes,
                        counters.write_bytes,
                    )
            except AttributeError:
                per_process_io = False
            except PsutilError:
                continue
        if not per_process_io:
            read, write = self._system_io()
        return f"cpu={cpu_delta / wall * 100.0:.1f} rss={
            rss / Constants.mib:.1f} threads={threads} procs={len(seen)} read={
            read / Constants.mib / wall:.2f} write={
            write / Constants.mib / wall:.2f} ioscope={
            ('proc' if per_process_io else 'system')
        }"

    def _system_io(self) -> tuple[int, int]:
        """Return system-wide disk byte deltas since the previous call.

        Platforms without per-process I/O counters fall back to this.

        Returns:
            ``(read_bytes, write_bytes)`` deltas, zero when unavailable.

        """
        counters: _IoCounters | None = disk_io_counters()
        if counters is None:
            return (0, 0)
        current: tuple[int, int] = (counters.read_bytes, counters.write_bytes)
        before: tuple[int, int] | None = self._system
        self._system = current
        if before is None:
            return (0, 0)
        return (max(0, current[0] - before[0]), max(0, current[1] - before[1]))
