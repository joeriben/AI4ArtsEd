# DevServer Architecture

**Part 40: GPU Admission Gate — one heavy operation at a time**

---

## Overview

Three processes put load on the same card: the **GPU service** (diffusers, HeartMuLa,
MMAudio, ImageBind, Stable Audio, Hunyuan3D, the local LLM/VLM), **ComfyUI** (every JSON
chunk), and the **DevServer** itself, which orchestrates both. Each of them used to decide
on its own whether there was room. Several of them read free VRAM in the same second, each
concluded there was room, and each allocated — the classic check-then-act race. On a 96 GB
card that produced a hard OOM during a live course; the workshop could not generate.

The admission gate replaces that arithmetic with a much duller rule:

> **Exactly one heavy operation may allocate at a time — across all three processes.**

The gate is therefore **not** a memory manager. It does not add up model sizes and it does
not promise that a model fits. It **serialises in time**. `required_mb` is `0` on nearly
every path; the only caller that passes a real number is HeartMuLa (16 GB), because that
one genuinely refuses rather than waits (see *Deployment note* below).

---

## Where it lives

| Concern | File |
|---|---|
| The gate itself (since stage 7 of the move to ComfyUI, 2026-09-15) | `devserver/my_app/services/gpu_gate.py` |
| The GPU service's own gate, which leases the one above for every hold of its own (`POST /api/gate/lease/*`) | `gpu_service/services/gpu_admission.py` |
| Measured per-model statistics | `devserver/my_app/services/gpu_model_stats.py` (seeded once from the GPU service's `gpu_service/services/gpu_model_stats.py`) |
| HTTP surface | `devserver/my_app/routes/gpu_gate_routes.py` (`/api/gate/...`; the GPU service's `/api/gpu/...` was struck in stage 8) |
| Lease client (in-process) | `devserver/my_app/services/gpu_lease_client.py` |
| ComfyUI lease wrapper | `devserver/my_app/services/comfyui_ws_client.py` |
| Warm-ahead worker (DevServer side) | `devserver/my_app/services/gpu_warm_ahead.py` |
| Configuration | `devserver/config.py` (`GPU_ADMISSION_*`; the GPU service's own in `gpu_service/config.py`) |

---

## The three ways in

### 1. `slot()` — local, in-process

```python
with admission.slot(kind="diffusers", model_id=model_id, required_mb=0, priority=0):
    ...  # the heavy work
```

A context manager. Blocks until the slot is free, holds it for the duration of the block,
gives it back in `finally` — including on exception.

**Reentrant per thread.** `slot()` counts a per-thread depth (`threading.local`). A nested
acquisition on the same thread returns immediately without taking a second slot. This is
what makes it possible to gate *loading* and *inference* separately while an inference path
that loads on demand still works: the outer inference slot covers the inner load. Without
this, every load path would self-deadlock.

**Plain `threading.Condition`, never asyncio.** The Flask/Waitress routes spin up a fresh
event loop per request, so an asyncio primitive would be bound to a loop that dies with the
request. All waiting is done on OS threads.

### 2. `@gated(...)` — route decorator

For routes whose whole body is heavy. Used on the MMAudio, Stable Audio (2),
cross-aesthetic (3, this is also where ImageBind runs) and Hunyuan3D routes.

### 3. The remote lease — acquire / heartbeat / release over HTTP

ComfyUI is a separate process; it cannot take a Python context manager. Instead the
**DevServer** takes a lease on ComfyUI's behalf for the duration of a ComfyUI job, in its
own process (`services/gpu_lease_client.py`). The same lease stands on HTTP for a holder
outside that process — the GPU service, whose own gate leases here for every hold of its
own (`gpu_admission.py`, `_lease_upstream`), a research script, an operator's curl:

```
POST /api/gate/lease/acquire   -> {"token": "…"}
POST /api/gate/lease/heartbeat  (every 30 s while the job runs)
POST /api/gate/lease/release
```

`devserver/my_app/services/comfyui_ws_client.py` wraps every workflow submission in
`gpu_lease(...)`. If the DevServer dies mid-job the lease is **reaped** after
`GPU_ADMISSION_HEARTBEAT_TIMEOUT_S` (120 s) — the card is never held by a corpse.

---

## Model identity

The gate needs to know *which* model an operation will use, in one namespace across both
paths:

* **diffusers** leases carry the HuggingFace model id
  (`diffusers::stabilityai/stable-diffusion-3.5-large`).
* **ComfyUI** leases carry the **checkpoint filename extracted from the workflow** by
  `_checkpoint_of()` in `comfyui_ws_client.py`
  (`comfyui::wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors`).

`_checkpoint_of()` prefers loader nodes (`CheckpointLoaderSimple`, `UNETLoader`, …) and
sorts by node id, so a workflow that also loads a shared text encoder is identified by its
*diffusion* model, not by the encoder it shares with three other workflows. All 20 workflow
chunks were checked by hand for this.

Loading and running the same model are **different kinds** on purpose — `diffusers-load::X`
and `diffusers::X` — because they have very different durations and very different VRAM
footprints, and the statistics keep them apart.

---

## The `llm-load` lease — and what a slot now covers

The kind is unchanged: a local LLM/VLM load takes `slot("llm-load", alias, 0, NORMAL,
timeout_s=5.0)` and, on `GpuBusy`, goes ahead **unserialised** rather than waiting. The safety
chain runs on every prompt, and a content check that queued behind a video render would stop
the prompt that is waiting for that render.

What has changed is what happens inside those seconds. The engine now spawns a supervised
`llama-server` child per alias (Part 31), so the lease covers the spawn **and the child's
readiness**: `/health` polled every 250 ms, bounded by the 180 s stall bound (nothing written,
nothing read off disk, no movement in the child's own per-PID NVML figure) and by the 900 s
per-attempt ceiling. Both bounds exist as much for this slot as for the child — a load that
never ends holds the plant-wide load lock, and with it every content check on the platform.
A refused load raises, the lease is marked `failed`, and the attempt stays out of the
`llm-load` duration bucket (see *Aborted runs do not enter the statistics*).

**Inference on this path takes no slot at all**, and that is a deliberate carve-out:
`_RUN_KINDS_WITHOUT_A_SLOT = {"llm"}`. Loading the weights takes the card, so it is gated; but
nothing of that model queues through the gate afterwards, so `_load_is_claimable()` refuses to
arm the post-load reservation for it — holding the card open for a run that never comes back
is pure idle time in a room that is waiting. Concurrency on the LLM path is handled one level
down instead: each child runs a single slot (`-np 1`), so two requests for the same alias
queue inside the child rather than at the gate.

**What an emergency reclaim now costs.** `emergency_reclaim_foreign()` ends the owned children
first (Part 27) and calls `forget_resident()` here. The children are the cheapest thing on the
card to lose — and they are not free: every reading in flight on them dies with its process and
surfaces as a 500 carrying the exit code, and the safety chain has nothing to check with until
the next request spawns a child again and pays that load. Before the child engine a reclaim
left the LLM models alone, because they were inside this process; now they are the first thing
it removes.

---

## The dequeue policy

Strict arrival order is fair but wasteful: `SD SD SD VIDEO SD SD` forces three model swaps
where one would do. The gate therefore prefers a waiter whose model is **already resident**,
under hard bounds that are checked **before** affinity:

`_pick_from(pool, resident, now)` in this order:

1. **Fairness first.** Any waiter that has been queued for
   `GPU_ADMISSION_AFFINITY_MAX_WAIT_S` (300 s), or that has been passed
   `GPU_ADMISSION_MAX_OVERTAKES` (3) times, goes next — unconditionally.
2. **Post-load reservation.** If a `*-load` lease has just finished, the slot is reserved
   for that same model for `GPU_ADMISSION_POST_LOAD_RESERVE_S` (5 s), so the run the load
   was made for actually gets the card. Without this, a load and its own inference are two
   separate acquisitions on two different threads, and a foreign waiter could slip between
   them — measured live before the fix. The reservation is **not** conditioned on a
   matching waiter already being in the queue: the run it is held for has not queued yet,
   which is the entire situation it addresses. It is not armed at all for a load that
   raised (nothing was put on the card) or for a kind whose inference never takes the slot
   (the safety chain's language models — a reservation for those could never be claimed and
   would simply park the card; see *The `llm-load` lease* above).
3. **Affinity.** Otherwise, the first waiter whose model matches the resident one.
   Both this and the reservation above are skipped entirely when
   `GPU_ADMISSION_AFFINITY=false`, so the off-switch really does restore arrival order.
4. **Arrival order.** Otherwise the head of the queue.

Every waiter that is passed gets `overtaken += 1`. `GPU_ADMISSION_AFFINITY=false` restores
strict arrival order.

**Waiting, not refusing.** A busy gate does not return an error to a child in a classroom.
Callers wait up to `GPU_ADMISSION_ACQUIRE_TIMEOUT_S` (5400 s); only past
`GPU_ADMISSION_MAX_WAITERS` (40) does a caller get `GpuBusy`.

---

## Measured, never declared

`gpu_model_stats.py` records two things per `kind::model_id`, from observation only:

* **hold time** — an EMA (alpha = 0.3) over how long that key actually held the slot;
* **VRAM footprint** — how far free memory fell from its own peak during the run
  (`max_free_mb − min_free_mb`), sampled by the reaper every 5 s. Measuring from the peak
  rather than from the reading taken at admission matters because a run that has to load
  first **evicts** first, and eviction *raises* free memory — so the admission reading sits
  on the wrong side of it and would record the model minus whatever was thrown out for it.
  See the prefetch section: this is corrected, the other two under-measurements are not.

The high-water mark, not the average: the question a prefetch has to answer is whether the
model *fits*, and for that the worst observed moment is the honest number.

A value is **trusted** only after `TRUSTED_SAMPLES` (3) observations
(`vram_estimate_mb(trusted_only=True)`). Until then it is `None` and every decision that
depends on it declines. Nothing is read from a declared table — `MODEL_PEAK_VRAM_MB` and
`gpu_model_footprints.json` are deliberately **not** consulted here.

Hold times carry a second gate, because a mean can be well sampled and still describe
nothing: `wan2.2_t2v_high_noise_14B_fp8_scaled` ran 93 times between 10.8 s and 170.1 s, and
its EMA of 19.9 s is a duration no run of it had. So `record_hold` also keeps `hold_mad_s`,
an EMA of how far each run landed from what was expected, and `hold_estimate_s` answers
`None` whenever that deviation exceeds `SPREAD_LIMIT` (0.6) of the mean. The deviation and
not the largest run ever seen: one cold outlier should not silence a model permanently,
while a genuinely two-sided distribution should keep it quiet. Entries written before the
deviation was recorded fall back to a quarter of the observed range, which errs toward
silence and is replaced by the real figure on the next run.

### The two keys, and why neither alone was enough

**By output config, not by model.** One checkpoint serves several configs, and what a run
costs is a property of what is asked of the weights, not only of the weights. `Lease.workload`
carries the config from the DevServer; `Lease.stats_key` prefers it and falls back to the
model. `affinity_key` is untouched — reordering asks a different question ("what has to be on
the card") and keeps its own answer. A config with no record of its own reads the model's:
coarser, still measurement, still behind both gates. Without that fallback the re-key threw
away a hundred good samples per model and the platform went quiet about waits it had been
getting right.

**Cold and warm apart.** This, not the config, is what silenced video. Exactly ONE active
config uses the wan2.2 t2v checkpoint, at a fixed resolution, frame count and step count —
so the 16-fold range was never config mixing. It is the load: ComfyUI has no load lease at
all, because the checkpoint comes off disk inside the submitted workflow, so loading and
running sit in one reading. `Lease.was_resident` is recorded at admission, and a run that had
to load first is filed under `<kind>-cold`. Measured on this machine right after the split:
the same config, 132.1 s cold and 21.0 s warm.

The estimator then reads the bucket the run is actually heading for. A cold reading already
contains the load, so no surcharge is added to it; only where no cold reading exists does the
warm figure plus a separately measured load stand in — which is how the diffusers path has
always worked, since there the load is a lease of its own. The ComfyUI **preload** in the
settings surface takes its lease as `comfyui-load` for the same reason: it holds the card to
put weights on it, and as a run it dragged the run average toward "warming a model".

Runs that **failed** in the slot are not recorded at all — a run that died holding the card
held it for a length that says nothing about the model, and it is exactly the sort of short
reading that drags an average down.

The file is written outside the working tree
(`/var/tmp/ai4artsed/gpu_model_stats.json`, override `GPU_MODEL_STATS_PATH`) — it is
runtime measurement, not repository content.

---

## Speculative prefetch (warm-ahead) — BUILT, AND OFF

The one place where the "one at a time" rule would be deliberately relaxed: while a long
run holds the slot, the *next* model could already be pulled into the free part of the
card. `GPU_ADMISSION_PREFETCH` defaults to **false**, and it has to stay that way until
three things are settled — an adversarial review found each of them in the code and, for
the first, in the live measurement file:

1. **The measured footprint is a lower bound, not a size.** The free-VRAM reading is taken
   at admission, the low-water mark is sampled every few seconds and usually misses the
   peak, and a model that was already resident measures only its activations. The live file
   held 4802 MB — past the trust threshold — for a model whose measured peak is 30253 MiB.
   On a 32 GB card that arithmetic permits warming a 30 GB model into 16 GB of free memory.
2. **A ComfyUI warm is queued, not executed.** ComfyUI runs it minutes later, after the gate
   has already admitted somebody else against memory the warm had not taken yet.
3. **`get_queue_status()` answers `total=0` on any error**, including a timeout while
   ComfyUI streams weights off disk — so "the warm is finished" is reported while it is
   still loading, and the claim is released.

Everything else in this document runs without it. What follows describes the mechanism as
built, for whoever picks it up.

`prefetch_advice()` names a model only if **all** of the following hold:

* prefetch is enabled and nothing else is in flight;
* the next waiter's model differs from the resident one (a swap is really coming);
* its footprint is **trusted** (at least 3 measurements);
* `free − needed − GPU_ADMISSION_PREFETCH_HEADROOM_MB` (10 GB) is not negative;
* the running operation has at least `GPU_ADMISSION_PREFETCH_MIN_REMAINING_S` (45 s) left,
  by its own measured EMA.

`gpu_warm_ahead.py` (DevServer, background thread `gpu-warm-ahead`) polls the advice and
warms either ComfyUI (a tiny loader-only workflow) or diffusers
(`POST /api/diffusers/load {"prefetch": true}`). **The load route re-verifies the advice
server-side and answers 409 if it disagrees** — the gate never trusts the caller's claim
that there is room.

`_admit()` makes a new admission wait (bounded, 120 s) while a prefetch of a *different*
model is still in flight, so the two do not stack.

---

## Residency belief

The gate remembers which model it believes is on the card (`_last_key`) and uses that for
affinity and prefetch. That belief is **invalidated** (`forget_resident(why)`) whenever
something outside the gate frees VRAM — `_try_comfyui_eviction()` and
`emergency_reclaim_foreign()` both call it. A stale belief would otherwise make the gate
prefer a model that is no longer there.

**Known limitation, and it only ever over-states a wait.** `_last_key` is *what ran last*,
not *what is on the card*. The diffusers backend can hold several pipelines at once, so a
queued run whose weights are in fact resident — but which was not the last thing to run —
is charged the full load surcharge in the forecast (measured: +133 s for SD 3.5 Large). It
never under-states: a run is never promised a card sooner than it can have it. Fixing it
means asking the backend for its loaded pipelines, and until an eviction signal exists for
that set, believing a model resident that has been thrown out would be the worse error.

---

## Forecast

`plan()` replays the dequeue policy against **copies of the waiters, and lets the copies
age**: a simulated pick charges the waiters it passed with an overtake, and the simulated
clock advances by each run's expected hold. Both bounds keep accruing while a real queue
drains, so a frozen snapshot shows an order the gate will not honour — measured on a stub
harness: position 9 promised where the gate ran the same lease at 4, and in one case the run
shown last went first. `expected_start_in_s` comes from measured hold times; a load
surcharge is charged only when the model is not resident, and then at the **longest observed
load**, not the mean (a load whose model is already there returns at once and is recorded
too, which drags the mean far below any load that really happens).

**Unknown travels, and never becomes a zero.** A run that has outlived its estimate reports
`expected_remaining_s: null`, not `0` — telling a room "about to start" about a video that
was quoted 10 s and has been running for 200 is worse than saying the number is not known.
The same rule runs the length of the chain: an unknown remaining time on the running job
makes every `expected_start_in_s` behind it `null`; a queued run whose own model has no
usable measurement reports `expected_run_s: null` **and** blanks the start times of everyone
behind it, because the clock cannot be advanced past a duration nobody knows. The order is
still simulated across such a run — the platform-wide average moves the simulated clock so
the fairness bounds keep ageing — but that average never reaches a display.

`gate_reachable` distinguishes **"nothing is waiting"** from **"the card cannot be seen"**.
An unreachable gate used to arrive as an empty plan, and an empty plan reads as an idle
card: the status tab said FREE, and "Nothing is waiting for the card", while the service was
down and a room was stuck. `_gate_plan()` now returns `None` on any failure and every
consumer branches on it; `expected_wait_for_a_new_press_s` and `beyond_promise` become
`null` rather than `0.0` and `false`.

The DevServer asks the gate at most once every two seconds **and at most once at a time** —
a second caller arriving during a request takes the previous answer rather than opening
another connection to the service that is already the bottleneck. The call runs inside open
SSE streams, so its timeout is short by design (2 s connect, 3 s read): a gate that has not
answered in that long is not slow, and every second beyond it is a second of silence on
somebody's stream.

Both halves of the line a child reads come from the **same** queue. `position` used to be
the count of generations this DevServer had open minus one — a number that includes runs
nowhere near the card and the run holding it — while the time came from the gate's own
order, so the child at the front was told three were ahead. `_gate_place()` now derives both
from the plan, and falls back to the open-generation count only while the run has not
reached the gate, where it says nothing about time at all.

`GET /api/schema/pipeline/queue-forecast` (DevServer) merges that with runs that have not
yet reached the gate — a run in Prompt Interception is announced to the generation tracker
as `phase: "preparing"` the moment its stream starts, and becomes `"generating"` at stage 4.
**The per-device lock, the queue count and `/generation-active` still count only
`phase == "generating"`**, so nothing about the existing behaviour changes; the phase only
makes the pre-gate runs visible to the forecast.

`beyond_promise` marks entries whose predicted start lies past the acquire budget — three
states, not two: past it, inside it, or `null` where no prediction exists.

### What a person sees

Two displays consume this, and no third one may be added without consolidating (project
rule 13):

* **the run itself** — the queue line in `x2x_flow.vue` gains the time: "queue position: 23
  · about 7 min to go" in the band, and on the run panel's own figure line the short form
  ("~7 min") beside the position, because that box is 150 px wide and holds a number, not a
  sentence. The line is cleared the moment the card starts drawing this run and on every way
  a run can end — otherwise the last thing the gate said stands beside the finished picture.
* **Settings → Backend status → "Card queue"** — for the course leader: who holds the card
  with the time left, then the waiting runs in the order the gate will run them, each with
  its start time, and a mark on any run the affinity ordering has passed over. A dash means
  no measurement exists; it is never rendered as 0.

---

## HTTP surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/gate/lease/acquire` | take a remote lease (the GPU service, a script) |
| POST | `/api/gate/lease/heartbeat` | keep it alive |
| POST | `/api/gate/lease/release` | give it back |
| GET | `/api/gate/status` | holder and queue, raw |
| GET | `/api/gate/plan` | queue in the order it will run |
| GET | `/api/gate/stats` | measured hold times and footprints |
| GET | `/api/gate/prefetch-advice` | what may be warmed now |
| POST | `/api/gate/prefetch-claim` | claim the in-flight prefetch |
| POST | `/api/gate/prefetch-done` | release it |
| GET | `/api/gate/vram` | the card: memory, processes, ComfyUI's resident models |
| GET | `/api/schema/pipeline/queue-forecast` | merged, user-facing forecast |

---

## Configuration

All in `gpu_service/config.py`, all overridable by environment variable.

| Variable | Default | Meaning |
|---|---|---|
| `GPU_ADMISSION_ACQUIRE_TIMEOUT_S` | 5400 | how long a caller waits before giving up |
| `GPU_ADMISSION_MAX_WAITERS` | 40 | queue length past which `GpuBusy` is raised |
| `GPU_ADMISSION_MAX_HOLD_S` | 2400 | a wedged holder is released after this |
| `GPU_ADMISSION_HEARTBEAT_TIMEOUT_S` | 120 | remote lease without heartbeat is reaped |
| `GPU_ADMISSION_REAPER_INTERVAL_S` | 5 | reaper tick; also the footprint sampling rate |
| `GPU_ADMISSION_AFFINITY` | true | prefer a resident model over arrival order |
| `GPU_ADMISSION_MAX_OVERTAKES` | 3 | how often a waiter may be passed |
| `GPU_ADMISSION_AFFINITY_MAX_WAIT_S` | 300 | after this, arrival order wins outright |
| `GPU_ADMISSION_POST_LOAD_RESERVE_S` | 5 | a load reserves the slot for its own run |
| `GPU_ADMISSION_PREFETCH` | **false** | speculative warm-ahead — see the section above before enabling |
| `GPU_ADMISSION_PREFETCH_HEADROOM_MB` | 10240 | spare VRAM required to warm ahead |
| `GPU_ADMISSION_PREFETCH_MIN_REMAINING_S` | 45 | minimum remaining run time to warm ahead |
| `GPU_ADMISSION_BLIND_SAMPLES` | 3 | consecutive failed sensor reads before degrading |

---

## Aborted runs do not enter the statistics

A run that ends early holds the slot for a time no completed run has — milliseconds when
it was cancelled in the queue, half a render when it was interrupted. Recorded as valid,
such holds drag the EMA toward zero and blow the deviation past the spread gate: the
statistics the measurement exists to build are poisoned by the aborts it will always see.

What keeps them out:

* **Local leases** (`slot()`): a body that raises marks the lease `failed` — unchanged.
* **Remote leases**: the release call now carries `failed` (`POST /api/gate/lease/release`,
  body `{"token": ..., "failed": true}`), and both DevServer lease managers set it for ANY
  exception that ends the leased body — an abort raised into it, a cancelled task, a crash.
  An old client that never sends the key behaves exactly as before.
* **Interrupts raise.** ComfyUI answers an interrupt with `execution_interrupted` and then
  ends the job like a finished one (`executing: node=None`) — without a dedicated branch
  the tracking loop reports a cancelled render as a completed run. The branch raises, the
  raise reaches the release, the release says `failed`.
* **A failed warmup is not a completed load.** The settings preload exits its lease with a
  synthetic exception when the warmup did not complete — on BOTH exits: the main path, and
  the grant that lands after the dialog already died (which used to record a queue-to-grant
  millisecond as a valid load sample and arm the post-load reservation for a model that was
  never warmed).
* **A lease refused at admission never ran.** `acquire_remote` flags the lease failed
  before releasing it when `_admit` raises — without that, an admission refusal after the
  `admitted_at` stamp recorded its near-zero age as a valid hold.
* **A load that fails by returning False is marked, not trusted.** The diffusers and the
  in-process LLM load bodies report failure with a return value, which the slot never sees
  as an exception — so they mark the lease themselves (the child engine raises instead, and
  is marked on the way out; see *The `llm-load` lease*) (`slot()` yields it; the reentrant and
  prefetch paths yield None and are guarded). Unmarked, a failed diffusers load claimed
  residency for the pipeline its own cleanup had just deleted — the next run was priced
  warm and WITHOUT a load surcharge, an under-stated wait — filed its partial allocation
  as the model footprint, armed the post-load reservation for a phantom, and poisoned the
  load bucket that every config on that checkpoint reads as its cold surcharge.
* **A failed lease neither claims residency it cannot know, nor files a footprint, nor
  feeds the ordering EMA.** A failed run that had to LOAD leaves `_last_key = None`
  ("unknown") — claiming residency priced the same-model retry with the warm figure while
  the card had to load, the one direction the forecast promised never to err in. A failed
  run whose model was ALREADY resident keeps the residency — its failure unloads nothing,
  and answering "unknown" there sent the next same-model run into the cold bucket with a
  warm success (two of those and the spread gate silences the config). The VRAM footprint
  of a failed run (a partial allocation) stays out of the memory records, and the
  platform-wide ordering EMA no longer absorbs aborted holds — a handful of closed tabs
  multiplied it toward its 10 s floor and distorted the simulated order.

The one direction that remains loses data, never invents it: a run whose abort lands a
breath after its completion is flagged failed and drops one valid sample.

**Known gap (bounded, deliberate) — failures the flag still does not see:** the failed
flag rides on exceptions or on a body marking the lease `slot()` hands it; what remains
are callers that do neither. The members, named completely after four review rounds
(the legacy workflow surface `workflow_streaming_routes.py`, which was one of them, was
removed on 2026-10-10): the HeartMuLa output-file check, which detects failure only after
`run_admitted` has already exited; and the `@gated` views (seven views —
stable_audio 2, mmaudio 1, hunyuan3d 1, cross_aesthetic 3 — with eighteen unmarked
return sites; hunyuan3d additionally converts exceptions into 500-returns inside the
slot, and the decorator does not expose the lease to the view). Their HOLDS and
footprints stay in their own buckets (the slots carry neither workload nor a shared
checkpoint key), read only when a run of that same surface sits in the queue — but an
unmarked failure still writes two pieces of SHARED state: the platform ordering EMA
absorbs the aborted hold, and the residency belief is overwritten with the failed
surface's key. A stable_audio parameter-400 that never touched the card leaves
"stable_audio" as what-ran-last while SD3.5 is in fact resident — the next SD3.5 run is
then priced cold and records its warm success into SD3.5's COLD bucket, the two-sample
spread-gate poisoning described above. The gap members' damage crosses surfaces through
the residency belief and the ordering clock, not through their buckets. Deliberately
left the evening before a measurement night; the work order is in
docs/devserver_todos.md.

With that, a failed lease writes nothing at all: no hold, no footprint, no residency
claim beyond what was already known, no EMA sample.

---

## Deployment note — cards below the Blackwell specification

The gate serialises; it does not guarantee a fit. **HeartMuLa is the one caller that checks
a real number: it demands 16 GB free VRAM and refuses rather than waits.** On the current
specification (RTX 5090 and above) that is unremarkable. On a **deprecated RTX 4090 (24 GB)**
it is the first thing that will fail in a mixed workshop: a resident SD3.5 or a video model
leaves less than 16 GB, and music generation is refused while everything else still works.
The gate cannot repair this — the card is too small for the combination, and the honest fix
is the eviction the gate already performs, or a bigger card.

---

## What this is not

* **Not a scheduler for fairness between users.** The bounds prevent starvation; they do
  not implement per-user quotas.
* **Not a memory accountant.** It does not sum model sizes and it cannot prevent an OOM
  caused by a single operation that is too big for the card on its own.
* **Not a replacement for the VRAM coordinator.** `vram_coordinator.py` still does
  cross-backend eviction; the gate decides *when* someone may ask it to.

---

## Related

* Part 27 — VRAM Management & GPU Model Cache
* Part 31 — GPU Service
* Part 34 — Generation Tracker
* Part 24 — ComfyUI Integration
