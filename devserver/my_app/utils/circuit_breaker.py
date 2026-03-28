"""
Circuit Breaker for safety LLM verification calls.

Three states:
- CLOSED (normal): LLM calls go through
- OPEN (after consecutive failures): attempt self-healing, then fail-closed
- HALF_OPEN (after cooldown): one probe call tests recovery

Replaces the TEMPORARY fail-open markers from Session 217 emergency fixes.
Integrates with llm_watchdog for automatic LLM health checking.
"""

import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for LLM verification calls (safety system)."""

    def __init__(self, name: str, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                logger.info(f"[CIRCUIT-BREAKER:{self.name}] OPEN → HALF_OPEN (cooldown expired)")
        return self._state

    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def record_failure(self):
        """Record a failed LLM call (None return)."""
        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        if self._consecutive_failures >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"[CIRCUIT-BREAKER:{self.name}] → OPEN after {self._consecutive_failures} "
                    f"consecutive failures — attempting self-healing"
                )
                # Attempt automatic LLM restart
                if self._attempt_self_healing():
                    # LLM recovered — reset to CLOSED
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    logger.info(f"[CIRCUIT-BREAKER:{self.name}] Self-healing succeeded → CLOSED")

    def _attempt_self_healing(self) -> bool:
        """Try to restart LLM backend automatically. Returns True if recovered."""
        try:
            from my_app.utils.llm_watchdog import attempt_restart
            return attempt_restart()
        except Exception as e:
            logger.error(f"[CIRCUIT-BREAKER:{self.name}] Self-healing error: {e}")
            return False

    def record_success(self):
        """Record a successful LLM call."""
        if self._state != CircuitState.CLOSED:
            logger.info(f"[CIRCUIT-BREAKER:{self.name}] {self._state.value} → CLOSED (recovery confirmed)")
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0


# Module-level singleton instances — one per safety verification type
safety_breaker = CircuitBreaker("safety-llm", failure_threshold=3, cooldown_seconds=30.0)
