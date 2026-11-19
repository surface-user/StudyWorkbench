"""Policy regressions; real native component evidence is recorded separately."""
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def binary(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('prepare_ffmpeg_binary')


@pytest.mark.parametrize('case', ['release', 'foreign_file', 'extra_key', 'bad_digest'])
def test_profile_rejects_changed_scope(binary, monkeypatch, tmp_path, case):
    value = binary.profile()
    if case == 'release':
        value['readiness']['release_ready'] = True
    elif case == 'foreign_file':
        value['runtime']['outside.dll'] = value['runtime']['ffmpeg.exe']
    elif case == 'extra_key':
        value['command'] = 'arbitrary command'
    else:
        value['runtime']['ffmpeg.exe']['sha256'] = 'not-a-hash'
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps(binary.envelope(value)), encoding='utf-8')
    monkeypatch.setattr(binary, 'PROFILE', path)
    with pytest.raises(ValueError):
        binary.profile()


def configuration_fixture(binary):
    lines = [f'#define CONFIG_{name} 0' for name in [
        'NETWORK', 'GPL', 'NONFREE', 'VERSION3', 'AUTODETECT', 'STATIC',
        'SWSCALE', 'SWRESAMPLE', 'AVDEVICE', 'ZLIB', 'BZLIB', 'LZMA']]
    lines += [f'#define CONFIG_{name} 1' for name in [
        'SHARED', 'FFMPEG', 'FFPROBE', 'AVCODEC', 'AVFORMAT', 'AVFILTER', 'AVUTIL']]
    for field, suffix in [('protocols', 'PROTOCOL'), ('demuxers', 'DEMUXER'),
                          ('muxers', 'MUXER'), ('parsers', 'PARSER'), ('bsfs', 'BSF')]:
        lines += [f'#define CONFIG_{name.upper()}_{suffix} 1' for name in binary.CAPABILITIES[field]]
    lines += [f'#define CONFIG_{name.upper()}_FILTER 1' for name in
              ['aformat', 'anull', 'atrim', 'crop', 'format', 'hflip', 'null', 'rotate', 'transpose', 'trim', 'vflip']]
    return ('\n'.join(lines) + '\n').encode()


def test_identical_official_macro_repetition_allowed_conflict_refused(binary):
    raw = configuration_fixture(binary)
    binary.configuration([raw, b'#define CONFIG_LIBSMBCLIENT 0\n#define CONFIG_LIBSMBCLIENT 0\n'])
    with pytest.raises(ValueError, match='Conflicting'):
        binary.configuration([raw, b'#define CONFIG_NETWORK 1\n'])


@pytest.mark.parametrize('macro', ['HTTP_PROTOCOL', 'H264_DECODER', 'H264_ENCODER', 'SCALE_FILTER'])
def test_extra_compiled_features_refused(binary, macro):
    with pytest.raises(ValueError):
        binary.configuration([configuration_fixture(binary), f'#define CONFIG_{macro} 1\n'.encode()])


def test_existing_output_preserved_before_build_access(binary, monkeypatch, tmp_path):
    target = tmp_path / 'existing'
    target.mkdir()
    original = target / 'original'
    original.write_bytes(b'keep original')

    def no_build(*args):
        pytest.fail('Existing output must be refused before inspecting build inputs')

    monkeypatch.setattr(binary, 'verify_build', no_build)
    with pytest.raises(ValueError, match='exists'):
        binary.prepare(tmp_path / 'absent', tmp_path / 'absent', tmp_path / 'absent', target)
    assert original.read_bytes() == b'keep original'


@pytest.mark.parametrize('case', ['self_rehash', 'metadata_type'])
def test_rehashed_lock_cannot_change_fixed_expectations(binary, monkeypatch, tmp_path, case):
    expected = {'schema_version': 1, 'readiness': binary.READINESS.copy(), 'files': {}}
    actual = json.loads(json.dumps(expected))
    if case == 'self_rehash':
        actual['files']['foreign.dll'] = binary.record(b'foreign')
    else:
        actual['readiness']['release_ready'] = 0
    monkeypatch.setattr(binary, 'payload', lambda value: expected)
    (tmp_path / binary.LOCK).write_text(json.dumps(binary.envelope(actual)), encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot differs'):
        binary.verify(tmp_path, {})


def test_checked_file_rejects_same_length_corruption(binary, tmp_path):
    path = tmp_path / 'file'
    path.write_bytes(b'original')
    expected = binary.record(path.read_bytes())
    path.write_bytes(b'modified')
    with pytest.raises(ValueError, match='hash differs'):
        binary.checked_file(path, expected)
