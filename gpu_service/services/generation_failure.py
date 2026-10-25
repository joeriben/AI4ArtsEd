"""What a generation says when it broke.

Until 2026-09-07 the two generating backends answered a failure by returning
None, and their routes turned that into one sentence — "Generation failed",
"Audio generation failed". The reason CUDA gave stayed in this service's log.
By the time the DevServer's router saw the run it read

    Python chunk execution failed: SD3.5 generation returned empty result

which is true of every failure there is, so nothing downstream could tell an
exhausted card from a missing file. The router's own switch — the one that
keeps a run OFF a second model when the card is the problem — was reading that
sentence and finding nothing in it (schemas/engine/backend_router.py,
_is_card_fault).

The reason travels as an exception, the way GpuBusy and GenerationCancelled
already do here: those two are not failures and are raised past the catch, this
one is a failure and carries its own words.
"""


class GenerationFailed(RuntimeError):
    """A generation broke, with the reason the caller can be told."""
