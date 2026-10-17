# Moved here from gpu_service/services/repetition_guard.py with the generation
# loop it belongs to (stage 3 of the move to ComfyUI): the
# local models generate inside ComfyUI now, and this is the loop that reads
# what they write. The copy in gpu_service/ falls with that directory in stage 8.
"""Stop a generation that has begun to repeat itself.

A model that repeats a passage has made that passage its own most probable
continuation, so it keeps going until the context is full. Measured on the
comparison page (2026-08-15): qwen3-vl:2b on a long framing prompt wrote
51,259 characters in 311 seconds, the same reflection question over and over.
Nothing else stops that -- output caps are forbidden platform-wide, and the
context ceiling is 4,096 tokens for the text models but 16,384 for the VLMs.

TWO rules, because a text runs away in two different shapes.

**Finished segments.** Count finished lines and sentences as they complete, and
say stop at the THIRD identical one. A reading repeats a heading, never a whole
sentence three times. Segments below 30 characters are skipped, so headings,
bullet markers and rules do not count. The limit was six at first, which is
where the comparison page had put it empirically, until a run of Wern 9b on the
language model comparison repeated its whole paragraph five times and passed
underneath it. Three repeats are the cap.

**A period in the tail.** The shape the first rule is structurally blind to: a
model whose inner state has been pushed out of the region where language lives
writes "and the, and the, and the" with no full stop and no line break, so no
segment ever completes and nothing is ever counted. Measured 2026-08-25 on the
Representation Engineering surface (Qwen3-4B, steering strength 3): the client
gave up after fifteen minutes with the answer still growing. So the tail is
read for a period as well. A string has period p exactly when s[p:] == s[:-p],
which makes the whole test one slice comparison per candidate period -- exact,
not a heuristic, and ten uninterrupted repetitions end the generation. Only the
tail is read, so the cost stays the same however long the answer already is.

It lives here, at the generation loop, rather than in one route: the call that
is most exposed to this -- the local describer of the image safety check --
is a blocking chat() with no stream anybody could watch.

Callers see it as finish_reason "repetition", alongside llama-cpp's own "stop"
and "length". What the model wrote up to that point stands; whether a stopped
text may still be used is the caller's decision, and for the safety chain the
answer is no.
"""
import re
from collections import Counter

SEGMENT_MIN_CHARS = 30
REPEAT_LIMIT = 3
_SEGMENT_BOUNDARY = re.compile(r"\n|(?<=[.!?…])\s")

# The periodic rule. The unit has to carry a letter or a digit, which keeps a
# row of dashes, a line of dots and an ASCII rule out of it -- those are
# punctuation doing its job. Ten repetitions of at least forty characters
# together put the shortest unit that can trigger at four characters.
LOOP_TAIL_CHARS = 600
LOOP_MIN_PERIOD = 2
LOOP_MAX_PERIOD = 60
LOOP_REPEATS = 10
LOOP_MIN_LENGTH = 40


class RepetitionGuard:
    """Watches a growing text for both shapes of a loop.

    Fed the pieces as they arrive; `feed` returns True the moment either rule
    fires, and keeps returning True afterwards. Neither rule rereads the whole
    text -- a segment is counted once, at the moment it is complete, and the
    period is looked for in the last few hundred characters only.

    After it fires, `segment` holds what repeated and `reason` says which rule
    saw it: "segment" or "loop".
    """

    def __init__(self, min_chars: int = SEGMENT_MIN_CHARS, repeat_limit: int = REPEAT_LIMIT):
        self._min_chars = min_chars
        self._repeat_limit = repeat_limit
        self._pending = ""
        self._seen: Counter = Counter()
        self._tail = ""
        self.triggered = False
        self.segment = ""
        self.reason = ""

    def feed(self, piece: str) -> bool:
        """Add a piece of the answer. True once the text has begun to loop."""
        if self.triggered or not piece:
            return self.triggered

        self._tail = (self._tail + piece)[-LOOP_TAIL_CHARS:]
        unit = self._repeating_unit()
        if unit:
            self.triggered = True
            self.segment = unit
            self.reason = "loop"
            return True

        self._pending += piece
        while True:
            match = _SEGMENT_BOUNDARY.search(self._pending)
            if not match:
                break
            segment = self._pending[:match.start()]
            self._pending = self._pending[match.end():]

            normalised = " ".join(segment.split()).lower()
            if len(normalised) < self._min_chars:
                continue
            self._seen[normalised] += 1
            if self._seen[normalised] >= self._repeat_limit:
                self.triggered = True
                self.segment = normalised[:120]
                self.reason = "segment"
                break

        return self.triggered

    def describe(self) -> str:
        """One line for the log: which rule saw it, and what repeated."""
        if self.reason == "loop":
            return "the unit %r %dx without a break" % (self.segment, LOOP_REPEATS)
        return "the same passage %dx: %r" % (self._repeat_limit, self.segment)

    def _repeating_unit(self) -> str:
        """The short unit the tail consists of, if it consists of one at all.

        Empty when the tail is ordinary text. The shortest period wins, so
        "ab ab ab ..." reports "ab " rather than the longer block that also
        fits.
        """
        tail = self._tail
        for period in range(LOOP_MIN_PERIOD, LOOP_MAX_PERIOD + 1):
            span = period * LOOP_REPEATS
            if span < LOOP_MIN_LENGTH:
                continue
            if span > len(tail):
                break
            # A necessary condition, two characters wide: unless the tail ends
            # the way it ended a period earlier, no comparison is needed. It
            # settles almost every candidate in ordinary text, and it costs two
            # character lookups rather than a slice.
            if tail[-1] != tail[-1 - period] or tail[-2] != tail[-2 - period]:
                continue
            window = tail[-span:]
            if window[period:] != window[:-period]:
                continue
            unit = window[:period]
            if any(ch.isalnum() for ch in unit):
                return unit
        return ""
