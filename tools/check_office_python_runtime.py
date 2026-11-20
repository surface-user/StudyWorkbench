"""Run the same fixed Python-entry helper from source or a source-matched frozen backend."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from prepare_java_runtime import no_links  # noqa: E402
from study_workbench.office_python_probe import PROBE_SCRIPT, RUNTIME_SHA256  # noqa: E402
from study_workbench.office_runtime import WindowsProcessJob  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--office', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    office, output = args.office.absolute(), args.output.absolute()
    no_links(office)
    no_links(output.parent)
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(office.resolve()):
        raise ValueError('Output must be new and outside the Office component')
    executable_hash, source_match = None, None
    if args.exe:
        executable = args.exe.absolute()
        no_links(executable)
        if not executable.is_file() or executable.stat().st_size > 128 * 1024 * 1024:
            raise ValueError('Frozen backend input exceeds the supported file budget')
        executable_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
        check = Path(__file__).with_name('check_frozen_sources.py')
        checked = subprocess.run([sys.executable, str(check), '--exe', str(executable)],
                                 capture_output=True, encoding='utf-8', check=True, timeout=60)
        if len(checked.stdout) + len(checked.stderr) > 4096:
            raise ValueError('Frozen source-check output exceeds budget')
        source_match = checked.stdout.strip()
        prefix = [str(executable)]
    else:
        prefix = [sys.executable, '-B', '-m', 'study_workbench']
    output.mkdir()
    for name in ('tmp', 'profile'):
        (output / name).mkdir()
    environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    environment.update(PATH=str(Path(sys.executable).parent) + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32'),
        TEMP=str(output / 'tmp'), TMP=str(output / 'tmp'), APPDATA=str(output / 'profile'),
        LOCALAPPDATA=str(output / 'profile'), USERPROFILE=str(output / 'profile'))
    if not args.exe:
        environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'backend')
    command = prefix + ['--probe-office-python', str(office), str(output / 'worker')]
    job, process = WindowsProcessJob(), None
    try:
        process = job.start(command, output, environment)
        code = process.wait(600)
        if code != 0:
            raise ValueError('Python runtime helper failed; original output retained: ' + str(code))
        path = output / 'worker/report.json'
        if not path.is_file() or path.stat().st_size > 65536:
            raise ValueError('Missing bounded helper report')
        report = json.loads(path.read_text('utf-8'))
        if (report['component_inventory_sha256'] != RUNTIME_SHA256
                or report['probe_script_sha256'] != hashlib.sha256(PROBE_SCRIPT.encode('utf-8')).hexdigest()
                or report['mode'] != ('frozen' if args.exe else 'source')
                or [row['image'] for row in report['entries']] != ['python.exe', 'pythonw.exe']
                or any(row['exit_code'] != 0 for row in report['entries'])
                or report['component_bytes_preserved'] is not True):
            raise ValueError('Helper report identity differs from current fixed probe')
        if args.exe and hashlib.sha256(executable.read_bytes()).hexdigest() != executable_hash:
            raise ValueError('Frozen backend changed during validation')
        result = dict(mode=report['mode'], entries=2, component_inventory_sha256=RUNTIME_SHA256,
            frozen_executable_sha256=executable_hash, frozen_source_match=source_match,
            helper_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            helper_launcher_pid=process.pid, report=report)
        (output / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                           encoding='utf-8', newline='\n')
        print(json.dumps(dict(mode=result['mode'], entries=2, component_inventory_sha256=RUNTIME_SHA256)))
    finally:
        job.close()
        if process is not None:
            try:
                process.wait(10)
            finally:
                process.close()


if __name__ == '__main__':
    main()
