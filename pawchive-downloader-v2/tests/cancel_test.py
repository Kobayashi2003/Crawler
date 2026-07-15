"""Cancellation: cancel one, cancel all, and the guarantees that make it rigorous."""
import sys, io, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.core.scheduler import Scheduler
from src.core.models import DownloadTask, TaskType

fails = []


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


class _Log:
    def __getattr__(self, _):
        return lambda **k: None


class StubDownloader:
    """Mirrors the real Downloader's cancellation contract."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cancelled = set()
        self.aborted = False
        self.abort_calls = 0

    def cancel(self, *ids):
        with self.lock:
            self.cancelled.update(ids)

    def uncancel(self, aid):
        with self.lock:
            self.cancelled.discard(aid)

    def is_cancelled(self, aid):
        with self.lock:
            return aid in self.cancelled

    def abort_requests(self):
        self.aborted = True
        self.abort_calls += 1

    def resume_requests(self):
        self.aborted = False


def make(**kw):
    s = Scheduler(storage=None, downloader=StubDownloader(), logger=_Log(),
                  global_timer=None, max_workers=3)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def enqueue(s, *ids):
    for aid in ids:
        t = DownloadTask(aid, task_type=TaskType.MANUAL)
        s.queue.put(t)
        s.queued.add(t)


# A worker that leaves `active` once it observes its own cancel flag.
def spawn_worker(s, aid):
    def run():
        while not s.downloader.is_cancelled(aid):
            time.sleep(0.02)
        with s.lock:
            s.active.pop(aid, None)
    threading.Thread(target=run, daemon=True).start()


print("cancel one")
s = make()
enqueue(s, "a", "b", "c")
check("queued cancel returns 'queued'", s.cancel("b") == "queued")
check("only the target left the queue", [t.artist_id for t in s.list_queued()] == ["a", "c"])
check("queued set stays in sync", {t.artist_id for t in s.queued} == {"a", "c"})
check("unknown id returns None", s.cancel("zz") is None)

s = make()
s.active["r1"] = DownloadTask("r1", task_type=TaskType.MANUAL)
spawn_worker(s, "r1")
check("running cancel returns 'running'", s.cancel("r1") == "running")
check("task left active", "r1" not in s.active)
check("single cancel must NOT abort other artists' requests", s.downloader.abort_calls == 0)

print("\ncancel all")
s = make()
enqueue(s, "q1", "q2")
for aid in ("r1", "r2"):
    s.active[aid] = DownloadTask(aid, task_type=TaskType.MANUAL)
    spawn_worker(s, aid)
n = s.cancel_all()
check("returns the number that were running", n == 2)
check("queue emptied", s.list_queued() == [])
check("queued set emptied", s.queued == set())
check("all running tasks left active", not s.active)
check("in-flight requests were aborted", s.downloader.abort_calls == 1)
check("requests resumed afterwards", s.downloader.aborted is False)
check("_cancelling cleared", s._cancelling is False)

print("\nthe guarantee: a timeout must not un-cancel a straggler")
s = make(CANCEL_TIMEOUT=0.3)
s.active["stuck"] = DownloadTask("stuck", task_type=TaskType.MANUAL)  # never exits
n = s.cancel_all()
check("cancel_all returns despite the straggler", n == 1)
check("straggler is STILL marked cancelled after timeout",
      s.downloader.is_cancelled("stuck"))
check("requests resumed even though it is stuck", s.downloader.aborted is False)
check("_cancelling cleared even on timeout", s._cancelling is False)
# Only the run itself may clear the flag.
s.downloader.uncancel("stuck")
check("flag clears only when the run exits", not s.downloader.is_cancelled("stuck"))

print("\nno task may start mid-cancel")
s = make(CANCEL_TIMEOUT=0.3)
s.active["stuck"] = DownloadTask("stuck", task_type=TaskType.MANUAL)
enqueue(s, "later")
s._cancelling = True
s._process()  # would otherwise pop "later" and run it into the abort
check("_process starts nothing while cancelling", "later" not in s.active)

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
