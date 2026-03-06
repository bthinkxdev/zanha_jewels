"""
Temporary DEBUG-only tracing for ProductUpdateView edit flow.
Uses print() with time for each step (no logger). Only runs when settings.DEBUG_TRACE is True.
"""
import time

from django.conf import settings


def _enabled():
    return getattr(settings, "DEBUG_TRACE", False)


class Trace:
    """Print step timings (elapsed seconds). No-op when DEBUG_TRACE is False."""

    def __init__(self, label):
        self.label = label
        self.start = time.perf_counter()
        self._enabled = _enabled()
        if self._enabled:
            print("[EDIT +%.4fs] START: %s" % (0.0, label))

    def step(self, msg):
        if self._enabled:
            elapsed = time.perf_counter() - self.start
            print("[EDIT +%.4fs] %s" % (elapsed, msg))

    def end(self):
        if self._enabled:
            elapsed = time.perf_counter() - self.start
            print("[EDIT +%.4fs] END: %s (total %.4fs)" % (elapsed, self.label, elapsed))
