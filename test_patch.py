import subprocess
import sys

# Apply patch
_orig_popen = subprocess.Popen
def _patched_popen(*args, **kwargs):
    print("PATCHED POPEN CALLED!")
    if 'creationflags' not in kwargs:
        kwargs['creationflags'] = 0x08000000
    return _orig_popen(*args, **kwargs)
subprocess.Popen = _patched_popen

# Test
subprocess.run(["cmd.exe", "/c", "echo hello"])
