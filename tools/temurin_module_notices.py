"""Map notices in a pinned, prepared Temurin image to observed Java module descriptors."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from prepare_java_runtime import LOCK_NAME, PACKAGE_SHA256, VERSION, no_links, verify_runtime
from prepared_office_sbom import MOUNT, file_sha, hashes, unique_object, verify_java
from study_workbench.office_runtime import JAVA_LOCK_SHA256

MODULE = r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*'
FILENAME = r'[A-Za-z0-9_][A-Za-z0-9_.+-]*'
COMMON = ('LICENSE', 'ADDITIONAL_LICENSE_INFO', 'ASSEMBLY_EXCEPTION')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module_descriptors(listing, image):
    lines = [line for line in listing.splitlines() if line.strip()]
    if not lines or lines[0] != f'jimage: {image}' or len(lines) % 2 != 1:
        raise ValueError('Unexpected image descriptor listing')
    modules = set()
    for title, descriptor in zip(lines[1::2], lines[2::2], strict=True):
        match = re.fullmatch(f'Module: ({MODULE})', title)
        if not match or descriptor.strip() != 'module-info.class' or match[1] in modules:
            raise ValueError('Invalid or duplicated module descriptor')
        modules.add(match[1])
    if not modules:
        raise ValueError('Empty image descriptor listing')
    return modules


def declared_modules(release):
    fields = [line for line in release.splitlines() if line.startswith('MODULES=')]
    if len(fields) == 1 and (match := re.fullmatch(f'MODULES="({MODULE}(?: {MODULE})*)"', fields[0])):
        names = match[1].split()
        if len(names) == len(set(names)):
            return set(names)
    raise ValueError('Invalid MODULES declaration')


def resolve_notice(name, notices):
    """Resolve the publisher's single-line sibling references within the verified file set."""
    current, chain = name, []
    while current not in chain:
        chain.append(current)
        if current not in notices:
            return {'status': 'missing', 'chain': chain}
        raw = notices[current]
        try:
            body = raw.decode('utf-8-sig').strip()
        except UnicodeDecodeError:
            body = ''
        if not body or any(not (c.isprintable() or c.isspace()) for c in body):
            return {'status': 'unconfirmed-text', 'chain': chain}
        if not body.startswith('Please see'):
            result = {'status': 'direct' if len(chain) == 1 else 'reference', 'chain': chain,
                      'bodySha256': digest(raw)}
            if current.endswith('.md') and (heading := re.fullmatch(r'#{1,6} (.{1,256})', body.splitlines()[0])):
                result['publisherHeading'] = heading[1]
            return result
        ref = re.fullmatch(rf'Please see \.\./({MODULE})/({FILENAME})', body.replace('\\', '/'))
        if not ref:
            return {'status': 'unconfirmed-reference', 'chain': chain}
        current = f'legal/{ref[1]}/{ref[2]}'
    return {'status': 'cyclic-reference', 'chain': chain + [current]}


def inventory(actual, declared, notices):
    by_module, unassigned = {}, []
    for path in sorted(notices):
        match = re.fullmatch(rf'legal/({MODULE})/({FILENAME})', path)
        if match:
            by_module.setdefault(match[1], []).append(match[2])
        elif path != 'NOTICE':
            unassigned.append(path)
    modules = {}
    for module in sorted(actual | set(by_module)):
        supplied = by_module.get(module, [])
        files = set(supplied) | (set(COMMON) if module in actual else set())
        modules[module] = {'descriptorPresent': module in actual, 'legalDirectoryFiles': len(supplied),
                           'notices': {name: resolve_notice(f'legal/{module}/{name}', notices) for name in sorted(files)}}
    return {'modules': modules, 'declaredOnly': sorted(declared - actual), 'imageOnly': sorted(actual - declared),
            'noticeDirectoriesWithoutDescriptor': sorted(by_module.keys() - actual),
            'imageModulesWithoutNoticeDirectory': sorted(actual - by_module.keys()), 'unassignedLegalPaths': unassigned,
            'rootNotice': resolve_notice('NOTICE', notices),
            'providedNoticeSha256': {path: digest(raw) for path, raw in sorted(notices.items())}}


