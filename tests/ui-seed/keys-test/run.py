# Loads vegas-keys as a module with short timers and starts it (test only).
import importlib.machinery, importlib.util, sys
p = sys.argv[1]
loader = importlib.machinery.SourceFileLoader("vk", p)
spec = importlib.util.spec_from_loader("vk", loader); vk = importlib.util.module_from_spec(spec); loader.exec_module(vk)
vk.T_DIM, vk.T_OFF, vk.T_AWAY_DIM, vk.T_AWAY_OFF, vk.T_GLANCE, vk.T_PIN = 2, 3, 2, 3, 2, 3
import threading, os
threading.excepthook = vk._die
vk.Keys().main()
