"""Worker threads for vectorized numpy work, sized by what helps on this host.

The enumeration cost probe (services.stl_generator._probe_throughput) times
one thread against all usable CPUs at startup and keeps the faster; until then
work runs on one thread.
"""
import os

_worker_threads = 1


def available_cpus() -> int:
    """CPUs this process may use: its affinity, capped by a cgroup v2 CPU quota."""
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    try:
        with open("/sys/fs/cgroup/cpu.max", encoding="ascii") as fh:
            quota, period = fh.read().split()
        if quota != "max":
            cpus = min(cpus, max(1, int(quota) // int(period)))
    except (OSError, ValueError):
        pass
    return cpus


def worker_threads() -> int:
    return _worker_threads


def set_worker_threads(count: int) -> None:
    global _worker_threads
    _worker_threads = max(1, count)
