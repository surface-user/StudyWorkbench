"""Pinned Office's local UNO configuration engine; no Desktop, acceptor, or scanner is created."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from study_workbench.office_runtime import OfficeRuntime, profile_configuration

runtime = OfficeRuntime(Path(r'D:\computer_work\project\StudyWorkbench\.local\release-tools\libreoffice-java-26.8.1-21.0.13'))
directory = ROOT / '.local/config-engine01'
(directory / 'profile/user').mkdir(parents=True)
(directory / 'tmp').mkdir()
profile = directory / 'profile/user/registrymodifications.xcu'
profile.write_text(profile_configuration(False), encoding='utf-8')
foreign = directory / 'foreign-finalized.xcu'
foreign.write_text('''<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting">
<prop oor:name="MacroSecurityLevel" oor:op="fuse" oor:finalized="true"><value>0</value></prop>
<prop oor:name="DisableMacrosExecution" oor:op="fuse" oor:finalized="true"><value>false</value></prop>
</item><item oor:path="/org.openoffice.Setup/Office">
<prop oor:name="ooSetupConnectionURL" oor:op="fuse" oor:finalized="true"><value>pipe,name=off02e-unused;urp;</value></prop>
</item></oor:items>''', encoding='utf-8')
foreign_rdb = directory / 'foreign-services.rdb'
foreign_rdb.write_text('''<components xmlns="http://openoffice.org/2010/uno-components">
<component loader="com.sun.star.loader.SharedLibrary" uri="file:///off02e-not-a-library.dll">
<implementation name="org.study.off02e.Foreign"><service name="com.study.off02e.Foreign"/></implementation>
</component></components>''', encoding='utf-8')
unorc = directory / 'profile/user/uno_packages/cache/registry/com.sun.star.comp.deployment.component.PackageRegistryBackend/unorc'
unorc.parent.mkdir(parents=True)
unorc.write_text('[Bootstrap]\nUNO_SERVICES=' + foreign_rdb.as_uri() + '\n', encoding='utf-8')
bootstrap = dict(value[5:].split('=', 1) for value in runtime.command(directory / 'source.docx', directory)
                 if value.startswith('-env:'))
environment = runtime.environment(directory)
environment.update(PYTHONHOME=str(runtime.root / 'program/python-core-3.13.15'),
                   PYTHONPATH=str(runtime.root / 'program'), PYTHONDONTWRITEBYTECODE='1',
                   URE_BOOTSTRAP=(runtime.root / 'program/fundamental.ini').as_uri())
script = '''import json
import uno
from com.sun.star.beans import PropertyValue
context = uno.getComponentContext()
provider = context.ServiceManager.createInstanceWithContext('com.sun.star.configuration.ConfigurationProvider', context)
result = {}
for path, names in [('/org.openoffice.Office.Common/Security/Scripting', ('MacroSecurityLevel', 'DisableMacrosExecution', 'DisableActiveContent', 'DisablePythonRuntime', 'DisableOLEAutomation', 'BlockUntrustedRefererLinks')), ('/org.openoffice.Setup/Office', ('ooSetupConnectionURL',)), ('/org.openoffice.Office.Writer/Content/Update', ('Link', 'Field', 'Chart'))]:
    argument = PropertyValue()
    argument.Name, argument.Value = 'nodepath', path
    access = provider.createInstanceWithArguments('com.sun.star.configuration.ConfigurationAccess', (argument,))
    result[path] = {name: access.getPropertyValue(name) for name in names}
result['foreign_service_registered'] = 'com.study.off02e.Foreign' in context.ServiceManager.getAvailableServiceNames()
print(json.dumps(result))
'''
foreign_layers = bootstrap['CONFIGURATION_LAYERS'].replace(' user:!', f' user:*{foreign.as_uri()} user:!')
cases = [('foreign-finalized', dict(bootstrap, CONFIGURATION_LAYERS=foreign_layers)),
         ('controlled', bootstrap),
         ('foreign-extension', {key: value for key, value in bootstrap.items() if key not in {
             'UNO_SERVICES', 'UNO_TYPES', 'URE_MORE_JAVA_TYPES'}})]
results = []
for label, settings in cases:
    result = subprocess.run([str(runtime.root / 'program/python.exe'), '-c', script], cwd=directory,
                            env=dict(environment, **settings), capture_output=True, text=True,
                            encoding='utf-8', timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, (label, result.returncode, result.stderr)
    assert not result.stderr
    value = json.loads(result.stdout)
    results.append({'case': label, 'values': value})
    print(json.dumps(results[-1]), flush=True)
    scripting, setup = value['/org.openoffice.Office.Common/Security/Scripting'], value['/org.openoffice.Setup/Office']
    if label == 'foreign-finalized':
        assert scripting['MacroSecurityLevel'] == 0 and scripting['DisableMacrosExecution'] is False
        assert setup['ooSetupConnectionURL'] == 'pipe,name=off02e-unused;urp;'
    else:
        assert scripting['MacroSecurityLevel'] == 3 and scripting['DisableMacrosExecution'] is True
        assert setup['ooSetupConnectionURL'] == ''
    assert value['foreign_service_registered'] is (label == 'foreign-extension')
summary = {'scope': 'local UNO context, bootstrap parameters supplied through environment; not soffice CLI',
           'results': results, 'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'fixtures': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (profile, foreign, foreign_rdb, unorc)}}
(ROOT / 'artifacts/off02e/config-engine01.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
