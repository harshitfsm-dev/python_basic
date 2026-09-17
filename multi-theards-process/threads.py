"""
Python concurrency, end to end
==============================

Three things are demonstrated here, in order:

  1. Threading primitives  - Semaphore, Lock, RLock, Event, Condition, Barrier,
                             thread-local storage, ThreadPoolExecutor, daemons.
  2. The GIL, before/after  - the same benchmarks run on a normal build and on a
                             free-threaded build produce very different numbers.
  3. asyncio vs threads     - where each model wins, and how they interoperate.

Run everything:
    python theards/threads.py

Run one or more sections (names come from the DEMOS registry at the bottom):
    python theards/threads.py gil_cpu gil_io asyncio_vs_threads

The interesting experiment is running the *same* file on both builds:
    python3.14   theards/threads.py gil_cpu gil_races   # GIL enabled
    python3.14t  theards/threads.py gil_cpu gil_races   # free-threaded
    (uv python install 3.14t  installs the second one)

Measured on an M-series Mac, 12 logical cores (6 performance), by running this
file on both builds:

    section         metric                        3.14 (GIL)   3.14t (no GIL)
    -------------   ---------------------------   ----------   --------------
    gil_cpu         4 threads vs serial                0.98x            3.97x
    gil_cpu         4 processes vs serial              2.49x            2.86x
    gil_io          8 threads on blocking I/O          7.98x            7.94x
    gil_races       lost updates, tight loop               0          582,626
    asyncio_scale   RSS for 5,000 threads          +  168 MB        + 1412 MB
    asyncio_scale   RSS for 5,000 coroutines       +    7 MB        +    8 MB

Three things to read off that table:

  * CPU-bound threading goes from pointless to genuinely parallel, and on 3.14t
    it beats multiprocessing, because there is no pickling or spawn cost.
  * I/O-bound threading is unchanged. The GIL was never the problem there.
  * The race that the GIL silently absorbed for decades shows up on the first
    run. Nothing got less correct; the code just stopped getting away with it.

Also note the last two rows: a free-threaded thread costs roughly 8x the memory
of a GIL-build thread here, while coroutines cost the same on both. Free
threading makes threads parallel, not cheap.

Background on the "before / after" framing:
  * Before: CPython has always had a Global Interpreter Lock. One thread runs
    Python bytecode at a time. The lock is handed off every `sys.getswitchinterval()`
    seconds (5 ms by default) and is released around blocking I/O and many C calls.
  * After: PEP 703 added a free-threaded build (`python3.13t`), and PEP 779 promoted
    it from experimental to officially supported in Python 3.14. It is a separate
    build, not the default. With the GIL gone, threads execute bytecode in parallel.
    Costs: more memory (up to ~20% higher on the pyperformance geometric mean) and
    races that the GIL used to hide are now easy to hit.
"""

import asyncio
import queue
import resource
import sys
import sysconfig
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


# ---------------------------------------------------------------------------
# Small helpers used by every section
# ---------------------------------------------------------------------------


def banner(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


class timed:
    """Context manager that prints and records a wall-clock duration."""

    def __init__(self, label):
        self.label = label
        self.elapsed = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info):
        self.elapsed = time.perf_counter() - self._start
        print(f"  {self.label:<44} {self.elapsed:6.2f}s")
        return False


def me():
    """Current thread name, for readable interleaved logs."""
    return threading.current_thread().name


# ===========================================================================
# PART 1 - THREADING PRIMITIVES
# ===========================================================================


def demo_semaphore():
    """Semaphore = a counter. Caps how many threads are inside a section."""
    banner("1a. Semaphore - bound concurrency to N slots")

    connection_pool = threading.Semaphore(value=2)

    def access_api_service():
        print(f"  {me()} waiting for a free slot...")
        # Blocks here while both slots are taken.
        with connection_pool:
            print(f"  {me()} CONNECTED, processing.")
            time.sleep(0.6)  # stand-in for a network call
            print(f"  {me()} done, releasing slot.")

    workers = [
        threading.Thread(target=access_api_service, name=f"Worker-{i + 1}")
        for i in range(5)
    ]
    for t in workers:
        t.start()
    for t in workers:
        t.join()

    print("  5 workers shared 2 slots -> ~3 waves instead of 1.")


