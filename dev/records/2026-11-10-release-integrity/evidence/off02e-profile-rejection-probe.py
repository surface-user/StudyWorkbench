import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from study_workbench.office_inputs import validate_office
from study_workbench.office_runtime import OfficeRuntime, profile_configuration

runtime = OfficeRuntime(Path(r'D:\computer_work\project\StudyWorkbench\.local\release-tools\libreoffice-java-26.8.1-21.0.13'))
directory = ROOT / '.local/changed-profile01'
(directory / 'profile/user').mkdir(parents=True)
for name in ('output', 'tmp'):
    (directory / name).mkdir()
source = directory / 'source.docx'
source.write_bytes((ROOT / 'contracts/samples/original-study.docx').read_bytes())
before = hashlib.sha256(source.read_bytes()).hexdigest()
configuration = profile_configuration(validate_office(source.read_bytes(), '.docx'))
configuration = configuration.replace('<value>3</value>', '<value>0</value>')
(directory / 'profile/user/registrymodifications.xcu').write_text(configuration, encoding='utf-8')
environment = runtime.environment(directory)
environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
result = subprocess.run([str(ROOT / 'dist/study_backend/study_backend.exe'), '--launch-office',
                         str(runtime.root), str(directory), '.docx'], cwd=directory, env=environment,
                        capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
stderr = result.stderr.decode('utf-8', errors='replace')
assert result.returncode != 0 and '转换配置已变化' in stderr, (result.returncode, stderr)
assert not any((directory / 'output').iterdir())
assert hashlib.sha256(source.read_bytes()).hexdigest() == before
summary = {'returncode': result.returncode, 'profile_change_rejected': True, 'output_empty': True,
           'source_sha256': before, 'stderr': stderr}
(ROOT / 'artifacts/off02e/changed-profile01.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in summary.items() if key != 'stderr'}))
