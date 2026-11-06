"""Generate only self-authored Calc fixtures, then check the inert source/frozen viewer."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench import office_runtime  # noqa: E402

FODS = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2"
 office:mimetype="application/vnd.oasis.opendocument.spreadsheet" office:version="1.3">
<office:body><office:spreadsheet>
<table:table table:name="中文成绩">
<table:table-row><table:table-cell office:value-type="string"><text:p>科目</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>分数</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>数学</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="85"><text:p>85</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>英语</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="90"><text:p>90</text:p></table:table-cell></table:table-row>
<table:table-row><table:table-cell office:value-type="string"><text:p>合计</text:p></table:table-cell><table:table-cell table:formula="of:=SUM([.B2:.B3])" office:value-type="float" office:value="175"><text:p>175</text:p></table:table-cell></table:table-row>
</table:table>
<table:table table:name="日期与字面">
<table:table-row><table:table-cell office:value-type="date" office:date-value="2026-11-05"><text:p>2026-11-05</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>&lt;script&gt;不执行&lt;/script&gt;</text:p></table:table-cell><table:table-cell office:value-type="boolean" office:boolean-value="true"><text:p>TRUE</text:p></table:table-cell></table:table-row>
</table:table>
</office:spreadsheet></office:body></office:document>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()  # Never reuse or erase an earlier run.
    source = root / '自编课程.fods'
    source.write_bytes(FODS.encode('utf-8'))
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    runtime = office_runtime.OfficeRuntime(args.runtime.resolve())
    runtime.verify(lambda: None)
    profile, output, temporary = root / 'profile', root / 'output', root / 'tmp'
    (profile / 'user').mkdir(parents=True)
    output.mkdir()
    temporary.mkdir()
    (profile / 'user/registrymodifications.xcu').write_text(office_runtime.PROFILE, encoding='utf-8')
    environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    environment.update(PATH=str(runtime.executable.parent) + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32'),
                       TEMP=str(temporary), TMP=str(temporary), APPDATA=str(profile), LOCALAPPDATA=str(profile),
                       USERPROFILE=str(profile), SAL_DISABLESKIA='1', SAL_DISABLE_OPENCL='1')
    command = [str(runtime.executable), '-env:UserInstallation=' + profile.as_uri(), '--headless', '--nologo',
               '--nodefault', '--norestore', '--quickstart=no', '--convert-to', 'xlsx:Calc MS Excel 2007 XML',
               '--outdir', str(output), str(source)]
    job, process = office_runtime.WindowsProcessJob(), None
    try:
        process = job.start(command, root, environment)
        deadline = time.monotonic() + 90
        while process.poll() is None:
            if time.monotonic() > deadline:
                raise RuntimeError('Self-authored fixture generation timed out')
            time.sleep(.1)
        assert process.returncode == 0
    finally:
        job.close()
        if process is not None:
            process.wait(10)
            process.close()
    sample = output / '自编课程.xlsx'
    raw = sample.read_bytes()
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.exe:
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
    result = subprocess.run(command + ['--view-document', 'xlsx'], input=b'{}\n' + raw,
                            cwd=root if args.exe else Path(__file__).resolve().parents[1] / 'backend', env=env,
                            capture_output=True, timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0
    value = json.loads(result.stdout)
    assert 'error' not in value, value
    assert value['renderer_version'] == 'xlsx-values-v1'
    assert [s['name'] for s in value['sheets']] == ['中文成绩', '日期与字面']
    first, second = [{c['address']: c for c in sheet['cells']} for sheet in value['sheets']]
    assert first['A2']['value'] == '数学' and Decimal(first['B2']['value']) == 85
    assert Decimal(first['B4']['value']) == 175 and first['B4']['formula'] and not first['B4']['cache_missing']
    assert Decimal(second['A1']['value']) == (date(2026, 11, 5) - date(1899, 12, 30)).days
    assert second['B1']['value'] == '<script>不执行</script>'
    # Calc exports this unstyled ODF boolean as numeric 1; the viewer must preserve the XML type/value.
    with ZipFile(sample) as archive:
        sheet_xml = ET.fromstring(archive.read('xl/worksheets/sheet2.xml'))
    declared = sheet_xml.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c[@r="C1"]')
    assert declared is not None and declared.get('t') == 'n'
    assert declared.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v').text == '1'
    assert second['C1']['value'] == '1'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == checksum and sample.read_bytes() == raw
    (root / 'viewer.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {'generator': 'LibreOffice ' + office_runtime.VERSION, 'runtime_fingerprint': runtime.fingerprint,
               'frozen': bool(args.exe), 'sheets': len(value['sheets']), 'cells': value['cell_count'],
               'source_preserved': True, 'cached_formula_and_date_serial_verified': True,
               'xlsx_sha256': hashlib.sha256(raw).hexdigest(), 'window_verified': False}
    (root / 'result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