def demo_lock():
    """Lock (mutex) = mutual exclusion. Exactly one thread inside at a time."""
    banner("1b. Lock - serialise access to shared state")

    counter = 0
    counter_lock = threading.Lock()

    def increment():
        nonlocal counter
        # `with` acquires and always releases, even if the body raises.
        with counter_lock:
            print(f"  {me()} acquired the lock.")
            current = counter
            time.sleep(0.1)  # widen the read-modify-write window on purpose
            counter = current + 1
            print(f"  {me()} set counter={counter}, releasing.")

    workers = [
        threading.Thread(target=increment, name=f"Thread-{i + 1}") for i in range(3)
    ]
    for t in workers:
        t.start()
    for t in workers:
        t.join()

    print(f"  Final counter: {counter} (expected 3)")


def demo_rlock():
    """RLock = re-entrant. Same thread may acquire it repeatedly; Lock deadlocks."""
    banner("1c. RLock - re-entrant lock for recursive / nested code")

    lock = threading.RLock()
    depth = 0

    def walk(n):
        nonlocal depth
        with lock:  # re-acquired on every recursive call
            depth = max(depth, n)
            print(f"  {me()} holds the RLock {n} time(s) deep.")
            if n < 3:
                walk(n + 1)

    t = threading.Thread(target=walk, args=(1,), name="Recursive")
    t.start()
    t.join()
    print(
        f"  Reached depth {depth}. A plain threading.Lock() would have deadlocked here."
    )


def demo_event():
    """Event = one-bit broadcast flag. Many waiters wake on a single set()."""
    banner("1d. Event - broadcast a state change to many threads")

    config_ready = threading.Event()
    shutdown = threading.Event()

    def consumer():
        print(f"  {me()} blocked until config is ready.")
        config_ready.wait()
        print(f"  {me()} unblocked, doing work.")
        # wait() with a timeout returns True if set, False on timeout: a
        # cancellable sleep, which is how you build cooperative shutdown.
        while not shutdown.wait(timeout=0.15):
            pass
        print(f"  {me()} saw shutdown, exiting cleanly.")

    consumers = [
        threading.Thread(target=consumer, name=f"Consumer-{i + 1}") for i in range(3)
    ]
    for t in consumers:
        t.start()

    time.sleep(0.4)
    print("  main: config loaded -> set()")
    config_ready.set()  # all three wake from one call
    time.sleep(0.4)
    print("  main: asking everyone to stop")
    shutdown.set()
    for t in consumers:
        t.join()


def demo_condition_and_queue():
    """Condition = lock + wait/notify. queue.Queue is the version you should use."""
    banner("1e. Condition vs queue.Queue - producer / consumer")

    # --- hand-rolled with a Condition (educational) ---
    buffer = []
    cond = threading.Condition()
    MAX = 3
    DONE = object()

    def producer():
        for i in range(6):
            with cond:
                # Always re-check the predicate in a loop: wait() can return
                # spuriously, and another thread may win the race after notify.
                while len(buffer) >= MAX:
                    cond.wait()
                buffer.append(i)
                print(f"  producer put {i} (buffer={len(buffer)})")
                cond.notify_all()
            time.sleep(0.05)
        with cond:
            buffer.append(DONE)
            cond.notify_all()

    def consumer():
        while True:
            with cond:
                while not buffer:
                    cond.wait()
                item = buffer.pop(0)
                cond.notify_all()
            if item is DONE:
                print("  consumer saw sentinel, stopping.")
                return
            print(f"    consumer got {item}")
            time.sleep(0.12)

    p = threading.Thread(target=producer, name="Producer")
    c = threading.Thread(target=consumer, name="Consumer")
    p.start()
    c.start()
    p.join()
    c.join()

    # --- the same thing with queue.Queue: locking is built in ---
    print("\n  Same pipeline with queue.Queue (no manual locking):")
    q = queue.Queue(maxsize=3)

    def q_producer():
        for i in range(6):
            q.put(i)  # blocks when full
        q.put(None)  # sentinel

    def q_consumer():
        while (item := q.get()) is not None:
            print(f"    queue consumer got {item}")
            q.task_done()
        q.task_done()

    tp = threading.Thread(target=q_producer)
    tc = threading.Thread(target=q_consumer)
    tp.start()
    tc.start()
    tp.join()
    tc.join()
    print("  queue.Queue is the default answer for thread-to-thread handoff.")


