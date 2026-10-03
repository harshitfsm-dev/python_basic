"""
multiprocessing, end to end
===========================

Companion to threads.py. Same layout, same runner, different tool.

The one-line summary: threads share memory and fight over the GIL, processes
each get their own interpreter and their own memory, so they get real CPU
parallelism but have to *copy* everything they want to share.

  1. Process basics   - start/join, and the fact that memory is NOT shared.
  2. Talking          - Queue, Pipe, Value/Array, Manager.
  3. Pools            - Pool and ProcessPoolExecutor, errors, the cost of data.
  4. Start methods    - spawn vs fork vs forkserver, and what changed in 3.14.
  5. Comparison       - serial vs threads vs processes vs asyncio, measured.

Run everything (about 20 seconds):
    python multi-theards-process/process.py

Run one or more sections:
    python multi-theards-process/process.py isolation showdown summary

Measured on an M-series Mac, 12 logical cores, Python 3.14, spawn:

    same 4 x 15M-iteration CPU loop      serial   threads  processes  asyncio
    ---------------------------------    ------   -------  ---------  -------
    speedup vs serial                     1.00x     0.97x      2.77x    0.94x

    same 8 x 0.5s blocking waits         serial   threads  processes  asyncio
    ---------------------------------    ------   -------  ---------  -------
    speedup vs serial                     1.00x     7.97x      5.52x    8.03x

    cost of one unit of concurrency       thread   process (spawn / fork)   coroutine
    ----------------------------------    ------   ----------------------   ---------
    start + join                           37 us     106 ms  /   1.8 ms       2.5 us

So: processes are the only option that makes pure-Python CPU work faster on a
standard build, and they are ~2800x more expensive to create than a thread.
Both facts drive every design decision in this file.

The catch that surprises people is section 3c: handing a process a big list can
easily be 20x SLOWER than not parallelising at all, because the data has to be
pickled and piped. Processes pay off when compute per byte transferred is high.

Two rules that make everything here work, and cause most beginner bugs:

  * Worker functions must live at module level. Child processes rebuild them by
    importing this module and looking the name up, so lambdas, closures and
    nested functions cannot be sent. That is why every worker below is a
    top-level `def` with a `_worker`-ish name instead of being defined inline.
  * Everything that runs must sit behind `if __name__ == "__main__"`. With the
    spawn start method the child re-imports this file, and unguarded top-level
    code would run again in every child, forever.
"""

import asyncio
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


# ---------------------------------------------------------------------------
# Small helpers (same as threads.py)
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


# ===========================================================================
# WORKERS
# Every function a child process runs must be importable by name, so they all
# live here at module level rather than inside the demos that use them.
# ===========================================================================

# A module-level global. Section 1b uses it to show what children inherit.
SHARED_GLOBAL = 0


def w_greet(label):
    """Prints from inside the child, to show it is a separate process."""
    print(f"  {label}: pid={os.getpid()}, parent={os.getppid()}")
    time.sleep(0.2)


def w_report_global(queue):
    """Reports the value of SHARED_GLOBAL as seen by the child."""
    queue.put((mp.current_process().name, SHARED_GLOBAL, os.getpid()))


def w_mutate_global():
    """Mutates the child's own copy. The parent will not see it."""
    global SHARED_GLOBAL
    SHARED_GLOBAL = 999


def w_crash():
    """Raises, so we can look at exitcode."""
    raise ValueError("something went wrong in the child")


def w_forever():
    """Never returns; used to demonstrate terminate()."""
    while True:
        time.sleep(0.1)


def w_producer(queue, count):
    for i in range(count):
        queue.put(f"item-{i}")
        time.sleep(0.05)
    queue.put(None)  # sentinel: tells the consumer to stop


def w_consumer(queue):
    while (item := queue.get()) is not None:
        print(f"    consumer (pid {os.getpid()}) got {item}")


def w_pipe_child(conn):
    """Talks back and forth over one end of a Pipe."""
    request = conn.recv()
    conn.send(f"child {os.getpid()} handled {request!r}")
    conn.close()


def w_bump_unsafe(counter, times):
    """Increments a shared Value with no lock. Races."""
    for _ in range(times):
        counter.value += 1  # read, add, write: three steps, interruptible


