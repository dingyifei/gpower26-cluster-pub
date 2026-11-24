"""vegas-net headless tests: a stateful fake wpa_supplicant behind wpa_cli, fake tools, Textual pilot at 60x56."""
from conftest import BASE, FakeRunner, put
from textual.widgets import Button, Input, Static

from vegasui import wpa
from vegasui.host import Result
from vegasui.net import Net, NetRow

SIZE = (60, 56)
HDR = "bssid / frequency / signal level / flags / ssid\n"
SCAN = HDR + "".join([
    "aa:00:00:00:00:01\t5180\t-52\t[WPA2-PSK-CCMP][ESS]\tharbour-guest\n",
    "aa:00:00:00:00:02\t2437\t-61\t[ESS]\tcafe-lumen\n",
    "aa:00:00:00:00:03\t2412\t-70\t[WPA2-PSK-CCMP][ESS]\tharbour-guest\n",      # weaker duplicate
    "aa:00:00:00:00:04\t2462\t-66\t[WPA2-PSK-CCMP][ESS]\tCaf\\xc3\\xa9 \\\"Nord\\\"\n",   # UTF-8 + quotes
    "aa:00:00:00:00:05\t5745\t-80\t[SAE-CCMP][ESS]\tsae-only\n",
    "aa:00:00:00:00:06\t2412\t-40\t[WPA2-EAP-CCMP][ESS]\tcorp\n",
    "aa:00:00:00:00:07\t2412\t-75\t[ESS]\t\\x00\\x00\n",                           # hidden: left out
    "aa:00:00:00:00:08\t2412\t-77\t[WPA-PSK-TKIP][ESS]\tn8\n",
    "aa:00:00:00:00:09\t2412\t-78\t[ESS]\tn9\n",
])


class FakeWpa:
    """Just enough of wpa_supplicant: networks, select/enable, status. join_ok decides how a join ends."""

    def __init__(self, join="ok"):
        self.nets = {0: {"ssid": "harbour-guest", "flags": "[CURRENT]", "prio": 0, "psk": None}}
        self.cur = 0
        self.join = join      # 'ok' | 'wrongkey' | 'never'
        self.good = {0}       # networks that always connect when selected (the old one: going back works)
        self.saves = 0
        self.log = []

    def __call__(self, argv):
        a = argv[5:]
        self.log.append(a)
        c = a[0]
        if c == "status":
            if self.cur is None:
                return "wpa_state=SCANNING\n"
            n = self.nets[self.cur]
            return (f"bssid=aa:00:00:00:00:01\nfreq=5180\nssid={n['ssid']}\nid={self.cur}\nkey_mgmt=WPA2-PSK\n"
                    f"wpa_state=COMPLETED\nip_address=192.0.2.57\n")
        if c == "signal_poll":
            return "RSSI=-52\nLINKSPEED=433\n"
        if c == "scan":
            return "OK\n"
        if c == "scan_results":
            return SCAN
        if c == "list_networks":
            return "network id / ssid / bssid / flags\n" + "".join(
                f"{i}\t{n['ssid']}\tany\t{n['flags']}\n" for i, n in sorted(self.nets.items()))
        if c == "add_network":
            i = max(self.nets, default=-1) + 1
            self.nets[i] = {"ssid": "", "flags": "[DISABLED]", "prio": 0, "psk": None}
            return f"{i}\n"
        if c == "set_network":
            i, k, v = int(a[1]), a[2], a[3]
            if k == "ssid":
                b = bytes.fromhex(v)
                self.nets[i]["ssid"] = "".join(chr(x) if 32 <= x < 127 and chr(x) not in '\\"' else
                                               ("\\" + chr(x) if chr(x) in '\\"' else f"\\x{x:02x}") for x in b)
            elif k == "priority":
                self.nets[i]["prio"] = int(v)
            else:
                self.nets[i][k] = v
            return "OK\n"
        if c == "get_network":
            return f"{self.nets[int(a[1])]['prio']}\n"
        if c == "select_network":
            i = int(a[1])
            for j, n in self.nets.items():
                n["flags"] = "" if j == i else "[DISABLED]"
            if self.join == "ok" or i in self.good:
                self.cur = i
                self.nets[i]["flags"] = "[CURRENT]"
            elif self.join == "wrongkey":
                self.cur = None
                self.nets[i]["flags"] = "[TEMP-DISABLED]"
            else:
                self.cur = None
            return "OK\n"
        if c == "enable_network":
            for n in self.nets.values():
                n["flags"] = n["flags"].replace("[DISABLED]", "")
            if self.cur is None and self.join != "ok":
                self.cur = 0     # the old network comes back
            return "OK\n"
        if c == "remove_network":
            self.nets.pop(int(a[1]), None)
            return "OK\n"
        if c == "save_config":
            self.saves += 1
            return "OK\n"
        if c == "set":
            return "OK\n"
        return "FAIL\n"


