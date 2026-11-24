"""Minimal sway IPC client (no swaymsg fork): query outputs/workspaces, run harmless commands, wait for events.

D10: this module must never be used to send 'exit' or 'reload', or to switch an output off; run() refuses them.
The socket is $SWAYSOCK, else the first /run/sway/sway-ipc.*.sock (sway runs as root, XDG_RUNTIME_DIR=/run/sway).
"""
import glob
import json
import os
import re
import socket
import struct

MAGIC = b"i3-ipc"
RUN_COMMAND, GET_WORKSPACES, SUBSCRIBE, GET_OUTPUTS = 0, 1, 2, 3
FORBIDDEN = re.compile(r"\b(exit|reload)\b|\b(dpms|power)\s+(off|toggle)\b|\b(disable|toggle)\b", re.I)


def sock_path():
    s = os.environ.get("SWAYSOCK")
    if s and os.path.exists(s):
        return s
    socks = sorted(glob.glob("/run/sway/sway-ipc.*.sock"))
    return socks[0] if socks else None


class Sway:
    def __init__(self, timeout=2.0):
        path = sock_path()
        if not path:
            raise OSError("sway is not running")
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.settimeout(timeout)
        self.s.connect(path)

    def close(self):
        self.s.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise OSError("sway closed the IPC socket")
            buf += chunk
        return buf

    def send(self, kind, payload=""):
        data = payload.encode()
        self.s.sendall(MAGIC + struct.pack("=II", len(data), kind) + data)
        return self.read()[1]

    def read(self):
        """(type, decoded JSON) of the next message (a reply or an event)."""
        head = self._recv(14)
        if head[:6] != MAGIC:
            raise OSError("bad IPC reply")
        n, kind = struct.unpack("=II", head[6:])
        return kind, json.loads(self._recv(n) or b"null")

    def run(self, cmd):
        """Run a sway command such as 'workspace number 1'. Refuses exit/reload/output-off (D10)."""
        if FORBIDDEN.search(cmd):
            raise ValueError("refused (D10): %r" % cmd)
        return self.send(RUN_COMMAND, cmd)


def outputs():
    with Sway() as s:
        return s.send(GET_OUTPUTS)


def output_width(name="DSI-1", default=360):
    """Logical width of the panel (360 upright, 796 rotated), or default when sway cannot be asked.
    Falls back to the first active output when there is no DSI-1 (the VM's headless sway test)."""
    try:
        act = [o for o in outputs() if o.get("active")]
        for o in sorted(act, key=lambda o: o.get("name") != name):
            return int(o["rect"]["width"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return default


def focused_workspace():
    try:
        with Sway() as s:
            for w in s.send(GET_WORKSPACES):
                if w.get("focused"):
                    return w.get("num")
    except (OSError, ValueError):
        pass
    return None


def command(cmd):
    try:
        with Sway() as s:
            return s.run(cmd)
    except (OSError, ValueError):
        return None