def w_bump_safe(counter, lock, times):
    """Same, but the read-modify-write is protected."""
    for _ in range(times):
        with lock:
            counter.value += 1


def w_fill_array(array, index, value):
    array[index] = value


def w_manager_update(shared_dict, shared_list, key):
    """Manager proxies work like normal dict/list but talk over a socket."""
    shared_dict[key] = os.getpid()
    shared_list.append(key)


def w_cpu(n):
    """Pure-Python CPU work. Identical to the one in threads.py."""
    total = 0
    for i in range(n):
        total += i * i
    return total


def w_io(seconds=0.5):
    """Blocking I/O stand-in."""
    time.sleep(seconds)
    return seconds


def w_square(x):
    return x * x


def w_maybe_fail(x):
    if x == 3:
        raise ValueError(f"cannot process {x}")
    return x * 10


def w_sum(numbers):
    """Trivial work on a big payload: measures transfer cost, not compute."""
    return sum(numbers)


def w_start_method_probe(queue):
    queue.put((mp.get_start_method(), SHARED_GLOBAL, os.getpid()))


# ===========================================================================
# PART 1 - PROCESS BASICS
# ===========================================================================


def demo_basics():
    """A Process is a whole second Python interpreter."""
    banner("1a. Process basics - start, join, pid, exitcode")

    print(f"  parent pid={os.getpid()}, start method={mp.get_start_method()}")
    print(
        f"  cpu_count={mp.cpu_count()}, usable by this process={os.process_cpu_count()}"
    )

    workers = [
        mp.Process(target=w_greet, args=(f"Child-{i + 1}",), name=f"Child-{i + 1}")
        for i in range(3)
    ]
    for p in workers:
        p.start()
    for p in workers:
        p.join()  # wait for it to finish, exactly like Thread.join()

    for p in workers:
        print(f"  {p.name}: alive={p.is_alive()}, exitcode={p.exitcode}")

    print("\n  Every pid is different, so this is real OS-level parallelism.")
    print("  exitcode 0 = clean, non-zero = raised, negative = killed by signal.")


def demo_isolation():
    """The headline difference from threads: memory is not shared."""
    banner("1b. Memory is NOT shared (the whole point, and the whole cost)")

    global SHARED_GLOBAL
    SHARED_GLOBAL = 100
    print(f"  parent sets SHARED_GLOBAL = {SHARED_GLOBAL}\n")

    # What the child inherits depends entirely on the start method.
    for method in mp.get_all_start_methods():
        ctx = mp.get_context(method)
        queue = ctx.Queue()
        p = ctx.Process(target=w_report_global, args=(queue,))
        p.start()
        _, seen, pid = queue.get()
        p.join()
        note = (
            "copied the parent's memory" if seen == 100 else "re-imported this module"
        )
        print(f"  {method:<11} child saw {seen:>4}   ({note})")

    # And a child mutating it never reaches the parent, on any method.
    p = mp.Process(target=w_mutate_global)
    p.start()
    p.join()
    print(f"\n  child set it to 999; parent still sees {SHARED_GLOBAL}")

    print("\n  With threads, that last line would print 999 - one memory space.")
    print("  With processes there is no shared memory at all, so to communicate")
    print("  you must copy data across a pipe (section 2) or ask the OS for an")
    print("  explicitly shared block (Value / Array).")
    SHARED_GLOBAL = 0


def demo_lifecycle():
    """Failures, daemons, and killing a process that will not stop."""
    banner("1c. Lifecycle - exceptions, terminate, daemon")

    # An exception in a child does not propagate. You get an exitcode.
    p = mp.Process(target=w_crash)
    p.start()
    p.join()
    print(f"  crashed child: exitcode={p.exitcode}  (traceback went to stderr)")
    print("  Note: the parent did NOT raise. Use a Pool/Executor if you want the")
    print("  exception delivered back to you (section 3b).")

    # terminate() sends SIGTERM. Abrupt: no cleanup, no finally blocks.
    p = mp.Process(target=w_forever, daemon=True)
    p.start()
    print(f"\n  runaway child pid={p.pid}, alive={p.is_alive()}")
    p.terminate()
    p.join(timeout=2)
    print(f"  after terminate(): alive={p.is_alive()}, exitcode={p.exitcode}")
    print("  Negative exitcode = killed by that signal number (-15 is SIGTERM).")
    print("\n  daemon=True also means the parent will not wait for it at exit,")
    print("  and daemonic processes may not have children of their own.")


