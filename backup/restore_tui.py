#!/usr/bin/env python3
"""Pick a database + point in time on a backup timeline, then run restore.sh.

Front end only: all restore logic (and the final YES confirmation) stays in
restore.sh. Stdlib only, so it runs on the bare host.
"""
import curses
import json
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
BACKUP_ROOT = os.path.join(os.path.dirname(REPO_DIR), "backups")
STANZA = "shaka_db"
DB_IMAGE = "odoo_19_db:pg16"
SYSTEM_DBS = {"postgres", "template0", "template1"}
STEPS = [(1, "1s"), (10, "10s"), (60, "1m"), (600, "10m"), (3600, "1h"), (86400, "1d")]
TZ = ZoneInfo("Asia/Tehran")  # same zone as the containers (docker-compose.yml)
MODES = ["replace", "side-by-side", "whole cluster"]


def pgbackrest_info(*extra):
    cmd = ["docker", "run", "--rm", "--user", "postgres",
           "-v", f"{BACKUP_ROOT}/pgbackrest:/var/lib/pgbackrest",
           "-v", f"{REPO_DIR}/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro",
           "--entrypoint", "pgbackrest", DB_IMAGE,
           f"--stanza={STANZA}", "info", "--output=json", *extra]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"cannot read backup repo at {BACKUP_ROOT}/pgbackrest:\n{out.stderr or out.stdout}")
    return json.loads(out.stdout)[0]


def load_backups():
    print("reading backup repo ...", flush=True)
    backups = []
    for b in pgbackrest_info().get("backup", []):
        detail = pgbackrest_info(f"--set={b['label']}")["backup"][0]
        dbs = sorted(d["name"] for d in detail.get("database-ref", []) if d["name"] not in SYSTEM_DBS)
        backups.append({
            "label": b["label"],
            "type": b["type"],
            # pgbackrest needs a backup whose stop time is strictly before the target
            "stop": b["timestamp"]["stop"] + 1,
            "dbs": dbs,
        })
    if not backups:
        sys.exit("no backups in the repo yet — run ./backup/pgbackrest_full.sh first")
    return sorted(backups, key=lambda b: b["stop"])


def fmt(ts):
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M:%S")


