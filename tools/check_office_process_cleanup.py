"""Exercise real native timeout/cancellation after one complete runtime verification."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench import office_runtime  # noqa: E402


def main():
    import _winapi
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()
    runtime = office_runtime.OfficeRuntime(args.runtime.resolve())
    runtime.verify(lambda: None)
    # This probe isolates native cleanup timing; production still verifies every conversion.
    runtime.verify = lambda checkpoint: checkpoint()
    handles = []
    original_job = office_runtime.WindowsProcessJob

    class ObservedJob(original_job):
        def start(self, command, directory, environment):
            process = super().start(command, directory, environment)
            handles.append(_winapi.OpenProcess(0x100000, False, process.pid))
            return process

    office_runtime.WindowsProcessJob = ObservedJob
    try:
        for mode in ['timeout', 'cancel']:
            directory = root / mode
            directory.mkdir()
            source = directory / ('source' + args.source.suffix)
            original = args.source.read_bytes()
            source.write_bytes(original)
            launched = None

            def checkpoint():
                nonlocal launched
                if (directory / 'profile').exists():
                    launched = launched or time.monotonic()
                    if mode == 'cancel' and time.monotonic() - launched > .3:
                        raise office_runtime.ConversionStopped()

            expected = ValueError if mode == 'timeout' else office_runtime.ConversionStopped
            try:
                runtime.convert(source, directory, checkpoint, timeout=.01 if mode == 'timeout' else 90)
                raise AssertionError('Expected native interruption')
            except expected as error:
                if mode == 'timeout':
                    assert '90' in str(error), str(error)
            assert source.read_bytes() == original
            assert handles and _winapi.WaitForSingleObject(handles[-1], 10000) == 0
            print(json.dumps(dict(mode=mode, process_exited=True, source_preserved=True)), flush=True)
    finally:
        office_runtime.WindowsProcessJob = original_job
        for handle in handles:
            _winapi.CloseHandle(handle)


if __name__ == '__main__':
    main()