def make(join="ok", extra=None):
    fw = FakeWpa(join)
    table = dict(BASE)
    table[("wpa_cli",)] = fw
    table.update(extra or {})
    return FakeRunner(table, installed={"qrencode"}), fw


async def settle(app, pilot):
    for _ in range(3):
        await app.workers.wait_for_complete()
        await pilot.pause()


def test_unescape_and_security():
    assert wpa.unescape("Caf\\xc3\\xa9 \\\"Nord\\\"").decode() == 'Café "Nord"'
    assert wpa.unescape("a\\\\b") == b"a\\b"
    assert wpa.security("[SAE-CCMP][ESS]") == "WPA3"
    assert wpa.security("[WPA2-PSK+SAE-CCMP][ESS]") == "WPA2"
    assert wpa.security("[WPA2-EAP-CCMP][ESS]") == "802.1X"
    assert wpa.security("[ESS]") == "open"
    assert [wpa.bars(d) for d in (-50, -60, -70, -90)] == [4, 3, 2, 1]
    # same PSK as wpa_passphrase "test" "password" (IEEE 802.11i test vector style check)
    assert wpa.psk_hex("password", b"IEEE") == "f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e"


def test_scan_results_dedup_order():
    r, _ = make()
    nets = wpa.Wpa(r).scan_results()
    names = [n["ssid"] for n in nets]
    assert names[0] == b"corp" and names.count(b"harbour-guest") == 1
    assert b"\x00\x00" not in names
    hg = next(n for n in nets if n["ssid"] == b"harbour-guest")
    assert hg["dbm"] == -52 and hg["freq"] == 5180


async def test_list_and_status(sysroot):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        rows = list(app.query(NetRow))
        assert len(rows) == 6 and len(app.nets) == 7
        assert str(app.query_one("#more", Button).label) == "▼ 1 more"
        first = [x for x in rows if x.net["ssid"] == b"harbour-guest"][0]
        assert first.saved and "saved" in str(first.render())
        cur = str(app.query_one("#cur", Static).render())
        assert "harbour-guest" in cur and "connected" in cur and "192.0.2.57 · -52 dBm · 5 GHz · WPA2" in cur
        assert "scanned just now" in str(app.query_one("#head", Static).render())
        await pilot.click("#more")
        await pilot.pause()
        assert len(app.query(NetRow)) == 7
        for w in app.query("Button, NetRow"):
            assert w.region.right <= 60
        assert not any("ccmni" in " ".join(c) for c in r.calls)


async def test_join_wpa2_hashes_and_saves(sysroot):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        row = [x for x in app.query(NetRow) if x.net["ssid"] == "Café \"Nord\"".encode()][0]
        row.action_choose()
        await pilot.pause()
        assert isinstance(app.screen.query_one("#field"), Input)
        assert r.called("pkill", "-USR2", "-x", "wvkbd-(vegas|mobintl)")
        app.screen.query_one("#field", Input).value = "short"
        await pilot.click("#ok")
        assert "8 to 63" in str(app.screen.query_one("#err", Static).render())
        app.screen.query_one("#field", Input).value = "correct horse"
        await pilot.press("enter")
        await settle(app, pilot)
        assert r.called("pkill", "-USR1", "-x", "wvkbd-(vegas|mobintl)")
        new = max(fw.nets)
        ssid = 'Café "Nord"'.encode()
        assert ["set_network", str(new), "ssid", ssid.hex()] in fw.log
        assert fw.nets[new]["psk"] == wpa.psk_hex("correct horse", ssid)
        assert not any("correct horse" in " ".join(c) for c in r.calls)     # only the hash leaves the app
        assert fw.saves == 1 and fw.cur == new
        assert "connected" in str(app.query_one("#msg", Static).render())