# ===========================================================================
# PART 2 - TALKING BETWEEN PROCESSES
# ===========================================================================


def demo_queue():
    """mp.Queue: the default way to move work between processes."""
    banner("2a. Queue - the default channel")

    queue = mp.Queue()
    producer = mp.Process(target=w_producer, args=(queue, 5))
    consumer = mp.Process(target=w_consumer, args=(queue,))
    producer.start()
    consumer.start()
    producer.join()
    consumer.join()

    print(f"\n  parent pid={os.getpid()} - the two children talked directly.")
    print("  Under the hood: objects are pickled, written to a pipe, unpickled.")
    print("  So anything you put on a queue must be picklable, and big objects")
    print("  cost real time to move (measured in section 3c).")


def demo_pipe():
    """Pipe: a direct two-way channel between exactly two processes."""
    banner("2b. Pipe - a direct link between two processes")

    parent_conn, child_conn = mp.Pipe()
    p = mp.Process(target=w_pipe_child, args=(child_conn,))
    p.start()

    parent_conn.send({"job": "resize-image"})
    print(f"  parent received: {parent_conn.recv()}")
    p.join()

    print("\n  Pipe is faster and lighter than Queue but only connects two ends")
    print("  and has no locking, so two processes writing the same end can")
    print("  corrupt data. Queue is Pipe plus a lock plus a feeder thread.")


def demo_shared_memory():
    """Value and Array: actual shared memory, and why you still need a Lock."""
    banner("2c. Value / Array - real shared memory, and the lock you still need")

    TIMES = 20_000
    PROCS = 4

    # Without a lock: counter.value += 1 is read, add, write.
    unsafe = mp.Value("i", 0)
    workers = [
        mp.Process(target=w_bump_unsafe, args=(unsafe, TIMES)) for _ in range(PROCS)
    ]
    for p in workers:
        p.start()
    for p in workers:
        p.join()

    expected = TIMES * PROCS
    print(
        f"  no lock:   {unsafe.value:>7,} of {expected:,}  "
        f"(lost {expected - unsafe.value:,})"
    )

    # With a lock: correct, and noticeably slower.
    safe = mp.Value("i", 0)
    lock = mp.Lock()
    workers = [
        mp.Process(target=w_bump_safe, args=(safe, lock, TIMES)) for _ in range(PROCS)
    ]
    for p in workers:
        p.start()
    for p in workers:
        p.join()
    print(f"  with lock: {safe.value:>7,} of {expected:,}")

    # Array is the same idea for a fixed-size block of one C type.
    scores = mp.Array("d", 4)
    workers = [
        mp.Process(target=w_fill_array, args=(scores, i, (i + 1) * 1.5))
        for i in range(4)
    ]
    for p in workers:
        p.start()
    for p in workers:
        p.join()
    print(f"  shared Array: {list(scores)}")

    print("\n  Value/Array live in memory both processes can see, so there is no")
    print("  pickling - but that also means the same races you get with threads.")
    print("  Note the 'i' and 'd': these hold C types, not arbitrary Python")
    print("  objects. For those you need a Manager.")


def demo_manager():
    """Manager: shared Python objects, at the cost of a server process."""
    banner("2d. Manager - shared dict/list/etc, via a server process")

    with mp.Manager() as manager:
        registry = manager.dict()
        order = manager.list()

        workers = [
            mp.Process(target=w_manager_update, args=(registry, order, f"task-{i}"))
            for i in range(4)
        ]
        for p in workers:
            p.start()
        for p in workers:
            p.join()

        print(f"  shared dict: {dict(registry)}")
        print(f"  shared list: {list(order)}")

    print("\n  A Manager starts a separate server process that owns the real")
    print("  object; everyone else holds a proxy and every access is an IPC")
    print("  round trip. Very convenient, clearly the slowest option - do not")
    print("  put a Manager proxy inside a hot loop.")
    print("\n  Rough ordering, fastest to slowest:")
    print("    Value/Array  <  Pipe  <  Queue  <  Manager proxy")


