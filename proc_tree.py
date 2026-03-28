#!/usr/bin/env python3
"""proc_tree — Process tree viewer with resource usage.

Usage:
    proc_tree.py tree
    proc_tree.py tree --pid 1234
    proc_tree.py top --count 10
    proc_tree.py find "python"
    proc_tree.py ports
    proc_tree.py kill --name "node" --dry-run
"""

import sys
import os
import re
import json
import signal
import argparse
import subprocess
from collections import defaultdict


def get_processes():
    """Get all processes with details."""
    result = subprocess.run(
        ['ps', '-eo', 'pid,ppid,user,%cpu,%mem,rss,comm,args'],
        capture_output=True, text=True
    )
    procs = []
    for line in result.stdout.strip().split('\n')[1:]:
        parts = line.split(None, 7)
        if len(parts) >= 7:
            procs.append({
                'pid': int(parts[0]),
                'ppid': int(parts[1]),
                'user': parts[2],
                'cpu': float(parts[3]),
                'mem': float(parts[4]),
                'rss': int(parts[5]),
                'comm': parts[6],
                'args': parts[7] if len(parts) > 7 else parts[6],
            })
    return procs


def build_tree(procs, root_pid=None):
    """Build process tree structure."""
    children = defaultdict(list)
    by_pid = {}
    for p in procs:
        children[p['ppid']].append(p)
        by_pid[p['pid']] = p
    return children, by_pid


def print_tree(children, by_pid, pid, prefix='', is_last=True, depth=0, max_depth=10):
    """Print tree recursively."""
    if depth > max_depth:
        return
    
    proc = by_pid.get(pid)
    if not proc:
        return
    
    connector = '└── ' if is_last else '├── '
    if depth == 0:
        connector = ''
    
    name = proc['comm']
    cpu = proc['cpu']
    mem_mb = proc['rss'] / 1024
    
    extras = []
    if cpu > 0.1:
        extras.append(f'{cpu:.1f}%cpu')
    if mem_mb > 10:
        extras.append(f'{mem_mb:.0f}MB')
    
    extra_str = f' ({", ".join(extras)})' if extras else ''
    print(f'{prefix}{connector}{pid} {name}{extra_str}')
    
    kids = sorted(children.get(pid, []), key=lambda p: p['pid'])
    for i, child in enumerate(kids):
        is_last_child = (i == len(kids) - 1)
        new_prefix = prefix + ('    ' if is_last or depth == 0 else '│   ')
        print_tree(children, by_pid, child['pid'], new_prefix, is_last_child, depth + 1, max_depth)


def cmd_tree(args):
    procs = get_processes()
    children, by_pid = build_tree(procs)
    
    if args.pid:
        if args.pid in by_pid:
            print_tree(children, by_pid, args.pid, max_depth=args.depth)
        else:
            print(f'PID {args.pid} not found')
    else:
        # Find root processes (ppid=0 or ppid=1 or ppid not in by_pid)
        roots = set()
        for p in procs:
            if p['ppid'] == 0 or p['ppid'] not in by_pid:
                roots.add(p['pid'])
        
        for pid in sorted(roots):
            print_tree(children, by_pid, pid, max_depth=args.depth)
            print()


def cmd_top(args):
    procs = get_processes()
    
    if args.sort == 'cpu':
        procs.sort(key=lambda p: p['cpu'], reverse=True)
    elif args.sort == 'mem':
        procs.sort(key=lambda p: p['rss'], reverse=True)
    
    print(f'{"PID":>7} {"USER":<10} {"CPU%":>6} {"MEM%":>6} {"RSS":>8} {"COMMAND":<30}')
    print('-' * 75)
    for p in procs[:args.count]:
        rss = f'{p["rss"]/1024:.0f}MB' if p['rss'] > 1024 else f'{p["rss"]}KB'
        print(f'{p["pid"]:>7} {p["user"]:<10} {p["cpu"]:>6.1f} {p["mem"]:>6.1f} {rss:>8} {p["comm"]:<30}')


def cmd_find(args):
    procs = get_processes()
    pattern = re.compile(args.pattern, re.IGNORECASE)
    
    matches = [p for p in procs if pattern.search(p['comm']) or pattern.search(p['args'])]
    
    if not matches:
        print(f'No processes matching "{args.pattern}"')
        return
    
    print(f'Found {len(matches)} processes:')
    for p in matches:
        rss = f'{p["rss"]/1024:.0f}MB' if p['rss'] > 1024 else f'{p["rss"]}KB'
        print(f'  {p["pid"]:>7} {p["user"]:<10} {p["cpu"]:>5.1f}% {rss:>8} {p["args"][:80]}')


def cmd_ports(args):
    """Show processes listening on ports."""
    try:
        result = subprocess.run(
            ['/usr/sbin/lsof', '-iTCP', '-sTCP:LISTEN', '-nP'],
            capture_output=True, text=True, timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return
    
    if not result.stdout:
        print('No listening ports found')
        return
    
    lines = result.stdout.strip().split('\n')
    print(f'{"COMMAND":<20} {"PID":>7} {"USER":<10} {"PORT":<15}')
    print('-' * 55)
    
    seen = set()
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 9:
            cmd, pid, user = parts[0], parts[1], parts[2]
            addr = parts[8]
            key = f'{pid}:{addr}'
            if key not in seen:
                seen.add(key)
                port = addr.split(':')[-1] if ':' in addr else addr
                print(f'{cmd:<20} {pid:>7} {user:<10} {port:<15}')


def cmd_kill(args):
    procs = get_processes()
    pattern = re.compile(args.name, re.IGNORECASE)
    matches = [p for p in procs if pattern.search(p['comm']) and p['pid'] != os.getpid()]
    
    if not matches:
        print(f'No processes matching "{args.name}"')
        return
    
    sig = getattr(signal, f'SIG{args.signal.upper()}', signal.SIGTERM)
    
    for p in matches:
        if args.dry_run:
            print(f'  [DRY RUN] Would kill {p["pid"]} ({p["comm"]})')
        else:
            try:
                os.kill(p['pid'], sig)
                print(f'  Killed {p["pid"]} ({p["comm"]})')
            except ProcessLookupError:
                print(f'  {p["pid"]} already gone')
            except PermissionError:
                print(f'  {p["pid"]} permission denied')


def main():
    p = argparse.ArgumentParser(description='Process tree viewer')
    p.add_argument('--json', action='store_true')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('tree', help='Show process tree')
    s.add_argument('--pid', type=int)
    s.add_argument('--depth', type=int, default=10)
    s.set_defaults(func=cmd_tree)

    s = sub.add_parser('top', help='Top processes by resource')
    s.add_argument('--count', type=int, default=10)
    s.add_argument('--sort', choices=['cpu', 'mem'], default='cpu')
    s.set_defaults(func=cmd_top)

    s = sub.add_parser('find', help='Find processes by name/pattern')
    s.add_argument('pattern')
    s.set_defaults(func=cmd_find)

    s = sub.add_parser('ports', help='Show listening ports')
    s.set_defaults(func=cmd_ports)

    s = sub.add_parser('kill', help='Kill processes by name')
    s.add_argument('--name', required=True)
    s.add_argument('--signal', default='TERM')
    s.add_argument('--dry-run', action='store_true')
    s.set_defaults(func=cmd_kill)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