async def test_join_wrong_key_removes_and_reopens(sysroot):
    r, fw = make(join="wrongkey")
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        [x for x in app.query(NetRow) if x.net["ssid"] == b"n8"][0].action_choose()
        await pilot.pause()
        app.screen.query_one("#field", Input).value = "wrongpass"
        await pilot.press("enter")
        await settle(app, pilot)
        assert set(fw.nets) == {0} and fw.saves == 0 and fw.cur == 0
        assert "Wrong passphrase?" in str(app.screen.query_one(".text", Static).render()) or \
               "Wrong passphrase?" in " ".join(str(s.render()) for s in app.screen.query(Static))


async def test_join_timeout(sysroot):
    r, fw = make(join="never")
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        [x for x in app.query(NetRow) if x.net["ssid"] == b"cafe-lumen"][0].action_choose()
        await settle(app, pilot)
        assert set(fw.nets) == {0} and fw.saves == 0
        assert ["set_network", "1", "key_mgmt", "NONE"] in fw.log
        assert f"No connection after {wpa.WAIT_SECS} s" in str(app.query_one("#msg", Static).render())   # 30 s; guard at 38 s


async def test_saved_forget_and_move(sysroot):
    r, fw = make()
    fw.nets[1] = {"ssid": "other", "flags": "", "prio": 3, "psk": None}
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        [x for x in app.query(NetRow) if x.net["ssid"] == b"harbour-guest"][0].action_choose()
        await pilot.pause()
        await pilot.click("#c-up")
        await settle(app, pilot)
        assert fw.nets[0]["prio"] == 4 and fw.saves == 1
        [x for x in app.query(NetRow) if x.net["ssid"] == b"harbour-guest"][0].action_choose()
        await pilot.pause()
        await pilot.click("#c-forget")
        await settle(app, pilot)
        assert 0 not in fw.nets and fw.saves == 2


async def test_unsupported_and_mobile(sysroot):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        [x for x in app.query(NetRow) if x.net["ssid"] == b"corp"][0].action_choose()
        await pilot.pause()
        assert "not supported" in " ".join(str(s.render()) for s in app.screen.query(Static))
        await pilot.click("#c-cancel")
        await pilot.click("#mobile")
        await pilot.pause()
        assert "Reboot to Android" in " ".join(str(s.render()) for s in app.screen.query(Static))
        assert not any(c[0] in ("mmcli", "ModemManager") for c in r.calls)


async def test_hotspot_usb_on(sysroot):
    state = {"on": False}

    def usbshare(argv):
        if argv[1] == "on":
            state["on"] = True
            return Result(0, "USB sharing on via wlan0, DNS 192.168.1.1 (the computer must renew its DHCP lease)\n")
        return Result(0, "on via wlan0 (1234 bytes out)\n" if state["on"] else "off\n")
    r, fw = make(extra={("vegas-usbshare",): usbshare, ("vegas-usbshare", "status"): usbshare})
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#hotspot")
        await pilot.pause()
        assert app.screen.query_one("#c-modem", Button).has_class("dimmed")
        await pilot.click("#c-usb")
        await pilot.pause()
        await pilot.click("#c-go")
        await settle(app, pilot)
        assert r.called("vegas-usbshare", "on")
        assert "renew its DHCP lease" in str(app.query_one("#msg", Static).render())
        assert str(app.query_one("#hotspot", Button).label) == "Hotspot on · usb"