# ===========================================================================
# PART 3 - POOLS
# ===========================================================================


def demo_pool():
    """Pools reuse a fixed set of processes instead of spawning per task."""
    banner("3a. Pool and ProcessPoolExecutor")

    numbers = list(range(10))

    with mp.Pool(processes=4) as pool:
        print(f"  pool.map:          {pool.map(w_square, numbers)}")
        # imap yields results lazily, in order, as they arrive.
        print(f"  pool.imap (lazy):  {list(pool.imap(w_square, numbers))}")
        # imap_unordered yields whichever finishes first.
        print(f"  imap_unordered:    {sorted(pool.imap_unordered(w_square, numbers))}")
        # apply_async for a single call you collect later.
        handle = pool.apply_async(w_square, (12,))
        print(f"  apply_async:       {handle.get(timeout=5)}")

    # The concurrent.futures API is the same shape as ThreadPoolExecutor, which
    # makes swapping between threads and processes a one-word change.
    with ProcessPoolExecutor(max_workers=4) as pool:
        print(f"  executor.map:      {list(pool.map(w_square, numbers))}")

    print("\n  A pool creates its workers once and feeds them. Spawning a fresh")
    print("  process per task would cost more than most tasks are worth.")
    print("  Sizing: cpu_count() for CPU-bound work. More only helps if the")
    print("  workers block on I/O, and then threads are usually the better tool.")


def demo_pool_errors():
    """Where the exception surfaces, and what cannot be sent at all."""
    banner("3b. Errors and pickling limits")

    with ProcessPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(w_maybe_fail, x): x for x in range(5)}
        for future, x in futures.items():
            try:
                print(f"  input {x} -> {future.result()}")
            except ValueError as exc:
                # Unlike a bare Process, the pool pickles the exception in the
                # child and re-raises it here. This is the main reason to use a
                # pool even when you only have one task.
                print(f"  input {x} -> FAILED: {exc}")

    # Things that cannot cross a process boundary.
    print("\n  Not picklable, so not usable as pool work:")
    try:
        with ProcessPoolExecutor(max_workers=1) as pool:
            list(pool.map(lambda x: x * 2, [1, 2, 3]))
    except Exception as exc:
        print(f"    lambda        -> {type(exc).__name__}")

    print("    closures, nested defs, open sockets, file handles, threading.Lock")
    print("  Workarounds: module-level functions, functools.partial, or pass the")
    print("  arguments a worker needs to build the object itself.")


def demo_data_cost():
    """The trade that decides whether multiprocessing helps at all."""
    banner("3c. The cost of moving data")

    chunks = [list(range(200_000)) for _ in range(8)]  # ~1.6M ints to ship

    with timed("serial sum (no data movement)") as serial:
        [w_sum(c) for c in chunks]

    with timed("4 processes (must pickle every chunk)") as parallel:
        with ProcessPoolExecutor(max_workers=4) as pool:
            list(pool.map(w_sum, chunks))

    print(f"\n  parallel/serial ratio: {parallel.elapsed / serial.elapsed:.1f}x SLOWER")
    print("  sum() over a list is almost no work per byte, so pickling the list,")
    print("  piping it, and unpickling it dwarfs the computation.")

    # Same process count, but now the work per byte is enormous.
    print()
    with timed("serial heavy compute") as serial2:
        [w_cpu(12_000_000) for _ in range(4)]

    with timed("4 processes, heavy compute, tiny args") as parallel2:
        with ProcessPoolExecutor(max_workers=4) as pool:
            list(pool.map(w_cpu, [12_000_000] * 4))

    print(f"\n  speedup: {serial2.elapsed / parallel2.elapsed:.2f}x FASTER")
    print("  Same four processes. The only difference is that the argument is one")
    print("  small int and the work per byte is huge.")
    print("\n  The rule: multiprocessing pays off when compute per byte transferred")
    print("  is high. If you are shipping big arrays around, look at chunksize,")
    print("  multiprocessing.shared_memory, or numpy before reaching for a pool.")


# ===========================================================================
# PART 4 - START METHODS
# ===========================================================================