def demo_barrier():
    """Barrier = rendezvous. Nobody proceeds until N threads have arrived."""
    banner("1f. Barrier - synchronise threads in phases")

    N = 4
    barrier = threading.Barrier(N)

    def phased_worker(delay):
        for phase in (1, 2):
            time.sleep(delay * phase)
            print(f"  {me()} finished phase {phase}, waiting at barrier.")
            index = barrier.wait()
            if index == 0:  # exactly one thread gets 0: use it as the leader
                print(f"  -- all threads cleared phase {phase} --")

    workers = [
        threading.Thread(target=phased_worker, args=(0.1 * (i + 1),), name=f"P{i + 1}")
        for i in range(N)
    ]
    for t in workers:
        t.start()
    for t in workers:
        t.join()


def demo_thread_local():
    """threading.local() = per-thread storage. Avoids sharing, so no lock needed."""
    banner("1g. threading.local - per-thread state instead of shared state")

    ctx = threading.local()

    def handle_request(request_id):
        ctx.request_id = request_id  # invisible to every other thread
        ctx.started = time.perf_counter()
        time.sleep(0.1)
        print(f"  {me()} handled request {ctx.request_id}")

    workers = [
        threading.Thread(target=handle_request, args=(f"req-{i}",), name=f"Handler-{i}")
        for i in range(4)
    ]
    for t in workers:
        t.start()
    for t in workers:
        t.join()

    print(f"  main thread has its own (empty) ctx: {hasattr(ctx, 'request_id')=}")
    print("  This is how frameworks carry request context without global locks.")


def demo_pool_and_daemon():
    """ThreadPoolExecutor for results/exceptions; daemon threads for fire-and-forget."""
    banner("1h. ThreadPoolExecutor and daemon threads")

    def fetch(url):
        time.sleep(0.2)
        if "bad" in url:
            raise ValueError(f"cannot reach {url}")
        return f"200 OK {url}"

    urls = ["/users", "/orders", "/bad-endpoint", "/health"]
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="pool") as pool:
        futures = {pool.submit(fetch, u): u for u in urls}
        for future, url in futures.items():
            try:
                print(f"  {url:<14} -> {future.result()}")
            except ValueError as exc:
                # Exceptions are captured in the Future, not lost like in a
                # bare Thread where they only print to stderr.
                print(f"  {url:<14} -> FAILED: {exc}")

    def heartbeat():
        while True:
            time.sleep(0.15)

    hb = threading.Thread(target=heartbeat, name="Heartbeat", daemon=True)
    hb.start()
    print(f"  {hb.name} is a daemon: the process will not wait for it to finish.")
    print("  Daemons are killed abruptly at exit - never use them to write files.")


# ===========================================================================
# PART 2 - THE GIL: BEFORE vs AFTER
# ===========================================================================


def gil_enabled():
    """True if this interpreter is currently running with the GIL."""
    if hasattr(sys, "_is_gil_enabled"):
        return sys._is_gil_enabled()
    return True  # anything older than 3.13 always has it