async def test_hotspot_wifi_fail_and_page(sysroot):
    calls = {"n": 0}

    def hotspot(argv):
        if argv[1] == "on":
            calls["n"] += 1
            return Result(1, "", "vegas-hotspot: uplink on 5 GHz radar channel 100: an AP cannot share it\n")
        return Result(0, "off\n")
    r, fw = make(extra={("vegas-hotspot",): hotspot, ("vegas-hotspot", "status"): hotspot})
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#hotspot")
        await pilot.pause()
        await pilot.click("#c-wifi")
        await settle(app, pilot)
        assert calls["n"] == 1                          # never retried
        assert r.called("vegas-hotspot", "on", "60")
        assert "radar channel" in str(app.query_one("#msg", Static).render())
        assert str(app.query_one("#hotspot", Button).label) == "Hotspot off"
    # now a hotspot that is on: the page shows name, passphrase and a QR code, Turn off works
    r2, _ = make(extra={("vegas-hotspot", "status"): "on: vegas-7k2, 2 device(s)\n",
                    ("vegas-hotspot", "show"): "SSID vegas-7k2\npassphrase abcDEF234ghjkmnp\n",
                    ("vegas-hotspot", "off"): "hotspot off\n",
                    ("qrencode",): "█▀▀▀█\n█▄▄▄█\n"})
    app = Net(runner=r2)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert str(app.query_one("#hotspot", Button).label) == "Hotspot on · wifi"
        await pilot.click("#hotspot")
        await settle(app, pilot)
        text = " ".join(str(s.render()) for s in app.screen.query(Static))
        assert "vegas-7k2" in text and "abcDEF234ghjkmnp" in text and "devices       2" in text and "█▀▀▀█" in text
        assert r2.called("qrencode", "-t", "UTF8", "-m", "1", "WIFI:T:WPA;S:vegas-7k2;P:abcDEF234ghjkmnp;;")
        assert app.screen.query("#add-usb") and not app.screen.query("#off-usb")
        await pilot.click("#off-wifi")
        await settle(app, pilot)
        assert r2.called("vegas-hotspot", "off")
    # both kinds on at once (page v28): label names both, the page offers both turn-offs
    r3, _ = make(extra={("vegas-hotspot", "status"): "on: vegas-7k2, 1 device(s)\n",
                        ("vegas-usbshare", "status"): "on via wlan0 (12 bytes out)\n",
                        ("vegas-hotspot", "show"): "SSID vegas-7k2\npassphrase abcDEF234ghjkmnp\n",
                        ("vegas-usbshare", "off"): "usb sharing off\n", ("qrencode",): "QR\n"})
    app = Net(runner=r3)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert str(app.query_one("#hotspot", Button).label) == "Hotspot on · wifi + usb"
        await pilot.click("#hotspot")
        await settle(app, pilot)
        assert "on via wlan0" in " ".join(str(s.render()) for s in app.screen.query(Static))
        await pilot.click("#off-usb")
        await settle(app, pilot)
        assert r3.called("vegas-usbshare", "off") and not r3.called("vegas-hotspot", "off")


async def test_signin_check(sysroot):
    r, fw = make(extra={("curl",): "302", ("networkctl",): "  Captive Portal: http://portal.example/login\n"})
    r.installed.add("w3m")
    r.table[("tmux", "new-window")] = ""
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#signin")
        await settle(app, pilot)
        await pilot.click("#c-w3m")
        assert r.called("tmux", "new-window", "-t", "main", "-n", "signin", "--", "w3m", "http://portal.example/login")
    # a hostile portal URL from the network never reaches a shell unquoted (designer security point)
    r, fw = make(extra={("curl",): "302",
                        ("networkctl",): "  Captive Portal: http://evil.example/a';reboot;'$(id)`x`,b{c}\n"})
    r.installed.add("firefox-esr")
    r.table[("swaymsg", "exec")] = ""
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#signin")
        await settle(app, pilot)
        await pilot.click("#c-firefox")
        (call,) = r.called("swaymsg", "exec")
        assert call[2] == "choom -n 0 -- firefox-esr 'http://evil.example/a%27%3Breboot%3B%27%24(id)%60x%60%2Cb%7Bc%7D'"

    r, fw = make(extra={("curl",): "204"})
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#signin")
        await settle(app, pilot)
        assert "Online" in str(app.query_one("#msg", Static).render())


async def test_hidden_network_and_new_hotspot_pass(sysroot):
    r, fw = make()
    put(sysroot, "/etc/vegas/hotspot.conf", "SSID=vegas-7k2\nPSK=oldoldoldold\n")
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#moreopts")
        await pilot.pause()
        r.table[("vegas-hotspot", "newpass")] = "new passphrase set\n"
        await pilot.click("#c-newpass")
        await settle(app, pilot)
        # B7: vegas-hotspot owns the file; vegas-net only calls its newpass verb and never shows a passphrase
        assert r.called("vegas-hotspot", "newpass")
        assert (sysroot / "etc/vegas/hotspot.conf").read_text() == "SSID=vegas-7k2\nPSK=oldoldoldold\n"
        assert "New passphrase set" in str(app.query_one("#msg", Static).render())
        await pilot.click("#moreopts")
        await pilot.pause()
        await pilot.click("#c-hidden")
        await pilot.pause()
        app.screen.query_one("#field", Input).value = "secret net"
        await pilot.press("enter")
        await pilot.pause()
        app.screen.query_one("#field", Input).value = "hunter22hunter"
        await pilot.press("enter")
        await settle(app, pilot)
        new = max(fw.nets)
        assert ["set_network", str(new), "scan_ssid", "1"] in fw.log
        assert ["set_network", str(new), "ssid", b"secret net".hex()] in fw.log