def demo_start_methods():
    """spawn, fork, forkserver - and what Python 3.14 changed."""
    banner("4. Start methods: spawn vs fork vs forkserver")

    global SHARED_GLOBAL
    SHARED_GLOBAL = 42

    print(f"  default here: {mp.get_start_method()}")
    print(f"  available:    {mp.get_all_start_methods()}\n")

    def launch(ctx, queue):
        p = ctx.Process(target=w_start_method_probe, args=(queue,))
        p.start()
        result = queue.get()
        p.join()
        return result

    for method in mp.get_all_start_methods():
        ctx = mp.get_context(method)
        queue = ctx.Queue()

        # Two children, timed separately: forkserver pays a one-time cost to
        # boot its server process, and that cost lands on the first child only.
        with timed(f"{method:<11} 1st child") as first:
            reported, seen, _ = launch(ctx, queue)
        with timed(f"{method:<11} 2nd child") as second:
            launch(ctx, queue)

        print(f"      -> child saw start_method={reported}, SHARED_GLOBAL={seen}")
        print(f"      -> 2nd child was {first.elapsed / second.elapsed:.1f}x faster")

    SHARED_GLOBAL = 0

    print("\n  Caveat on those timings: if you ran the whole file, section 1b already")
    print("  booted a forkserver, so forkserver's '1st child' here is already warm.")
    print("  Run this section alone to see the real one-time cost:")
    print("      python process.py start_methods")
    print("  Cold, the numbers are ~0.12s / ~0.13s / ~0.03s for spawn / forkserver")
    print("  1st / forkserver 2nd - forkserver amortises, spawn never does.")

    print("\n  spawn      : brand new interpreter, re-imports your module, inherits")
    print("               nothing. Slowest to start, safest, works everywhere.")
    print("  fork       : clones the parent process. Fast and inherits everything,")
    print("               which is exactly the problem - locks held at fork time")
    print("               stay locked, and threads do not survive, so a forked")
    print("               child can deadlock. Unsafe on macOS.")
    print("  forkserver : forks from a small, clean server process started early.")
    print("               Fast like fork, without inheriting your mess.")
    print("\n  Python 3.14: fork is no longer the default on ANY platform. macOS and")
    print("  Windows use spawn (macOS since 3.8), Linux now uses forkserver. Code")
    print("  that genuinely needs fork must ask for it:")
    print("      ctx = multiprocessing.get_context('fork')")
    print("\n  Practical consequence of spawn/forkserver: your module gets imported")
    print("  in the child, so top-level code must be guarded and workers must be")
    print("  importable by name. That is the source of most multiprocessing bugs.")


# ===========================================================================
# PART 5 - COMPARISON
# ===========================================================================


def demo_showdown():
    """The same two workloads under all four models."""
    banner("5a. Showdown: serial vs threads vs processes vs asyncio")

    WORK = 15_000_000
    N = 4

    print("  CPU-bound: 4 x 15,000,000 iteration loop\n")

    with timed("serial") as cpu_serial:
        [w_cpu(WORK) for _ in range(N)]

    with timed("threads (4)") as cpu_threads:
        with ThreadPoolExecutor(max_workers=N) as pool:
            list(pool.map(w_cpu, [WORK] * N))

    with timed("processes (4)") as cpu_procs:
        with ProcessPoolExecutor(max_workers=N) as pool:
            list(pool.map(w_cpu, [WORK] * N))

    async def cpu_async():
        # asyncio has no parallelism of its own. Coroutines that never await
        # simply run one after another on a single thread.
        return [w_cpu(WORK) for _ in range(N)]

    with timed("asyncio") as cpu_async_t:
        asyncio.run(cpu_async())

    print(
        f"\n    threads   {cpu_serial.elapsed / cpu_threads.elapsed:.2f}x   "
        f"processes {cpu_serial.elapsed / cpu_procs.elapsed:.2f}x   "
        f"asyncio {cpu_serial.elapsed / cpu_async_t.elapsed:.2f}x"
    )

    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    if gil:
        print("    Only processes win. Threads are blocked by the GIL, and asyncio")
        print("    never had anything to offer CPU-bound code.")
    else:
        print("    Free-threaded build: threads win too, and beat processes because")
        print("    there is no pickling or process startup to pay for.")

    print("\n  I/O-bound: 8 x 0.5s waits\n")

    IO_N = 8

    with timed("serial") as io_serial:
        [w_io() for _ in range(IO_N)]

    with timed("threads (8)") as io_threads:
        with ThreadPoolExecutor(max_workers=IO_N) as pool:
            list(pool.map(w_io, [0.5] * IO_N))

    with timed("processes (8)") as io_procs:
        with ProcessPoolExecutor(max_workers=IO_N) as pool:
            list(pool.map(w_io, [0.5] * IO_N))

    async def io_async():
        return await asyncio.gather(*(asyncio.sleep(0.5) for _ in range(IO_N)))

    with timed("asyncio") as io_async_t:
        asyncio.run(io_async())

    print(
        f"\n    threads   {io_serial.elapsed / io_threads.elapsed:.2f}x   "
        f"processes {io_serial.elapsed / io_procs.elapsed:.2f}x   "
        f"asyncio {io_serial.elapsed / io_async_t.elapsed:.2f}x"
    )
    print("    All three work. Processes get there by burning 8 interpreters and")
    print("    ~8x the memory to do nothing but wait, which is why nobody does it.")


