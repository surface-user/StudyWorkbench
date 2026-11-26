import hashlib
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('temurin_module_notices')


def test_descriptors_are_separate_from_release_and_notice_only_modules(tool):
    image = Path('test image') / 'modules'
    actual = tool.module_descriptors(f'jimage: {image}\n\nModule: java.base\n    module-info.class\n'
                                     'Module: java.observed\n    module-info.class\n', image)
    declared = tool.declared_modules('MODULES="java.base java.metadata"\n')
    report = tool.inventory(actual, declared, {'legal/java.base/LICENSE': b'text', 'legal/java.unseen/n.md': b'more',
                                               'legal/unassigned': b'other', 'NOTICE': b'root'})
    assert report['declaredOnly'] == ['java.metadata']
    assert report['imageOnly'] == ['java.observed']
    assert report['imageModulesWithoutNoticeDirectory'] == ['java.observed']
    assert report['noticeDirectoriesWithoutDescriptor'] == ['java.unseen']
    assert report['modules']['java.unseen']['descriptorPresent'] is False
    assert report['modules']['java.observed']['notices']['LICENSE']['status'] == 'missing'
    assert report['modules']['java.base']['notices']['ASSEMBLY_EXCEPTION']['status'] == 'missing'
    assert report['unassignedLegalPaths'] == ['legal/unassigned']
    assert report['rootNotice']['status'] == 'direct'


@pytest.mark.parametrize('listing', ['jimage: other\nModule: a\n module-info.class', 'jimage: x',
                                     'jimage: x\nModule: a\n other.class', 'jimage: x\nModule: ../x\n module-info.class',
                                     'jimage: x\nModule: a\n module-info.class\nModule: a\n module-info.class'])
def test_invalid_descriptor_listing_fails(tool, listing):
    with pytest.raises(ValueError):
        tool.module_descriptors(listing, Path('x'))


@pytest.mark.parametrize('declaration', ['MODULES="a a"', 'MODULES="a"\nMODULES="b"', 'MODULES="a ../b"', 'VERSION=21'])
def test_invalid_release_modules_fail(tool, declaration):
    with pytest.raises(ValueError):
        tool.declared_modules(declaration)


def test_reference_bodies_are_linked_without_counting_redirect_text_as_a_license(tool):
    notices = {'legal/m.one/X': b'Please see ..\\m.two\\Y\r\n', 'legal/m.two/Y': b'Please see ../m.three/Z',
               'legal/m.three/Z': b'final text'}
    found = tool.resolve_notice('legal/m.one/X', notices)
    assert found == {'status': 'reference', 'chain': list(notices), 'bodySha256': hashlib.sha256(b'final text').hexdigest()}
    del notices['legal/m.three/Z']
    missing = tool.resolve_notice('legal/m.one/X', notices)
    assert missing == {'status': 'missing', 'chain': [*notices, 'legal/m.three/Z']}
    notices['legal/m.two/Y'] = b'Please see ../m.one/X'
    assert tool.resolve_notice('legal/m.one/X', notices)['status'] == 'cyclic-reference'


def test_supplemental_title_comes_from_referenced_text(tool):
    notices = {'legal/a/other.md': b'Please see ../b/unknown.md', 'legal/b/unknown.md': b'## Sample Library 2\nText'}
    assert tool.resolve_notice('legal/a/other.md', notices)['publisherHeading'] == 'Sample Library 2'
    notices['legal/b/unknown.md'] = b'Additional notice without a title'
    assert 'publisherHeading' not in tool.resolve_notice('legal/a/other.md', notices)


@pytest.mark.parametrize('raw,status', [(b'Please see ../../outside', 'unconfirmed-reference'),
                                       (b'Please see C:\\name', 'unconfirmed-reference'),
                                       (b'Please see ../a/A\nother', 'unconfirmed-reference'),
                                       (b'\xff', 'unconfirmed-text'), (b'\0body', 'unconfirmed-text'),
                                       (b'  \n', 'unconfirmed-text')])
def test_unconfirmed_notice_gives_no_body_hash(tool, raw, status):
    assert tool.resolve_notice('legal/m/X', {'legal/m/X': raw}) == {'status': status, 'chain': ['legal/m/X']}


def test_only_exact_pinned_sbom_layer_files_match(tool):
    name = 'app/' + tool.MOUNT + 'java/NOTICE'
    sha = 'a' * 64
    member = {'name': name, 'bom-ref': 'file:' + name, 'type': 'file', 'hashes': tool.hashes(sha)}
    layer = {'bom-ref': 'archive:' + tool.PACKAGE_SHA256, 'version': tool.VERSION, 'components': [member]}
    bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'metadata': {'component': {'bom-ref': 'prepared:' + sha}},
           'components': [layer]}
    tool.check_layer(bom, {'NOTICE': sha})
    with pytest.raises(ValueError):
        tool.check_layer(bom, {'NOTICE': 'b' * 64})
    with pytest.raises(ValueError):
        tool.check_layer(bom, {'else': sha})
    layer['components'].append(member)
    with pytest.raises(ValueError):
        tool.check_layer(bom, {'NOTICE': sha})