def free_threaded_build():
    """True if this is a free-threaded (PEP 703 / 779) build."""
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def demo_gil_introspect():
    banner("2a. Which interpreter am I actually running?")
    print(f"  Version              : {sys.version.split()[0]}")
    print(f"  Free-threaded build  : {free_threaded_build()}")
    print(f"  GIL enabled right now: {gil_enabled()}")
    print(f"  Switch interval      : {sys.getswitchinterval() * 1000:.1f} ms")
    print(f"  Active threads       : {threading.active_count()}")

    if free_threaded_build():
        print("\n  -> 'AFTER' the GIL. Threads run bytecode on separate cores.")
        print("     A free-threaded build can still re-enable the GIL at startup")
        print("     (PYTHON_GIL=1 / -X gil=1) when a C extension demands it.")
    else:
        print("\n  -> 'BEFORE' the GIL removal. This is the standard build.")
        print("     Install the other one to compare:  uv python install 3.14t")


def cpu_burn(n):
    """Pure-Python CPU work: no I/O, no C library that releases the GIL."""
    total = 0
    for i in range(n):
        total += i * i
    return total


def demo_gil_cpu():
    """The headline difference: CPU-bound scaling."""
    banner("2b. CPU-bound: threads vs processes (this is what the GIL decides)")

    WORK = 15_000_000
    TASKS = 4

    with timed("serial (1 core)") as serial:
        for _ in range(TASKS):
            cpu_burn(WORK)

    with timed(f"{TASKS} threads") as threaded:
        workers = [
            threading.Thread(target=cpu_burn, args=(WORK,)) for _ in range(TASKS)
        ]
        for t in workers:
            t.start()
        for t in workers:
            t.join()

    with timed(f"{TASKS} processes") as procs:
        with ProcessPoolExecutor(max_workers=TASKS) as pool:
            list(pool.map(cpu_burn, [WORK] * TASKS))

    print(f"\n  thread speedup vs serial : {serial.elapsed / threaded.elapsed:.2f}x")
    print(f"  process speedup vs serial: {serial.elapsed / procs.elapsed:.2f}x")

    if gil_enabled():
        print("\n  BEFORE: ~1.0x for threads. Only one thread holds the GIL, so the")
        print("  work is serialised and you also pay for context switching. This is")
        print("  why CPU-bound Python has always meant multiprocessing.")
    else:
        print("\n  AFTER: threads now approach the process speedup, without pickling")
        print("  arguments, without spawn cost, and sharing memory directly.")


def demo_gil_io():
    """I/O-bound work was always fine, because blocking calls release the GIL."""
    banner("2c. I/O-bound: the GIL was never the bottleneck here")

    def blocking_io(seconds=0.5):
        time.sleep(seconds)  # releases the GIL while sleeping

    TASKS = 8

    with timed(f"serial ({TASKS} x 0.5s waits)") as serial:
        for _ in range(TASKS):
            blocking_io()

    with timed(f"{TASKS} threads") as threaded:
        workers = [threading.Thread(target=blocking_io) for _ in range(TASKS)]
        for t in workers:
            t.start()
        for t in workers:
            t.join()

    print(
        f"\n  speedup: {serial.elapsed / threaded.elapsed:.2f}x (near {TASKS}x on both builds)"
    )
    print("  A thread waiting on a socket, a file, or a subprocess holds no GIL.")
    print("  Same for numpy / hashlib / zlib, which drop it around heavy C loops.")


RACE_COUNTER = 0


def _passthrough(x):
    """A trivial Python call. Entering a Python frame IS a GIL checkpoint."""
    return x


def _race(iterations, variant):
    """Read-modify-write a global with no lock. Broken by construction."""
    global RACE_COUNTER
    for _ in range(iterations):
        if variant == "tight":
            # Straight-line LOAD_GLOBAL / STORE_GLOBAL, nothing in between.
            current = RACE_COUNTER
            RACE_COUNTER = current + 1
        elif variant == "call":
            # A Python call now sits between the read and the write.
            current = RACE_COUNTER
            RACE_COUNTER = _passthrough(current) + 1
        else:  # "release"
            # time.sleep(0) explicitly drops the GIL inside the window.
            current = RACE_COUNTER
            time.sleep(0)
            RACE_COUNTER = current + 1