def demo_summary():
    banner("5b. Summary")

    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    build = "standard (GIL on)" if gil else "free-threaded (GIL off)"
    print(
        f"  Python {sys.version.split()[0]}, {build}, "
        f"start method '{mp.get_start_method()}'\n"
    )

    rows = [
        ("", "threading", "multiprocessing", "asyncio"),
        ("-" * 18, "-" * 17, "-" * 17, "-" * 17),
        ("Unit", "OS thread", "OS process", "coroutine"),
        ("Memory", "shared", "separate", "shared"),
        ("CPU parallelism", "no (GIL)" if gil else "YES (no GIL)", "yes", "no"),
        ("I/O concurrency", "yes", "yes, wasteful", "yes, best"),
        ("Startup cost", "~40 us", "~100 ms spawn", "~3 us"),
        ("Data sharing", "free", "pickle + pipe", "free"),
        ("Crash blast area", "whole process", "one worker", "whole process"),
        ("Needs locks", "yes", "only for shared", "rarely"),
        ("10k units", "~350 MB", "not feasible", "~15 MB"),
        ("Debugging", "hard (races)", "hard (IPC)", "easier"),
    ]
    for row in rows:
        print(f"  {row[0]:<18} {row[1]:<17} {row[2]:<17} {row[3]}")

    print("\n  Startup costs above are measured on this machine: 37 us per thread,")
    print("  106 ms per spawned process, 1.8 ms per forked one, 2.5 us per")
    print("  coroutine. That ~2800x gap between a thread and a spawned process is")
    print("  why you use a Pool instead of a Process per task.")

    print("\n  How to choose, in order:")
    print("    1. Waiting on the network, and async libraries exist   -> asyncio")
    print("    2. Waiting on blocking calls, SDKs, or files           -> threads")
    print("    3. Burning CPU in pure Python                          -> processes")
    print("    4. Burning CPU, and you can use 3.14t                  -> threads")
    print("    5. Need crash isolation or to escape a leaky C library -> processes")

    print("\n  Before reaching for multiprocessing, check whether the library")
    print("  already releases the GIL. numpy, pandas, hashlib, zlib and most")
    print("  compiled extensions do, so plain threads may already be parallel.")

    print("\n  See threads.py for the threading side, including what changes on a")
    print("  free-threaded build.")


# ===========================================================================
# RUNNER
# ===========================================================================

DEMOS = {
    # Part 1 - basics
    "basics": demo_basics,
    "isolation": demo_isolation,
    "lifecycle": demo_lifecycle,
    # Part 2 - communication
    "queue": demo_queue,
    "pipe": demo_pipe,
    "shared": demo_shared_memory,
    "manager": demo_manager,
    # Part 3 - pools
    "pool": demo_pool,
    "pool_errors": demo_pool_errors,
    "data_cost": demo_data_cost,
    # Part 4 - start methods
    "start_methods": demo_start_methods,
    # Part 5 - comparison
    "showdown": demo_showdown,
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


# This guard is not optional. With spawn and forkserver every child re-imports
# this module, and without the guard each child would run main() again and spawn
# children of its own.
if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
