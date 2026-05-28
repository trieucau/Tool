import subprocess
import sys

_orig_popen = subprocess.Popen
def _patched_popen(*args, **kwargs):
    print("PATCHED POPEN CALLED FROM RUN!")
    if 'creationflags' not in kwargs:
        kwargs['creationflags'] = 0x08000000
    return _orig_popen(*args, **kwargs)
subprocess.Popen = _patched_popen

subprocess.run(["cmd.exe", "/c", "echo inside run"])
