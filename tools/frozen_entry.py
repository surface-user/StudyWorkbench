import sys

from study_workbench.__main__ import main

if __name__ == "__main__":
    # PyInstaller ignores PYTHONUTF8/PYTHONIOENCODING in its isolated interpreter.
    # The desktop pipe contract is UTF-8, including errors and Chinese data paths.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