def ui(scr, backups):
    curses.curs_set(0)
    curses.use_default_colors()
    for i, c in enumerate([curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED], 1):
        curses.init_pair(i, c, -1)
    CYAN, GREEN, YELLOW, RED = (curses.color_pair(i) for i in range(1, 5))

    tmin = backups[0]["stop"]
    tmax = int(datetime.now().timestamp())  # WAL is archived every <=30s, so "now" is reachable
    t, step, mode, sel, msg = tmax, 2, 0, 0, ""

    def put(y, x, s, attr=0):
        h, w = scr.getmaxyx()
        if 0 <= y < h and x < w:
            scr.addnstr(y, x, s, w - x - 1, attr)

    while True:
        base = max((b for b in backups if b["stop"] <= t), key=lambda b: b["stop"])
        dbs = base["dbs"]
        sel = min(sel, max(len(dbs) - 1, 0))
        latest = t >= tmax

        scr.erase()
        h, w = scr.getmaxyx()
        width = max(w - 6, 10)
        pos = lambda ts: 2 + round((ts - tmin) / max(tmax - tmin, 1) * (width - 1))

        put(0, 2, "Shaka backup restore", curses.A_BOLD)
        put(1, 2, "←/→ move  +/- step  [/] prev/next backup  t type time  e latest", curses.A_DIM)
        put(2, 2, "↑/↓ database  m mode  Enter restore  q quit", curses.A_DIM)

        put(4, 2, f"Restorable range: {fmt(tmin)}  →  now   (Tehran time)", CYAN)
        put(6, 2, "─" * width, CYAN)
        for b in backups:
            put(6, pos(b["stop"]), b["type"][0].upper(), GREEN | curses.A_BOLD)
        put(7, pos(t), "▲", YELLOW | curses.A_BOLD)
        put(8, 2, fmt(tmin)[:16], curses.A_DIM)
        put(8, 2 + width - 3, "now", curses.A_DIM)
        put(9, 2, "F = full  D = differential  I = incremental backup", curses.A_DIM)

        target = "latest (now)" if latest else fmt(t)
        put(11, 2, "Target: ", curses.A_BOLD)
        put(11, 10, target, YELLOW | curses.A_BOLD)
        put(11, 10 + len(target) + 2, f"step {STEPS[step][1]}", curses.A_DIM)
        put(12, 2, f"Uses backup {base['label']} ({base['type']}, finished {fmt(base['stop'])}) + WAL replay", curses.A_DIM)

        put(14, 2, "Mode: ", curses.A_BOLD)
        put(14, 8, MODES[mode], YELLOW | curses.A_BOLD)
        put(15, 2, {
            0: "Replace the live database; the current one is kept as <db>_before_restore_<ts>.",
            1: "Restore next to the live one under a new name; nothing existing changes.",
            2: "Wipe and restore EVERY database on the server (disaster recovery).",
        }[mode], RED if mode == 2 else curses.A_DIM)

        put(17, 2, "Database:" if mode != 2 else "Database: (all)", curses.A_BOLD)
        if mode != 2:
            if not dbs:
                put(18, 4, "no user databases in this backup", RED)
            for i, d in enumerate(dbs[: max(h - 21, 1)]):
                put(18 + i, 4, ("▸ " if i == sel else "  ") + d, YELLOW | curses.A_REVERSE if i == sel else 0)
        if msg:
            put(h - 1, 2, msg, RED)
        msg = ""
        scr.refresh()

        k = scr.get_wch()
        if k == "q":
            return None
        elif k == curses.KEY_LEFT:
            t = max(tmin, (tmax if latest else t) - STEPS[step][0])
        elif k == curses.KEY_RIGHT:
            t = min(tmax, t + STEPS[step][0])
        elif k in ("+", "="):
            step = min(step + 1, len(STEPS) - 1)
        elif k in ("-", "_"):
            step = max(step - 1, 0)
        elif k == "[":
            prev = [b["stop"] for b in backups if b["stop"] < t]
            t = prev[-1] if prev else tmin
        elif k == "]":
            nxt = [b["stop"] for b in backups if b["stop"] > t]
            t = nxt[0] if nxt else tmax
        elif k == "e":
            t = tmax
        elif k == curses.KEY_UP:
            sel = max(sel - 1, 0)
        elif k == curses.KEY_DOWN:
            sel = min(sel + 1, max(len(dbs) - 1, 0))
        elif k == "m":
            mode = (mode + 1) % len(MODES)
        elif k == "t":
            curses.echo(); curses.curs_set(1)
            put(h - 1, 2, "Tehran time (YYYY-MM-DD HH:MM[:SS]): ", curses.A_BOLD)
            raw = scr.getstr(h - 1, 40, 19).decode().strip()
            curses.noecho(); curses.curs_set(0)
            for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    ts = int(datetime.strptime(raw, f).replace(tzinfo=TZ).timestamp())
                    break
                except ValueError:
                    ts = None
            if ts is None:
                msg = f"can't read '{raw}'"
            elif not tmin <= ts <= tmax:
                msg = f"{raw} is outside the restorable range"
            else:
                t = ts
        elif k in ("\n", curses.KEY_ENTER):
            if mode != 2 and not dbs:
                msg = "no database to restore at this point"
                continue
            args = []
            if mode == 2:
                args.append("--all")
            else:
                args += ["--db", dbs[sel]]
                if mode == 1:
                    args += ["--as", f"{dbs[sel]}_{datetime.fromtimestamp(t, TZ):%Y%m%d_%H%M}"]
            if not latest:
                # explicit UTC offset: the host and the db container may be in different time zones
                z = datetime.fromtimestamp(t, TZ).strftime("%z")
                args += ["--target", fmt(t) + z[:3] + ":" + z[3:]]
            return args


def main():
    args = curses.wrapper(ui, load_backups())
    if args is None:
        print("nothing restored")
        return
    script = os.path.join(SCRIPT_DIR, "restore.sh")
    print("running:", script, " ".join(f"'{a}'" if " " in a else a for a in args), "\n")
    os.execv(script, [script, *args])  # restore.sh asks for the final YES


if __name__ == "__main__":
    main()
