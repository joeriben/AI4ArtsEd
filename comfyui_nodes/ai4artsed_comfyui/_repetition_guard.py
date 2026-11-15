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
context window is 65,536 tokens (_local_llm.DEFAULT_CONTEXT_TOKENS).

TWO rules, because a text runs away in two different shapes.

**Finished segments.** Count finished lines and sentences as they complete. A
loop writes its rounds back to back: the same segment, or the same run of up
to twenty segments, written three times in a row ends the generation at the
third round. A segment that recurs between other lines ends it at its TENTH
occurrence. Segments below 30 characters are not counted on their own; in a
run they count, so a short line between two copies keeps them apart, and one
written with every copy is part of the round. A run counts once its text
reaches 30 characters. A segment that is nothing but a list mark ("2.", "-")
or a rule ("---", "____") is part of the passage after it and keeps nothing
apart. The same mark or rule written sixty times in a row, with nothing else
between, ends the generation as well.
Until 2026-10-31 the answer had one number for copies in a row and copies
between other lines alike, the third identical segment: six at
first, which is where the comparison page had put it empirically, three after a
run of Wern 9b on the language model comparison repeated its whole paragraph
five times and passed underneath it. At three, it ended a poem whose stanzas
close on the same sentence of 30 characters or more at its third stanza.
Since 2026-10-31 the answer counts as the think block does (docs/DEVELOPMENT_DECISIONS.md, 2026-10-31).

**A period in the tail.** The shape the first rule is structurally blind to: a
model whose inner state has been pushed out of the region where language lives
writes "and the, and the, and the" with no full stop and no line break, so no
segment ever completes and nothing is ever counted. Measured 2026-08-25 on the
Representation Engineering surface (Qwen3-4B, steering strength 3): the client
gave up after fifteen minutes with the answer still growing. So the tail is
read for a period as well. A string has period p exactly when s[p:] == s[:-p],
which makes the whole test one slice comparison per candidate period -- exact,
not a heuristic, and ten uninterrupted repetitions end the generation. A unit
of more than sixty and up to five hundred characters is a round, and where
the count does not see it -- no line and no sentence ends in it, or more than
twenty do -- three of them in a row end the generation, as three rounds of a
run of segments do: on 2026-10-31 Qwen 3 VL 4B, at the
Interception node of the canvas, wrote "not a myth, not a legend, ... not a
truth, not a lie," over and over, 144 characters with no full stop, for
thirteen minutes. Only the tail is read, so the cost stays the same however
long the answer already is.

**Inside a think block** the first rule counts apart. Its two numbers were
set there on 2026-10-29; the ten rests on no measurement. That day Qwen 3.8
27B, translating a Quechua text on the canvas, wrote '"uywankunawan" = with
animals.' a third time in its think block and was stopped there, by the count
of that day, after 3,932 characters, before it had written a word of the
answer. The block and the answer keep separate counts, so a translation
drafted twice in the block and given once as the answer is not three of one
sentence. The periodic rule reads every piece
whole, tags included. Which part of a piece stands in the block is the
caller's to say (feed_split): the generation loop knows from the prompt
whether the template opened the block, and the guard does not.

It lives here, at the generation loop, rather than in one route: a blocking
call has no stream anybody could watch.

