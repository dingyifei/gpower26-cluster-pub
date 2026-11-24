import asyncio, os, sys, tempfile
from pathlib import Path
import conftest
from test_net import make
from vegasui.net import Net, NetRow
root=tempfile.mkdtemp(); os.environ["VEGAS_SYSROOT"]=root; conftest.make_tree(Path(root))
async def m():
    a=Net(runner=make()[0])
    async with a.run_test(size=(60,56)) as p:
        for _ in range(3):
            await a.workers.wait_for_complete(); await p.pause()
        for sel in ("#head",):
            w=a.query_one(sel); print(repr(w.render_line(0).text))
        r=list(a.query(NetRow))[1]
        for i in range(3): print(repr(r.render_line(i).text))
asyncio.run(m())