def demo_gil_hidden_races():
    """Why "it works on my machine" is not the same as "it is thread-safe"."""
    banner("2d. Races the GIL used to hide")

    global RACE_COUNTER
    THREADS = 4

    def measure(label, variant, iterations, switch_interval=None):
        global RACE_COUNTER
        RACE_COUNTER = 0
        gate = threading.Barrier(THREADS)  # force the threads to truly overlap

        def worker():
            gate.wait()
            _race(iterations, variant)

        original = sys.getswitchinterval()
        if switch_interval:
            sys.setswitchinterval(switch_interval)
        try:
            workers = [threading.Thread(target=worker) for _ in range(THREADS)]
            for t in workers:
                t.start()
            for t in workers:
                t.join()
        finally:
            sys.setswitchinterval(original)

        expected = iterations * THREADS
        print(f"  {label:<40} lost {expected - RACE_COUNTER:>8,} of {expected:,}")

    print("  Unsynchronised `counter = counter + 1` on 4 threads:\n")
    measure("tight loop, default 5 ms switching", "tight", 200_000)
    measure("tight loop, forced 1 us switching", "tight", 200_000, 1e-6)
    measure("Python call in the window, 1 us", "call", 200_000, 1e-6)
    measure("time.sleep(0) in the window", "release", 20_000)

    if gil_enabled():
        print("\n  Note the first two rows: zero lost updates. That is the trap.")
        print("  CPython only considers handing off the GIL at a few points - loop")
        print("  back-edges and Python frame entry - never between the LOAD_GLOBAL")
        print("  and STORE_GLOBAL of one straight-line statement. So the tight loop")
        print("  is *accidentally* atomic, and the bug is invisible. Add a single")
        print("  function call and the very same code starts shredding updates.")
        print("\n  Run this section again under a free-threaded build: the tight loop")
        print("  loses hundreds of thousands of updates, because there is no handoff")
        print("  point when there is no handoff.")
    else:
        print("\n  Every row loses updates, including the tight loop. There is no GIL")
        print("  to hand off, so the read and the write of two threads genuinely")
        print("  interleave. On a standard build the first two rows report zero,")
        print("  because CPython only considers a handoff at loop back-edges and at")
        print("  Python frame entry, never inside a straight-line statement - which")
        print("  made this bug *accidentally* invisible for decades.")
        print("\n  This is the real migration risk of free threading. The code did")
        print("  not get less correct; it stopped getting away with it.")

    # The fix is identical on both builds.
    RACE_COUNTER = 0
    lock = threading.Lock()

    def safe_increment(iterations):
        global RACE_COUNTER
        for _ in range(iterations):
            with lock:
                RACE_COUNTER += 1

    workers = [
        threading.Thread(target=safe_increment, args=(200_000,)) for _ in range(THREADS)
    ]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    print(
        f"\n  With a Lock: {RACE_COUNTER:,} of {200_000 * THREADS:,}, on every build."
    )

    print("\n  Single operations on built-in containers stay internally consistent,")
    print("  but compound ones never were atomic:")
    print(
        "    d[k] = d[k] + 1     lst.append(lst[-1] * 2)     if k not in d: d[k] = []"
    )
    print("  Fix: a Lock, a queue.Queue, itertools.count, or thread-local state.")


# ===========================================================================
# PART 3 - THREADS vs ASYNCIO
# ===========================================================================