async def test_keys_only_join_saved(sysroot):
    """Three keys: Down moves the highlight to the first row, Enter opens it, Down/Enter picks Connect."""
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("down")
        assert (sysroot / "run/vegas-ui/net").read_text().strip() == "highlight=1"
        while not (isinstance(app.focused, NetRow) and app.focused.net["ssid"] == b"harbour-guest"):
            await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down")          # focus the first dialog button (Connect)
        assert app.focused.id == "c-connect"
        await pilot.press("enter")
        await settle(app, pilot)
        assert ["select_network", "0"] in fw.log and ["enable_network", "all"] in fw.log


def test_safe_url():
    from vegasui.net import safe_url
    assert safe_url("https://p.example/x?a=1&b=2#f") == "https://p.example/x?a=1&b=2#f"
    assert safe_url("file:///etc/shadow") is None
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("http:///nohost") is None
    assert safe_url("http://a.example/ x") is None
    assert safe_url("http://a.example/\u00e9") == "http://a.example/%C3%A9"


async def test_review_repaint_dialog_markup(sysroot):
    """Review fixes: two empty scans in a row (no DuplicateIds on #empty); status refresh and the scan-age timer
    while a dialog is open; a portal URL / SSID with markup characters shown as plain text."""
    from vegasui.tui import AskScreen, ChoiceScreen
    r, w = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await app._paint_list()
        app.nets = []
        await app._paint_list()
        await app._paint_list()
        assert len(app.query("#empty")) == 1
        app.push_screen(AskScreen("x", password=True))
        await pilot.pause()
        app.refresh_status()
        app._age()
        await settle(app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        url = "http://portal.example/?a=[/b]&c=[@click=app.quit]x[/]"
        app.push_screen(ChoiceScreen("Sign-in page", [("cancel", "OK")], url))
        await pilot.pause()
        assert any(url in str(s.render()) for s in app.screen.query(Static))


# --- review 2026-11-23: network-controlled text must not reach the root terminal as control sequences ----------------
HOSTILE = "\\x1b[2J\\x1b[HX\\x1b]2;PWNED\\x07\\xc2\\x9b31m\\e[31mRED"   # wpa_cli's escaped form (\\xNN, \\e)
CTRL = [chr(c) for c in list(range(0x20)) + [0x7f] + list(range(0x80, 0xa0))]


def test_show_escapes_control_characters():
    raw = wpa.unescape(HOSTILE)
    assert b"\x1b" in raw and b"\x07" in raw              # matching / wpa_cli hex keep the real bytes
    s = wpa.show(raw)
    assert not any(c in s for c in CTRL), repr(s)
    assert "\\x1b[2J" in s and "\\x07" in s and "\\x9b31m" in s and "RED" in s
    assert wpa.show("Café \"Nord\"".encode()) == 'Café "Nord"'   # ordinary names unchanged
    assert wpa.printable("a‮b c") == "a\\u202eb\\u2028c"   # bidi override / line separator


async def test_hostile_ssid_and_portal_render_without_control_bytes(sysroot):
    from vegasui.tui import ChoiceScreen
    r, fw = make(extra={("curl",): "302", ("networkctl",): "  Captive Portal: http://p.example/\x1b]2;PWNED\x07x\n"})
    r.installed.add("w3m")
    fw.nets[0]["ssid"] = HOSTILE                            # the current network (status, saved list)
    global SCAN
    old, SCAN = SCAN, SCAN + f"aa:00:00:00:00:0a\t2412\t-41\t[ESS]\t{HOSTILE}\n"   # strongest: first row
    try:
        app = Net(runner=r)
        async with app.run_test(size=SIZE) as pilot:
            await settle(app, pilot)
            texts = [str(w.render()) for w in app.query("NetRow, #cur, #msg")]
            assert any("PWNED" in t for t in texts)          # it is shown, escaped
            for t in texts:                                  # (\n: the widgets' own line breaks)
                assert not any(c in t for c in CTRL if c != "\n"), repr(t)
            await pilot.click("#signin")
            await settle(app, pilot)
            assert isinstance(app.screen, ChoiceScreen)
            shown = [str(s.render()) for s in app.screen.query(Static)]
            assert any("PWNED" in t for t in shown)
            for t in shown:
                assert "\x1b" not in t and "\x07" not in t, repr(t)
    finally:
        SCAN = old
