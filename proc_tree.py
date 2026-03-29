#!/usr/bin/env python3
"""Process tree — fork, exec, wait, signals simulator."""
import sys, random

class Process:
    _pid = 0
    def __init__(self, name, parent=None):
        Process._pid += 1; self.pid = Process._pid
        self.name = name; self.parent = parent
        self.children = []; self.state = "running"; self.exit_code = None
    def fork(self, name):
        child = Process(name, self); self.children.append(child); return child
    def exit(self, code=0):
        self.state = "zombie"; self.exit_code = code
    def wait(self):
        zombies = [c for c in self.children if c.state == "zombie"]
        if zombies:
            z = zombies[0]; z.state = "reaped"; self.children.remove(z)
            return z.pid, z.exit_code
        return None, None
    def kill(self, child_pid):
        for c in self.children:
            if c.pid == child_pid: c.exit(137); return True
        return False

def print_tree(proc, indent=0):
    prefix = "  " * indent
    state = f"[{proc.state}]" if proc.state != "running" else ""
    print(f"{prefix}PID {proc.pid}: {proc.name} {state}")
    for c in proc.children: print_tree(c, indent + 1)

if __name__ == "__main__":
    init = Process("init")
    shell = init.fork("bash")
    vim = shell.fork("vim")
    ls = shell.fork("ls")
    daemon = init.fork("sshd")
    worker = daemon.fork("sshd-worker")
    print("Process tree:"); print_tree(init)
    ls.exit(0); vim.exit(0)
    pid, code = shell.wait()
    print(f"\nshell waited: PID {pid} exited with {code}")
    init.kill(daemon.pid)
    print("\nAfter kill:"); print_tree(init)
