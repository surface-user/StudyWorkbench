import sys

if __name__ == "__main__":
    # PyInstaller ignores PYTHONUTF8/PYTHONIOENCODING in its isolated interpreter.
    # The desktop pipe contract is UTF-8, including errors and Chinese data paths.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    # Keep the disposable native launcher outside the HTTP app's imports and threads.
    if len(sys.argv) == 5 and sys.argv[1] == '--launch-office':
        from pathlib import Path

        from study_workbench.office_runtime import launch_office
        raise SystemExit(launch_office(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
    from study_workbench.__main__ import main
    main()
