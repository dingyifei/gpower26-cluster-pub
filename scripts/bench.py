#!/usr/bin/env python3
"""Bench TUI: drive route D (scripts/route_d.sh) for the phones on this Mac's USB ports.

    .venv/bin/python scripts/bench.py

Left: attached phones (adb + fastboot, refreshed every 3 s) with the route stage they are on.
Right: stage list for the selected phone (logs/<serial>/stages.json) and its live log.
Every action runs an existing script as a subprocess, one job per phone, several phones in parallel.
Typed confirmations (FLASH/ERASE) and manual steps (setup wizard, SIM) pop up as dialogs.

Keys: r run/resume route D · o run one stage · f run from a stage · m modem on/off · k kill job
      w wake · p park · c record · l clear log view · q quit
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, OptionList, RichLog, Static
from textual.widgets.option_list import Option

ROOT = Path(__file__).resolve().parent.parent
ROUTE = ROOT / "scripts" / "route_d.sh"
PHONE = ROOT / "scripts" / "phone.sh"
NEVER: set[str] = set()   # serials route D must refuse (phone #1 was A until 2026-11-18; now D)
STAGE_STYLE = {"done": "green", "running": "yellow", "fail": "bold red", "skip": "dim", "": "dim"}


def stages_list() -> list[str]:
    try:
        return subprocess.run([str(ROUTE), "--list"], capture_output=True, text=True, timeout=10).stdout.split()
    except Exception:
        return []


def read_stages(serial: str) -> dict:
    f = ROOT / "logs" / serial / "stages.json"
    try:
        return json.loads(f.read_text()).get("stages", {})
    except Exception:
        return {}


def scan_devices() -> dict[str, str]:
    """serial -> mode (device / unauthorized / recovery / fastboot ...)."""
    out: dict[str, str] = {}
    try:
        for ln in subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=8).stdout.splitlines()[1:]:
            p = ln.split()
            if len(p) >= 2:
                out[p[0]] = "adb" if p[1] == "device" else p[1]
    except Exception:
        pass
    try:
        for ln in subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=8).stdout.splitlines():
            p = ln.split()
            if p:
                out[p[0]] = "fastboot"
    except Exception:
        pass
    return out


@dataclass
class Job:
    serial: str
    label: str
    proc: asyncio.subprocess.Process | None = None
    lines: list[str] = field(default_factory=list)


class ConfirmScreen(ModalScreen[str | None]):
    """Typed confirmation: the user must type the token."""

    def __init__(self, serial: str, token: str, text: str) -> None:
        super().__init__()
        self.serial, self.token, self.text = serial, token, text

    def compose(self) -> ComposeResult:
        with Vertical(id="dlg"):
            yield Label(f"[b]{self.serial}[/b] — confirm", classes="title")
            yield Static(self.text)
            yield Static(f"Type exactly: [b reverse] {self.token} [/]")
            yield Input(placeholder=self.token, id="ans")
            with Horizontal(classes="buttons"):
                yield Button("Confirm", variant="error", id="ok")
                yield Button("Cancel (abort job)", id="cancel")

    @on(Input.Submitted)
    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(self.query_one("#ans", Input).value)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class ManualScreen(ModalScreen[str]):
    """A step only a human can do."""

    def __init__(self, serial: str, text: str) -> None:
        super().__init__()
        self.serial, self.text = serial, text

    def compose(self) -> ComposeResult:
        with Vertical(id="dlg"):
            yield Label(f"[b]{self.serial}[/b] — manual step", classes="title")
            yield Static(self.text)
            with Horizontal(classes="buttons"):
                yield Button("Done", variant="success", id="done")
                yield Button("Skip", id="skip")

    @on(Button.Pressed, "#done")
    def _done(self) -> None:
        self.dismiss("")

    @on(Button.Pressed, "#skip")
    def _skip(self) -> None:
        self.dismiss("skip")


class PickStage(ModalScreen[str | None]):
    def __init__(self, title: str, stages: list[str]) -> None:
        super().__init__()
        self.title_text, self.stages = title, stages

    def compose(self) -> ComposeResult:
        with Vertical(id="dlg"):
            yield Label(self.title_text, classes="title")
            yield OptionList(*[Option(s, id=s) for s in self.stages], id="opts")
            yield Button("Cancel", id="cancel")

    @on(OptionList.OptionSelected)
    def _pick(self, ev: OptionList.OptionSelected) -> None:
        self.dismiss(ev.option.id)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class Bench(App):
    TITLE = "gpower2026 bench — route D"
    CSS = """
    #phones { width: 46; border: round $accent; }
    #right { border: round $accent; }
    #stages { height: 19; }
    #log { border-top: solid $accent; }
    #status { height: 1; color: $text-muted; }
    #dlg { width: 80; height: auto; padding: 1 2; border: thick $warning; background: $surface; }
    #dlg .title { text-style: bold; margin-bottom: 1; }
    #dlg Input { margin: 1 0; }
    #dlg OptionList { height: 18; }
    .buttons { height: auto; margin-top: 1; }
    .buttons Button { margin-right: 2; }
    ConfirmScreen, ManualScreen, PickStage { align: center middle; }
    """
    BINDINGS = [
        Binding("r", "run_route", "Run/resume D"),
        Binding("o", "run_only", "One stage"),
        Binding("f", "run_from", "From stage"),
        Binding("m", "toggle_modem", "Modem"),
        Binding("k", "kill", "Kill job"),
        Binding("w", "phone('wake')", "Wake"),
        Binding("p", "phone('park')", "Park"),
        Binding("c", "phone('record')", "Record"),
        Binding("l", "clear_log", "Clear log"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.devices: dict[str, str] = {}
        self.jobs: dict[str, Job] = {}
        self.logs: dict[str, list[str]] = {}
        self.selected: str | None = None
        self.modem = True
        self.stage_names = stages_list()

    # ---------- layout ----------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="phones", cursor_type="row", zebra_stripes=True)
            with Vertical(id="right"):
                yield DataTable(id="stages", cursor_type="none")
                yield RichLog(id="log", wrap=True, markup=False, max_lines=5000)
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        # keep references: while a dialog is open, app.query_one() searches the dialog screen, not this one
        self.w_phones = self.query_one("#phones", DataTable)
        self.w_stages = self.query_one("#stages", DataTable)
        self.w_log = self.query_one("#log", RichLog)
        self.w_status = self.query_one("#status", Static)
        self.w_phones.add_columns("serial", "mode", "stage", "job")
        self.w_stages.add_columns("stage", "status", "when", "note")
        self.set_interval(3, self.refresh_devices)
        self.refresh_devices()
        self.update_status()

    def update_status(self) -> None:
        running = sum(1 for j in self.jobs.values() if j.proc and j.proc.returncode is None)
        self.w_status.update(
            f" modem flash: {'ON (md1img-unlock)' if self.modem else 'OFF (--no-modem)'}   jobs running: {running}"
            f"   bench = this Mac (3 USB ports)")

    # ---------- device list ----------
    @work(thread=True, exclusive=True, group="scan")
    def refresh_devices(self) -> None:
        devs = scan_devices()
        self.call_from_thread(self._apply_devices, devs)

    def _apply_devices(self, devs: dict[str, str]) -> None:
        self.devices = devs
        t = self.w_phones
        serials = sorted(set(devs) | {s for s, j in self.jobs.items() if j.proc and j.proc.returncode is None})
        cur = self.selected
        t.clear()
        for s in serials:
            st = read_stages(s)
            last = ""
            for name in self.stage_names:
                if name in st:
                    last = f"{name}:{st[name]['status']}"
            job = self.jobs.get(s)
            jtxt = (job.label if job and job.proc and job.proc.returncode is None
                    else (f"exit {job.proc.returncode}" if job and job.proc else ""))
            mode = devs.get(s, "gone")
            if s in NEVER:
                mode += " (A)"
            t.add_row(s, mode, last, jtxt, key=s)
        if serials:
            if cur not in serials:
                cur = serials[0]
            t.move_cursor(row=serials.index(cur))
            self.selected = cur
        self.show_stages()

    @on(DataTable.RowHighlighted, "#phones")
    def _row(self, ev: DataTable.RowHighlighted) -> None:
        if ev.row_key is None or ev.row_key.value == self.selected:
            return
        self.selected = ev.row_key.value
        self.show_stages()
        log = self.w_log
        log.clear()
        for ln in self.logs.get(self.selected, [])[-2000:]:
            log.write(ln)

    def show_stages(self) -> None:
        s = self.w_stages
        s.clear()
        if not self.selected:
            return
        st = read_stages(self.selected)
        for name in self.stage_names:
            d = st.get(name, {})
            status = d.get("status", "")
            style = STAGE_STYLE.get(status, "")
            s.add_row(name, f"[{style}]{status or '·'}[/]" if style else status, d.get("ts", "")[5:], d.get("msg", "")[:60])

    # ---------- jobs ----------
    def _busy(self, serial: str) -> bool:
        j = self.jobs.get(serial)
        return bool(j and j.proc and j.proc.returncode is None)

    def _need(self, route: bool = False) -> str | None:
        s = self.selected
        if not s:
            self.notify("no phone selected", severity="warning")
            return None
        if self._busy(s):
            self.notify(f"{s}: a job is already running (k to kill)", severity="warning")
            return None
        if route and s in NEVER:
            self.notify(f"{s} is phone #1 (end state A): route D refuses it", severity="error")
            return None
        return s

    def _route_args(self, *extra: str) -> list[str]:
        return [str(ROUTE), *extra] + ([] if self.modem else ["--no-modem"])

    def action_run_route(self) -> None:
        s = self._need(route=True)
        if not s:
            return
        st = read_stages(s)
        resume = next((n for n in self.stage_names if st.get(n, {}).get("status") not in ("done", "skip")), None)
        if resume is None:
            self.notify(f"{s}: every stage is done")
            return
        args = self._route_args(s) if resume == self.stage_names[0] else self._route_args(s, "--from", resume)
        self.start_job(s, f"D from {resume}", args)

    def action_run_only(self) -> None:
        s = self._need(route=True)
        if s:
            self.push_screen(PickStage(f"{s}: run ONE stage", self.stage_names),
                             lambda st: st and self.start_job(s, f"D {st}", self._route_args(s, "--only", st)))

    def action_run_from(self) -> None:
        s = self._need(route=True)
        if s:
            self.push_screen(PickStage(f"{s}: run FROM stage", self.stage_names),
                             lambda st: st and self.start_job(s, f"D from {st}", self._route_args(s, "--from", st)))

    def action_phone(self, cmd: str) -> None:
        s = self._need()
        if s and self.devices.get(s) != "adb":
            self.notify(f"{s} is in '{self.devices.get(s, 'gone')}' mode: phone.sh {cmd} needs adb", severity="warning")
            return
        if s:
            self.start_job(s, cmd, [str(PHONE), cmd, s])

    def action_toggle_modem(self) -> None:
        self.modem = not self.modem
        self.update_status()

    def action_kill(self) -> None:
        s = self.selected
        j = self.jobs.get(s or "")
        if j and j.proc and j.proc.returncode is None:
            j.proc.terminate()
            self.notify(f"{s}: sent TERM to '{j.label}'")

    def action_clear_log(self) -> None:
        self.w_log.clear()

    async def action_quit(self) -> None:
        if any(self._busy(s) for s in self.jobs):
            self.notify("jobs still running — kill them first (k) or wait", severity="warning")
            return
        self.exit()

    def start_job(self, serial: str, label: str, args: list[str]) -> None:
        job = Job(serial, label)
        self.jobs[serial] = job
        self._log(serial, f"$ {' '.join(args)}")
        self.run_job(job, args)
        self.update_status()

    def _log(self, serial: str, line: str) -> None:
        self.logs.setdefault(serial, []).append(line)
        if serial == self.selected:
            self.w_log.write(line)

    @work(exclusive=False, group="jobs")
    async def run_job(self, job: Job, args: list[str]) -> None:
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        job.proc = await asyncio.create_subprocess_exec(
            *args, cwd=str(ROOT), env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        assert job.proc.stdout and job.proc.stdin
        while True:
            raw = await job.proc.stdout.readline()
            if not raw:
                break
            line = raw.decode(errors="replace").rstrip("\n")
            if line.startswith("::confirm "):
                token, _, text = line[len("::confirm "):].partition("|")
                ans = await self.push_screen_wait(ConfirmScreen(job.serial, token, text))
                await self._answer(job, "" if ans is None else ans)
                continue
            if line.startswith("::manual "):
                ans = await self.push_screen_wait(ManualScreen(job.serial, line[len("::manual "):]))
                await self._answer(job, ans)
                continue
            if line.startswith("::stage "):
                self.show_stages() if job.serial == self.selected else None
                self.refresh_devices()
                continue
            if line.startswith(">>> "):   # terminal-only prompt text (the dialog shows it)
                continue
            self._log(job.serial, line)
        rc = await job.proc.wait()
        self._log(job.serial, f"--- '{job.label}' exited {rc}")
        self.notify(f"{job.serial}: {job.label} {'OK' if rc == 0 else f'FAILED ({rc})'}",
                    severity="information" if rc == 0 else "error", timeout=10)
        self.refresh_devices()
        self.update_status()

    async def _answer(self, job: Job, text: str) -> None:
        if job.proc and job.proc.stdin and job.proc.returncode is None:
            job.proc.stdin.write((text + "\n").encode())
            await job.proc.stdin.drain()


if __name__ == "__main__":
    Bench().run()
