import multiprocessing
import numpy as np
import psutil
import time
from multiprocessing import cpu_count, Process, Queue

def kill_proc_tree(pid, include_parent = True, timeout = None, on_terminate=None):

    """Kill a process tree (including grandchildren).
    "on_terminate", if specified, is a callabck function which is
    called as soon as a child terminates.
    """

    parent = psutil.Process(pid)
    children = parent.children(recursive=True)

    if include_parent:
        children.append(parent)

    for p in children:

        p.terminate()
        gone, alive = psutil.wait_procs(children, timeout = timeout, callback = on_terminate)

        if alive:
            
            for p in alive:
                print("process survived SIGTERM; trying SIGKILL")
                p.kill()

            gone, alive = psutil.wait_procs(alive, timeout = timeout, callback = on_terminate)

            if alive:
                for p in alive:
                    print("process survived SIGKILL; kill it by hand")
                    
