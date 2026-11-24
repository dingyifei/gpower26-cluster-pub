"""Render SVG screenshots of Home / Network with fake data (python3 snap.py <outdir>)."""
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import conftest
from conftest import BASE, FakeRunner, put
from test_net import make
from vegasui.home import Home
from vegasui.net import Net, NetRow

out = sys.argv[1]
root = tempfile.mkdtemp()
os.environ["VEGAS_SYSROOT"] = root
from pathlib import Path
conftest.make_tree(Path(root))

async def shoot(app, size, name, act=None):
    async with app.run_test(size=size) as pilot:
        for _ in range(3):
            await app.workers.wait_for_complete(); await pilot.pause()
        if act:
            await act(app, pilot)
            for _ in range(3):
                await app.workers.wait_for_complete(); await pilot.pause()
        app.save_screenshot(f"{name}.svg", out)

async def main():
    r = FakeRunner(BASE)
    await shoot(Home(runner=r), (60, 56), "home")
    await shoot(Home(runner=r), (60, 37), "home-kbd", lambda a, p: p.press("down", "down", "down"))
    await shoot(Home(runner=r), (130, 30), "home-wide")
    r, fw = make()
    await shoot(Net(runner=r), (60, 56), "net")
    async def pw(a, p):
        [x for x in a.query(NetRow) if x.net["ssid"] == b"n8"][0].action_choose(); await p.pause()
    await shoot(Net(runner=r), (60, 37), "net-pass", pw)
    r, fw = make(extra={("vegas-hotspot", "status"): "on: vegas-7k2, 2 device(s)\n",
                        ("vegas-hotspot", "show"): "SSID vegas-7k2\npassphrase abcDEF234ghjkmnp\n"})
    r.table[("qrencode",)] = os.popen("qrencode -t UTF8 -m 1 'WIFI:T:WPA;S:vegas-7k2;P:abcDEF234ghjkmnp;;'").read()
    async def hs(a, p):
        await p.click("#hotspot")
    await shoot(Net(runner=r), (60, 56), "net-hotspot", hs)
    await shoot(Net(runner=make()[0]), (130, 30), "net-wide")

asyncio.run(main())
