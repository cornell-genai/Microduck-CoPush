"""The memory watchdog (scripts/guard/memwatch.sh) stops a job that passes its limits and leaves a normal one alone."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH = os.path.join(ROOT, "scripts", "guard", "memwatch.sh")
LEAK = "import time\nx = []\nwhile True:\n    x.append(bytearray(40 * 1024 * 1024)); time.sleep(0.05)\n"
HOLD = "import time\nx = bytearray(300 * 1024 * 1024)\ntime.sleep({s})\n"


def _job(code, per, total, tmp, n=1):
    """n processes running code in one new process group, watched with the given limits (GB) -> (processes, watchdog)."""
    first = subprocess.Popen([sys.executable, "-c", code], process_group=0)
    rest = [subprocess.Popen([sys.executable, "-c", code], process_group=first.pid) for _ in range(n - 1)]
    w = subprocess.Popen(["sh", WATCH, str(first.pid), str(per), str(total), str(tmp), "1"], stderr=subprocess.PIPE, text=True)
    return [first] + rest, w


def test_a_leaking_process_is_stopped_with_a_message_and_a_log_line(tmp_path):
    (tmp_path / "runs").mkdir()
    procs, w = _job(LEAK, 0.4, 100, tmp_path)
    assert procs[0].wait(timeout=60) != 0
    err = w.communicate(timeout=30)[1]
    assert "MEMORY GUARD" in err and "per-process limit" in err
    assert "MEMORY GUARD" in (tmp_path / "runs" / "memguard.log").read_text()


def test_the_job_total_is_limited_too(tmp_path):
    procs, w = _job(HOLD.format(s=60), 100, 0.5, tmp_path, n=3)   # 3 x 0.3 GB: each under 100 GB, together over 0.5 GB
    assert all(p.wait(timeout=60) != 0 for p in procs)
    assert "job limit" in w.communicate(timeout=30)[1]


def test_a_normal_job_is_left_alone_and_the_watchdog_exits_with_it(tmp_path):
    procs, w = _job(HOLD.format(s=4), 2, 4, tmp_path)
    assert procs[0].wait(timeout=30) == 0
    assert w.wait(timeout=30) == 0 and "MEMORY GUARD" not in w.stderr.read()


def test_rl_sh_starts_the_watchdog_once_per_job():
    sh = open(os.path.join(ROOT, "scripts", "rl.sh")).read()
    assert "memwatch.sh" in sh and "COPUSH_MEM_WATCH" in sh and "COPUSH_MEM_LIMIT_GB" in sh
