import asyncio
from rich.text import Text
from textual.app import App
from textual.widgets import Static
class W(Static):
    def render(self):
        t=Text(); t.append("AB", style="bold"); t.append(" cd", style="#7F8B99"); t.append("   ef"); t.append("\n   gh", style="#7F8B99"); return t
class A(App):
    def compose(self): yield W()
async def m():
    a=A()
    async with a.run_test(size=(30,4)) as p:
        await p.pause()
        print(repr([ "".join(s.text for s in l) for l in a.screen._compositor.render_update(full=True).lines] if hasattr(a.screen._compositor.render_update(full=True),'lines') else a.export_screenshot()[:0]))
        w=a.query_one(W); print([str(l.text) for l in [w.render_line(0), w.render_line(1)]])
asyncio.run(m())