def check_layer(bom, expected):
    if (bom['bomFormat'] != 'CycloneDX' or bom['specVersion'] != '1.6' or
            not re.fullmatch('prepared:[a-f0-9]{64}', bom['metadata']['component']['bom-ref'])):
        raise ValueError('Expected a prepared component SBOM')
    layers = [item for item in bom['components'] if item['bom-ref'] == 'archive:' + PACKAGE_SHA256]
    if len(layers) != 1 or layers[0]['version'] != VERSION:
        raise ValueError('Expected one pinned JRE layer')
    prefix = 'app/' + MOUNT + 'java/'
    members = layers[0]['components']
    if len(members) != len(expected) or {member['name'] for member in members} != {prefix + name for name in expected}:
        raise ValueError('JRE layer files differ')
    for member in members:
        name = member['name']
        if (member['type'] != 'file' or member['bom-ref'] != 'file:' + name or
                member['hashes'] != hashes(expected[name.removeprefix(prefix)])):
            raise ValueError('JRE layer file differs')


def generate(java, jre_zip, prepared_bom, bom_sha256, jimage, output):
    for path in (java, jre_zip, prepared_bom, jimage, output.parent):
        no_links(path.absolute())
    java = java.resolve()
    if output.resolve().is_relative_to(java) or output.exists():
        raise ValueError('Use a new output outside the runtime')
    if prepared_bom.stat().st_size > 32 << 20 or file_sha(prepared_bom) != bom_sha256:
        raise ValueError('Prepared SBOM differs from receipt')
    bom = json.loads(prepared_bom.read_bytes(), object_pairs_hook=unique_object)
    lock = java / LOCK_NAME
    no_links(lock)
    if file_sha(lock) != JAVA_LOCK_SHA256:
        raise ValueError('Prepared JRE lock differs')
    expected = json.loads(lock.read_bytes(), object_pairs_hook=unique_object)['files']
    check_layer(bom, expected)
    verify_java(jre_zip, expected)
    verify_runtime(java, expected)
    # Use a developer JDK reader on the image. The product JRE is never started.
    image = java / 'lib/modules'
    environment = {k: v for k, v in os.environ.items()
                   if k.upper() not in ('JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS', 'CLASSPATH')}
    reader = jimage.resolve()
    reader_sha = file_sha(reader)
    result = subprocess.run([str(reader), '-J-Dfile.encoding=UTF-8', '-J-Dsun.stdout.encoding=UTF-8',
                             'list', '--include', 'glob:**/module-info.class', str(image)],
                            cwd=reader.parent, env=environment, capture_output=True, check=True, timeout=60)
    listing = result.stdout.decode('utf-8')
    actual = module_descriptors(listing, image)
    declared = declared_modules((java / 'release').read_text(encoding='utf-8'))
    notices = {name: (java / name).read_bytes() for name in expected if name == 'NOTICE' or name.startswith('legal/')}
    report = inventory(actual, declared, notices)
    if (any(expected[path] != sha for path, sha in report['providedNoticeSha256'].items()) or
            file_sha(prepared_bom) != bom_sha256 or file_sha(image) != expected['lib/modules'] or
            file_sha(java / 'release') != expected['release'] or file_sha(reader) != reader_sha or
            file_sha(jre_zip) != PACKAGE_SHA256 or file_sha(lock) != JAVA_LOCK_SHA256):
        raise ValueError('Input changed during notice mapping')
    report.update({'scope': 'prepared Temurin JRE', 'preparedBomSha256': bom_sha256, 'zipSha256': PACKAGE_SHA256,
                   'imageSha256': expected['lib/modules'], 'descriptorReaderSha256': reader_sha,
                   'declaredModuleCount': len(declared), 'imageModuleCount': len(actual)})
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('java', 'jre-zip', 'prepared-bom', 'jimage', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--bom-sha256', required=True, help='Previously verified prepared SBOM digest')
    args = parser.parse_args()
    generate(args.java, args.jre_zip, args.prepared_bom, args.bom_sha256, args.jimage, args.output)