def demo_asyncio_vs_threads():
    banner("3a. Same I/O workload: threads vs asyncio")

    REQUESTS = 20
    LATENCY = 0.25

    def sync_call(i):
        time.sleep(LATENCY)
        return i

    with timed(f"threads   ({REQUESTS} requests)") as threaded:
        with ThreadPoolExecutor(max_workers=REQUESTS) as pool:
            list(pool.map(sync_call, range(REQUESTS)))

    async def async_call(i):
        await asyncio.sleep(LATENCY)
        return i

    async def gather_all():
        return await asyncio.gather(*(async_call(i) for i in range(REQUESTS)))

    with timed(f"asyncio   ({REQUESTS} requests)") as evented:
        asyncio.run(gather_all())

    print(
        f"\n  Wall clock is nearly identical ({threaded.elapsed:.2f}s vs "
        f"{evented.elapsed:.2f}s)."
    )
    print("  The difference is not speed, it is the concurrency model:")
    print("    threads  - OS preempts anywhere; every shared mutation needs a lock")
    print("    asyncio  - switches only at `await`; between awaits you are atomic")


def _peak_rss_mb():
    """Process high-water-mark RSS. ru_maxrss is bytes on macOS, KiB on Linux."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def demo_asyncio_scale():
    """Wall clock is a tie here. Memory is not."""
    banner("3b. Scale: 5,000 coroutines vs 5,000 OS threads")

    N = 5_000
    WAIT = 0.5

    baseline = _peak_rss_mb()
    print(f"  baseline peak RSS: {baseline:>6.0f} MB\n")

    async def idle():
        await asyncio.sleep(WAIT)

    async def spawn_many():
        await asyncio.gather(*(idle() for _ in range(N)))

    with timed(f"{N:,} asyncio tasks, all waiting {WAIT}s"):
        asyncio.run(spawn_many())
    after_tasks = _peak_rss_mb()
    print(
        f"  peak RSS now:      {after_tasks:>6.0f} MB "
        f"(+{after_tasks - baseline:.0f} MB for {N:,} coroutines)"
    )

    def idle_thread():
        time.sleep(WAIT)

    # 5,000 live OS threads is genuinely near the edge. It works on a typical
    # macOS/Linux box but can hit RLIMIT_NPROC or the per-process thread cap,
    # so the failure is caught and reported rather than crashing the demo.
    print()
    try:
        with timed(f"{N:,} OS threads, all waiting {WAIT}s"):
            workers = [threading.Thread(target=idle_thread) for _ in range(N)]
            for t in workers:
                t.start()
            for t in workers:
                t.join()
    except RuntimeError as exc:
        print(f"  could not start {N:,} threads: {exc}")
        print("  ...which is itself the point of this section.")
        return

    after_threads = _peak_rss_mb()
    print(
        f"  peak RSS now:      {after_threads:>6.0f} MB "
        f"(+{after_threads - after_tasks:.0f} MB for {N:,} threads)"
    )

    print("\n  Both finish in about the same wall clock, because both are just")
    print("  waiting. The cost shows up in memory: a coroutine is a heap object of")
    print("  a few hundred bytes, while every thread gets its own stack from the")
    print("  kernel plus an entry in the OS scheduler.")
    print("\n  That ratio is why high-concurrency network servers are written on")
    print("  event loops, and free threading does not change it: removing the GIL")
    print("  makes threads parallel, it does not make them cheap.")


def demo_asyncio_blocking_pitfall():
    banner("3c. asyncio's sharp edge: one blocking call stalls everything")

    ticks = 0

    async def heartbeat(stop):
        # A background task that should tick every 50 ms for as long as the
        # loop is healthy. 0.5s of work should let it tick about 10 times.
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.05)

    async def run(label, work):
        nonlocal ticks
        ticks = 0
        stop = asyncio.Event()
        hb = asyncio.create_task(heartbeat(stop))
        await asyncio.sleep(0)  # let the heartbeat actually start
        await work()
        stop.set()
        await hb
        print(f"  {label:<44} heartbeat ticked {ticks:>2}x")

    async def blocking():
        # WRONG inside a coroutine: nothing else on the loop can run.
        time.sleep(0.5)

    async def offloaded():
        # Hands the blocking call to a worker thread and gives control back to
        # the loop. asyncio.to_thread is the modern spelling of
        # loop.run_in_executor(None, ...).
        await asyncio.to_thread(time.sleep, 0.5)

    asyncio.run(run("time.sleep(0.5) inside the coroutine", blocking))
    asyncio.run(run("asyncio.to_thread(time.sleep, 0.5)", offloaded))

    print("\n  Both did 0.5s of the same work. The first froze the entire event")
    print("  loop; the second kept it responsive. asyncio is cooperative, so one")
    print("  uncooperative call takes down every task in the process.")
    print("\n  Rules of thumb:")
    print("    blocking I/O or a C library call -> asyncio.to_thread(...)")
    print("    CPU-bound work                   -> ProcessPoolExecutor, or threads")
    print("                                        on a free-threaded build")
    print("    calling async code from a thread  -> asyncio.run_coroutine_threadsafe")


def demo_summary():
    banner("Summary")

    build = "free-threaded (GIL off)" if not gil_enabled() else "standard (GIL on)"
    print(f"  Running on: Python {sys.version.split()[0]}, {build}\n")

    rows = [
        (
            "Workload",
            "threading (GIL)",
            "threading (no GIL)",
            "asyncio",
            "multiprocessing",
        ),
        ("-" * 17, "-" * 15, "-" * 17, "-" * 15, "-" * 15),
        ("CPU-bound", "no gain", "scales with cores", "no gain", "scales"),
        ("Blocking I/O", "scales", "scales", "needs to_thread", "works, wasteful"),
        ("Async I/O", "OK, heavy", "OK, heavy", "best fit", "overkill"),
        (
            "10k concurrent",
            "works, ~350 MB",
            "works, ~2.8 GB",
            "routine, ~15 MB",
            "impossible",
        ),
        (
            "Shared state",
            "locks needed",
            "locks required",
            "safe at awaits",
            "IPC / pickling",
        ),
        ("Switch points", "anywhere", "anywhere", "only at await", "n/a"),
    ]
    for row in rows:
        print(f"  {row[0]:<18} {row[1]:<16} {row[2]:<18} {row[3]:<16} {row[4]}")

    print("\n  Picking a model:")
    print("    many slow network calls, async libraries available -> asyncio")
    print("    blocking SDKs, moderate fan-out, shared memory     -> threads")
    print("    heavy pure-Python computation, standard build      -> processes")
    print("    heavy pure-Python computation, 3.14t build         -> threads, finally")
    print("\n  Migration note: the free-threaded build needs C extensions compiled")
    print("  against it. Check status per package before committing to it.")


# ===========================================================================
# RUNNER
# ===========================================================================

DEMOS = {
    # Part 1 - primitives
    "semaphore": demo_semaphore,
    "lock": demo_lock,
    "rlock": demo_rlock,
    "event": demo_event,
    "condition": demo_condition_and_queue,
    "barrier": demo_barrier,
    "local": demo_thread_local,
    "pool": demo_pool_and_daemon,
    # Part 2 - the GIL
    "gil_introspect": demo_gil_introspect,
    "gil_cpu": demo_gil_cpu,
    "gil_io": demo_gil_io,
    "gil_races": demo_gil_hidden_races,
    # Part 3 - asyncio
    "asyncio_vs_threads": demo_asyncio_vs_threads,
    "asyncio_scale": demo_asyncio_scale,
    "asyncio_blocking": demo_asyncio_blocking_pitfall,
    # Wrap-up
    "summary": demo_summary,
}


def main(argv):
    requested = argv[1:] or list(DEMOS)

    unknown = [name for name in requested if name not in DEMOS]
    if unknown:
        print(f"Unknown demo(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(DEMOS)}")
        return 1

    for name in requested:
        DEMOS[name]()
    return 0


# ProcessPoolExecutor uses the 'spawn' start method on macOS, which re-imports
# this module in the child. Everything above lives in a function, and the entry
# point is guarded, so the child imports cleanly instead of re-running demos.
if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
