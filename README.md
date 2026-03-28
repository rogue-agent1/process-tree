# proc_tree

Process tree viewer with resource usage, port listing, and process search/kill.

## Usage

```bash
python3 proc_tree.py tree              # Full process tree
python3 proc_tree.py tree --pid 1234   # Subtree from PID
python3 proc_tree.py top --count 10    # Top CPU consumers
python3 proc_tree.py top --sort mem    # Top memory consumers
python3 proc_tree.py find "python"     # Find processes
python3 proc_tree.py ports             # Listening ports
python3 proc_tree.py kill --name "node" --dry-run
```

## Zero dependencies. Single file. Python 3.8+.