Callers see it as finish_reason "repetition", alongside llama-cpp's own "stop"
and "length". What the model wrote up to that point stands; whether a stopped
text may still be used is the caller's decision, and for the safety chain the
answer is no. A caller that takes it can have it with what repeated standing in
it once (`once`): the Canvas translation, Interception and Model Adaption nodes
do (docs/DEVELOPMENT_DECISIONS.md, 2026-10-31).
"""
import re
from collections import Counter
from typing import List

SEGMENT_MIN_CHARS = 30
REPEAT_LIMIT = 3
SCATTERED_LIMIT = 10
ROUND_MAX_SEGMENTS = 20
MARKS_LIMIT = 60
_SEGMENT_BOUNDARY = re.compile(r"\n|(?<=[.!?…])\s")

# The periodic rule. The unit has to carry a letter or a digit, which keeps a
# row of dashes, a line of dots and an ASCII rule out of it -- those are
# punctuation doing its job. Ten repetitions of at least forty characters
# together put the shortest unit that can trigger at four characters.
LOOP_MIN_PERIOD = 2
LOOP_MAX_PERIOD = 60
LOOP_REPEATS = 10
LOOP_MIN_LENGTH = 40
# A longer unit is a round, and as many of them in a row as end a run of
# segments end the generation, unless the count sees it
# (RepetitionGuard._counted).
LOOP_MAX_ROUND = 500


class RepetitionGuard:
    """Watches a growing text for both shapes of a loop.

    Fed the pieces as they arrive; `feed` returns True the moment either rule
    fires, and keeps returning True afterwards. Neither rule rereads the whole
    text -- a segment is counted once, at the moment it is complete, and the
    period is looked for in the last fifteen hundred characters only.

    After it fires, `segment` holds what repeated and `reason` says which rule
    saw it: "segment" (one written for the tenth time), "round" (a run
    written three times in a row), "marks" (the same list mark or rule sixty
    times in a row) or "loop"; `in_think` says whether the think block repeated.
    """

    def __init__(self, min_chars: int = SEGMENT_MIN_CHARS, repeat_limit: int = REPEAT_LIMIT,
                 scattered_limit: int = SCATTERED_LIMIT):
        self._min_chars = min_chars
        self._repeat_limit = repeat_limit
        self._scattered_limit = scattered_limit
        self._pending = ""
        self._seen: Counter = Counter()
        self._run: List[str] = []
        self._think_pending = ""
        self._think_seen: Counter = Counter()
        self._think_run: List[str] = []
        self._marks_in_row = {False: ["", 0], True: ["", 0]}
        self._tail = ""
        self._tail_chars = max(LOOP_MAX_PERIOD * LOOP_REPEATS, LOOP_MAX_ROUND * repeat_limit)
        self._loop_repeats = LOOP_REPEATS
        self.triggered = False
        self.segment = ""
        self._passage = ""
        self.reason = ""
        self.in_think = False

    def feed(self, piece: str) -> bool:
        """Add a piece of the answer. True once the text has begun to loop."""
        return self.feed_split(piece, piece, "")

    def feed_split(self, piece: str, answer: str, thought: str) -> bool:
        """Add a piece of a reasoning model's output: `piece` as the model
        wrote it, `answer` and `thought` what of it stands outside and inside
        the think block, without the tags. True once the text has begun to
        loop."""
        if self.triggered or not piece:
            return self.triggered

        self._tail = (self._tail + piece)[-self._tail_chars:]
        unit = self._repeating_unit()
        if unit:
            self._fire(unit, "loop", bool(thought) and not answer)
            return True

        if thought:
            self._think_pending = self._count(self._think_pending + thought, thinking=True)
        if answer and not self.triggered:
            self._pending = self._count(self._pending + answer, thinking=False)
        return self.triggered

    def _count(self, pending: str, thinking: bool) -> str:
        """Count the segments `pending` has finished, in the tally of the
        answer or of the think block; the unfinished rest is handed back."""
        seen = self._think_seen if thinking else self._seen
        run = self._think_run if thinking else self._run
        while True:
            match = _SEGMENT_BOUNDARY.search(pending)
            if not match:
                break
            segment = pending[:match.start()]
            pending = pending[match.end():]

            normalised = " ".join(segment.split()).lower()
            if _mark(normalised):
                # The periodic rule passes over a unit without a letter or a
                # digit, so a loop of rules alone is counted here.
                if normalised:
                    marks = self._marks_in_row[thinking]
                    marks[1] = marks[1] + 1 if marks[0] == normalised else 1
                    marks[0] = normalised
                    if marks[1] >= MARKS_LIMIT:
                        self._fire(normalised, "marks", thinking)
                        break
                continue
            self._marks_in_row[thinking] = ["", 0]
            last = self._round(run, normalised)
            if last:
                self._fire(" / ".join(last)[:120], "round", thinking)
                break
            if len(normalised) < self._min_chars:
                continue
            seen[normalised] += 1
            if seen[normalised] >= self._scattered_limit:
                self._passage = normalised
                self._fire(normalised[:120], "segment", thinking)
                break
        return pending

    def _round(self, run: List[str], normalised: str) -> List[str]:
        """The run of segments `run` has just been given for the third time
        in a row; empty when there is none.

        Every segment but a list mark enters the sequence, short ones
        included, so that a line written between two copies keeps them apart. A run counts once
        its text reaches the segment minimum.
        """
        run.append(normalised)
        rounds = self._repeat_limit
        del run[:-ROUND_MAX_SEGMENTS * rounds]
        n = len(run)
        for k in range(1, ROUND_MAX_SEGMENTS + 1):
            if k * rounds > n:
                break
            last = run[n - k:]
            if sum(len(s) for s in last) < self._min_chars:
                continue
            if all(run[n - (i + 1) * k:n - i * k] == last for i in range(1, rounds)):
                return last
        return []

    def _fire(self, segment: str, reason: str, in_think: bool) -> None:
        self.triggered = True
        self.segment = segment
        self.reason = reason
        self.in_think = in_think

    def once(self, answer: str) -> str:
        """The answer with what repeated in it standing in it once; "" when
        the guard did not stop it.

        `answer` is what stands outside the think block, up to and with the
        piece that made the guard fire: the tokens written after the stop are
        not part of it. A loop the answer ends in keeps its first round
        (_one_round). So does a run written three times in a row, found again
        segment by segment as the guard counted it (_first_round), less each
        passage of that round that stood already before it
        (_without_what_stood), compared from 30 characters on. A passage
        written for the tenth time stands once from its first round on, and
        so does every other passage written again after that round
        (_each_passage_once). What stands before the
        repetition stays as written, and so does the whole answer when the
        think block repeated.
        """
        if not self.triggered:
            return ""
        if self.in_think:
            return answer.strip()
        if self.reason == "loop":
            return _one_round(answer, len(_root(self.segment)), self._repeat_limit).strip()
        if self.reason == "marks":
            return _up_to_the_first_mark(answer).strip()
        if self.reason == "round":
            found = self._first_round(answer)
            if found is None:
                # Only when `answer` is not the text the guard was fed.
                return answer.strip()
            begin, end = found
            return _without_what_stood(answer[:end], begin, self._min_chars).strip()
        return _each_passage_once(answer, self._passage).strip()

    def _first_round(self, text: str):
        """(begin, end) of the first round of the run the guard saw written
        three times in a row, with the segments of `text` counted again as
        `_count` counts them; None when `text` holds no such run."""
        run: List[str] = []
        # Each counted segment: where it begins with the list marks before
        # it, where it begins and ends, and those marks (key, start, end).
        spans = []
        at, marks = 0, []
        for boundary in _SEGMENT_BOUNDARY.finditer(text):
            key = " ".join(text[at:boundary.start()].split()).lower()
            if key and _mark(key):
                marks.append((key, at, boundary.start()))
            elif key:
                spans.append((marks[0][1] if marks else at, at, boundary.start(), tuple(marks)))
                marks = []
                last = self._round(run, key)
                if last:
                    k = len(last)
                    return _round_span(text, spans[-self._repeat_limit * k:], _root_run(last),
                                       self._repeat_limit)
            at = boundary.end()
        return None

    def describe(self) -> str:
        """One line for the log: which rule saw it, and what repeated."""
        where = " in its think block" if self.in_think else ""
        if self.reason == "loop":
            return "the unit %r %dx without a break%s" % (self.segment, self._loop_repeats, where)
        if self.reason == "round":
            return "the same run %dx in a row%s: %r" % (self._repeat_limit, where, self.segment)
        if self.reason == "marks":
            return "the same list mark or rule %dx in a row%s: %r" % (MARKS_LIMIT, where, self.segment)
        return "the same passage %dx%s: %r" % (self._scattered_limit, where, self.segment)

    def _repeating_unit(self) -> str:
        """The unit the tail consists of, if it consists of one at all.

        Empty when the tail is ordinary text. The shortest period wins, so
        "ab ab ab ..." reports "ab " rather than the longer block that also
        fits.
        """
        tail = self._tail
        # The unit of a period is the last `period` characters of the tail,
        # and it has to carry a letter or a digit: no period that reaches back
        # only over the signs the tail ends in can have one.
        bare = 0
        while bare < len(tail) and not tail[-1 - bare].isalnum():
            bare += 1
        for period in range(max(LOOP_MIN_PERIOD, bare + 1), LOOP_MAX_ROUND + 1):
            repeats = LOOP_REPEATS if period <= LOOP_MAX_PERIOD else self._repeat_limit
            span = period * repeats
            if span < LOOP_MIN_LENGTH or span > len(tail):
                continue
            # A necessary condition, two characters wide: unless the tail ends
            # the way it ended a period earlier, no comparison is needed. It
            # settles almost every candidate in ordinary text, and it costs two
            # character lookups rather than a slice.
            if tail[-1] != tail[-1 - period] or tail[-2] != tail[-2 - period]:
                continue
            window = tail[-span:]
            if window[period:] != window[:-period]:
                continue
            # A unit of up to sixty characters written over and over has ten
            # rounds, and a round the count sees is the count's.
            unit = window[:period]
            if period > LOOP_MAX_PERIOD and (len(_root(unit)) <= LOOP_MAX_PERIOD or self._counted(unit)):
                continue
            self._loop_repeats = repeats
            return unit
        return ""

    def _counted(self, unit: str) -> bool:
        """Whether the count stops a loop of `unit`: one whose round a line
        or a sentence ends in, of no more than ROUND_MAX_SEGMENTS segments
        besides the list marks, together as long as the segment minimum."""
        period, rounds = len(unit), unit * 3
        ends = [m for m in _SEGMENT_BOUNDARY.finditer(rounds, period) if m.start() < 2 * period]
        keys = []
        for i, end in enumerate(ends):
            to = ends[i + 1].start() if i + 1 < len(ends) else ends[0].start() + period
            key = " ".join(rounds[end.end():to].split()).lower()
            if not _mark(key):
                keys.append(key)
        return 0 < len(keys) <= ROUND_MAX_SEGMENTS and sum(len(k) for k in keys) >= self._min_chars


def _root(unit: str) -> str:
    """The shortest piece `unit` is made of: "no no " is "no " twice. The
    guard reports a unit of at least LOOP_MIN_LENGTH // LOOP_REPEATS
    characters."""
    n = len(unit)
    for d in range(1, n + 1):
        if n % d == 0 and unit[:d] * (n // d) == unit:
            return unit[:d]
    return unit


def _periodic_from(text: str, period: int, rounds: int):
    """Where the run of `period`-character rounds that `text` ends in begins,
    or None when it ends in fewer than `rounds` rounds, in fewer than
    LOOP_MIN_LENGTH characters, or in rounds without a letter or a digit.
    The run reaches back over whatever text before it ends the way a round
    ends."""
    n = len(text)
    if period < 1 or rounds * period > n:
        return None
    start = n - period
    while start > 0 and text[start - 1] == text[start - 1 + period]:
        start -= 1
    if (n - start) // period < rounds or n - start < LOOP_MIN_LENGTH:
        return None
    if not any(ch.isalnum() for ch in text[start:start + period]):
        return None
    return start


# Where a sentence or a clause ends. The stops of Latin, Devanagari, Arabic,
# Urdu, Armenian and Ethiopic script want whitespace after them, the wide
# signs of Chinese and Japanese none; closing quotes and brackets go with the
# stop before them.
_STOPS = ".!?…।॥؟۔։።፧"
_WIDE_STOPS = "。！？"
_PAUSES = ",;:،؛"
_WIDE_PAUSES = "，、；："
_CLOSERS = "\"'”’»」』)]）】》〉"


def _ends(text: str, c: int, sentence: bool) -> bool:
    """Whether a sentence (or else a clause) ends right before position `c`.

    A full stop after a single letter ends an abbreviation ("z. B.",
    "e. g."), and so does a stop the text goes on after in lower case.
    """
    n = len(text)
    j = c
    while j > 0 and text[j - 1] in _CLOSERS:
        j -= 1
    if j == 0:
        return False
    sign = text[j - 1]
    if sign in (_WIDE_STOPS if sentence else _WIDE_PAUSES):
        return True
    if sign not in (_STOPS if sentence else _PAUSES) or (c < n and not text[c].isspace()):
        return False
    if sentence:
        after = c
        while after < n and text[after].isspace():
            after += 1
        if after < n and text[after].islower():
            return False
        if sign == "." and j >= 2 and text[j - 2].isalpha() and (j == 2 or not text[j - 3].isalpha()):
            return False
    return True


def _round_end(text: str, start: int, period: int) -> int:
    """Where the first round of the run that begins at `start` ends.

    Where the text before the run ends the way a round ends, the run reaches
    back into it, and the first round ends that much later than one period
    on. Unless the text before ends a sentence, or there is none, so that the
    round begins where the run does, the end is the first place from one
    period on (whitespace at the end of a round aside), and no further than
    another period or sixty characters, whichever is less, where a sentence
    ends; failing that, a clause; failing that, a word.
    """
    n = len(text)
    begin = start
    while text[begin].isspace():
        begin += 1
    low = begin + period
    while low > begin + 1 and text[low - 1].isspace():
        low -= 1
    before = begin
    while before > 0 and text[before - 1].isspace():
        before -= 1
    if before == 0 or _ends(text, before, sentence=True):
        return low
    high = min(begin + period + min(period, LOOP_MAX_PERIOD), n)
    for ends in (lambda c: _ends(text, c, sentence=True),
                 lambda c: _ends(text, c, sentence=False),
                 lambda c: c < n and text[c].isspace() and not text[c - 1].isspace()):
        for c in range(low, high):
            if ends(c):
                return c
    return begin + period


def _one_round(text: str, period: int, rounds: int) -> str:
    """`text` with the loop it ends in cut to its first round; unchanged when
    it ends in none.

    The round is the unit the guard saw, reduced to the piece it is made of
    (_root). When the tags of a think block the model opened and closed in
    every round were part of that unit, the answer repeats a shorter one:
    then the round is the unit the end of `text` repeats most often, among
    the units the guard looks for, the shorter one of two repeated equally
    often.
    """
    start = _periodic_from(text, period, rounds)
    if start is None:
        best = None
        for candidate in range(LOOP_MIN_PERIOD, min(LOOP_MAX_ROUND, len(text) // 2) + 1):
            at = _periodic_from(text, candidate, rounds)
            if at is not None and (best is None or (len(text) - at) // candidate > best[0]):
                best = ((len(text) - at) // candidate, at, candidate)
        if best is None:
            return text
        _, start, period = best
    return text[:_round_end(text, start, period)]


def _without_what_stood(text: str, begin: int, min_chars: int) -> str:
    """`text` with each passage after `begin` taken out that stood already
    before it, a list mark or an empty line before it going with it.

    Only passages of the length the guard counts are compared, so a short
    answer such as "Ja." stays where it stands, and so does what repeats
    after `begin` alone. A list mark that closes the line of the passage
    before it ("... Nr. 7.") goes where that passage goes.
    """
    stood, kept, held = [], [], ""
    dropped = False
    at = 0
    pieces = []
    for boundary in _SEGMENT_BOUNDARY.finditer(text):
        pieces.append((text[at:boundary.start()], text[at:boundary.end()], at))
        at = boundary.end()
    pieces.append((text[at:], text[at:], at))
    for segment, written, start in pieces:
        key = " ".join(segment.split()).lower()
        if start < begin:
            if not _mark(key):
                stood.append(key)
            kept.append(written)
        elif key and _mark(key) and not _line_begins_at(text, start) \
                and _line_ends_at(text, start + len(segment)):
            if not dropped:
                kept.append(held + written)
            held = ""
        elif _mark(key):
            held += written
        elif len(key) >= min_chars and any(_is_copy(s, key) for s in stood):
            held, dropped = "", True
        else:
            kept.append(held + written)
            held, dropped = "", False
    return "".join(kept)


def _root_run(run: List[str]) -> int:
    """How many segments the shortest run has that `run` is written of: a
    sentence written six times in a row is three rounds of two of it, and
    one round of it is the sentence once."""
    k = len(run)
    for d in range(1, k + 1):
        if k % d == 0 and run[:d] * (k // d) == run:
            return d
    return k


def _round_span(text: str, spans: list, d: int, rounds: int):
    """(begin, end) of the first round, from the spans of the counted
    segments of all `rounds` rounds, `d` segments each.

    The round begins with its first segment, or with the list marks before
    it where every round has marks before it, and ends with its last
    segment. Of the marks between the first round and the second, those on
    the line of that segment end the round with it ("... Nr. 7."). Without
    a line break between the rounds, the second round begins with as many
    of them as the first round has of its own, the first round ends with
    the rest, and where it has none of its own, with all of them if they
    are written alike between every two rounds or stand after a single
    letter ("p. 12."). Where the
    first round begins
    inside a sentence, after a full stop the segments cut at ("z. B.",
    'Il dit : « Viens ici. »'), the rounds are written letter for letter
    alike and the text before ends the way a round ends, from the beginning
    of the text, of a line or of a sentence on, the round begins with the
    text it reaches back over.
    """
    first, last = spans[0], spans[d - 1]
    if rounds < 2:
        return first[0], last[2]
    second = spans[d]

    def keys(span):
        return [key for key, _, _ in span[3]]

    own = keys(first) if all(spans[i * d][3] for i in range(1, rounds)) else []
    begin, end = (first[0] if own else first[1]), last[2]
    between = second[3]
    line_break = text.find("\n", end, second[1])
    if line_break != -1:
        closing = [mark for mark in between if mark[2] <= line_break]
    elif own:
        alike = rounds > 2 and all(keys(spans[i * d]) == keys(second) for i in range(2, rounds))
        lead = len(own) if not alike or keys(second)[len(between) - len(own):] == own else 0
        closing = between[:max(len(between) - lead, 0)]
    elif (rounds > 2 and all(keys(spans[i * d]) == keys(second) for i in range(2, rounds))) \
            or _after_a_letter(text, end):
        closing = between
    else:
        closing = []
    if closing:
        end = closing[-1][2]
    period = second[0] - first[0]
    stop = spans[rounds * d - 1][2]
    if not _sentence_begins_at(text, begin) and text[begin + period:stop] == text[begin:stop - period]:
        back = begin
        while back > 0 and text[back - 1] == text[back - 1 + period]:
            back -= 1
        ahead = back
        while text[ahead].isspace():
            ahead += 1
        before = back
        while before > 0 and text[before - 1].isspace():
            before -= 1
        if ahead < begin and (before == 0 or "\n" in text[before:ahead]
                              or _ends(text, before, sentence=True)):
            begin, end = ahead, ahead + period
            while end > begin and text[end - 1].isspace():
                end -= 1
    return begin, end


# A segment that is nothing but the mark of a list item ("2.", "-", "**") or
# a rule ("---", "____") belongs to the passage after it.
_LIST_MARK = re.compile(r"\d{1,3}[.)]|[-*•·–—#>_=]+")


def _mark(key: str) -> bool:
    return not key or bool(_LIST_MARK.fullmatch(key))


def _up_to_the_first_mark(text: str) -> str:
    """`text` up to and with the first of the same list mark or rule it ends
    in."""
    at, first, last = 0, None, ""
    for boundary in _SEGMENT_BOUNDARY.finditer(text):
        key = " ".join(text[at:boundary.start()].split()).lower()
        if key and _mark(key):
            if key != last:
                first, last = boundary.start(), key
        elif key:
            first, last = None, ""
        at = boundary.end()
    return text if first is None else text[:first]


def _line_begins_at(text: str, i: int) -> bool:
    j = i
    while j > 0 and text[j - 1].isspace():
        j -= 1
    return j == 0 or "\n" in text[j:i]


def _line_ends_at(text: str, i: int) -> bool:
    j = i
    while j < len(text) and text[j].isspace():
        j += 1
    return j == len(text) or "\n" in text[i:j]


def _after_a_letter(text: str, i: int) -> bool:
    """Whether the text before `i` ends in a single letter and a full stop
    ("z.", "p.")."""
    j = i
    while j > 0 and text[j - 1].isspace():
        j -= 1
    return j >= 2 and text[j - 1] == "." and text[j - 2].isalpha() and (j == 2 or not text[j - 3].isalpha())


def _sentence_begins_at(text: str, i: int) -> bool:
    """Whether a line or a sentence begins at `i`. The segments are cut at
    every full stop before a space, and one can stand inside a sentence,
    after a single letter ("z. B.") or before the quote that closes it
    ('« Viens ici. »')."""
    if _line_begins_at(text, i):
        return True
    return text[i] not in _CLOSERS and not _after_a_letter(text, i)


def _is_copy(key: str, passage: str) -> bool:
    """A segment that is `passage`, or `passage` after a label on the same
    line ("Translation: ...", "**Translation:** ...")."""
    if key == passage:
        return True
    if not key.endswith(" " + passage):
        return False
    return key[:-len(passage)].rstrip(" *").endswith(":")


def _each_passage_once(text: str, passage: str) -> str:
    """`text` with what was written again after the first round of `passage`
    taken out.

    Passages are the segments the guard counts, compared as it compares them,
    whatever the case and the spacing. The first round runs up to the second
    copy of `passage`, less the segments before that copy that repeat the
    ones before the first (the heading or the short first sentence of a
    block written over and over);
    it stays as written, and so does everything before it. After it, every
    segment that stood already goes, and every copy of `passage`; a list mark
    or an empty line goes with the passage after it. The unfinished passage
    at the end goes when it is the beginning of one already written (the
    next copy, which the stop cut off) or a list mark. Unchanged when
    `passage` does not stand in two segments of `text`.
    """
    items = []
    at = 0
    for boundary in _SEGMENT_BOUNDARY.finditer(text):
        segment = text[at:boundary.start()]
        items.append((" ".join(segment.split()).lower(), segment + boundary.group()))
        at = boundary.end()
    rest = text[at:]
    copies = [i for i, (key, _) in enumerate(items) if _is_copy(key, passage)]
    if len(copies) < 2:
        return text
    first, second = copies[0], copies[1]

    lead = 0
    while first - lead > 0 and second - lead - 1 > first:
        one, other = items[first - lead - 1][0], items[second - lead - 1][0]
        if one != other and not (_mark(one) and _mark(other)):
            break
        lead += 1
    end = second - lead

    kept = [written for _, written in items[:end]]
    seen = {key for key, _ in items[:end] if not _mark(key)}
    held = ""
    for key, written in items[end:]:
        if _mark(key):
            held += written
        elif key in seen or _is_copy(key, passage):
            held = ""
        else:
            seen.add(key)
            kept.append(held + written)
            held = ""
    key = " ".join(rest.split()).lower()
    if not _mark(key) and not any(other.startswith(key) for other in seen):
        kept.append(held + rest)
    return "".join(kept)
