import base64
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows Authenticode')
SCRIPT = Path(__file__).resolve().parents[2] / 'packaging/windows/verify-backend-signature.ps1'
POWERSHELL = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass']


def verify(directory, *args, artifact='backend'):
    command = [str(SCRIPT), '-BackendDirectory', str(directory)] if artifact == 'backend' else [
        str(SCRIPT.with_name('verify-release-signature.ps1')), '-Artifact', 'Installer', '-Directory', str(directory)]
    return subprocess.run(
        [*POWERSHELL, '-File', *command, *args],
        capture_output=True, timeout=120,
    )


def test_signature_requires_explicit_pins(tmp_path):
    assert verify(tmp_path).returncode != 0
    assert verify(tmp_path, '-ExpectedFileSha256', 'bad', '-ExpectedSignerSha256', 'a' * 64).returncode != 0


def test_installer_verification_requires_the_outer_setup_file(tmp_path):
    (tmp_path / 'study_backend.exe').write_bytes(b'backend-only fixture')
    result = verify(tmp_path, '-ExpectedFileSha256', '0' * 64,
                    '-ExpectedSignerSha256', '0' * 64, artifact='installer')
    assert result.returncode != 0 and b'StudyWorkbench-M1-setup.exe' in result.stderr


@pytest.mark.parametrize(('artifact', 'filename'), [
    ('backend', 'study_backend.exe'), ('installer', 'StudyWorkbench-M1-setup.exe'),
])
def test_signed_fixture_and_tampering(tmp_path, artifact, filename):
    sdk = Path(os.environ['ProgramFiles(x86)']) / 'Windows Kits/10/bin'
    source = max(sdk.glob('10.*/x64/signtool.exe'), key=lambda p: tuple(map(int, p.parents[1].name.split('.'))))
    directory = tmp_path / 'backend with spaces'
    directory.mkdir()
    target = directory / filename
    shutil.copyfile(source, target)
    # Get the fixture identity separately from the Windows trust check under test.
    result = subprocess.run(
        [*POWERSHELL, '-Command',
         '[Convert]::ToBase64String([Security.Cryptography.X509Certificates.X509Certificate]'
         '::CreateFromSignedFile($env:STUDY_SIGNED_FIXTURE).GetRawCertData())'],
        env={**os.environ, 'STUDY_SIGNED_FIXTURE': str(source)}, capture_output=True, check=True, timeout=30,
    )
    signer = hashlib.sha256(base64.b64decode(result.stdout)).hexdigest()
    original = target.read_bytes()
    digest = hashlib.sha256(original).hexdigest()

    def check(expected_file, expected_signer):
        return verify(directory, '-ExpectedFileSha256', expected_file, '-ExpectedSignerSha256', expected_signer,
                      artifact=artifact)

    valid = check(digest, signer)
    assert valid.returncode == 0, valid.stderr
    receipt = json.loads(valid.stdout)
    assert receipt['file'] == filename
    assert (receipt['windows_status'], receipt['signature_type']) == ('Valid', 'Authenticode')
    assert receipt['file_sha256'].lower() == digest
    assert receipt['signer_certificate_sha256'].lower() == signer
    assert len(bytes.fromhex(receipt['timestamp_certificate_sha256'])) == 32
    wrong_signer = check(digest, '0' * 64)
    assert wrong_signer.returncode != 0 and b'signer certificate SHA256 mismatch' in wrong_signer.stderr

    modified = bytearray(original)
    modified[0x50] ^= 1  # DOS stub text, covered by the signature; PE layout stays intact.
    target.write_bytes(modified)
    wrong_file = check(digest, signer)
    assert wrong_file.returncode != 0 and b'file SHA256 mismatch' in wrong_file.stderr
    untrusted = check(hashlib.sha256(modified).hexdigest(), signer)
    assert untrusted.returncode != 0 and f'Valid embedded {artifact} signature required'.encode() in untrusted.stderr
    assert target.read_bytes() == modified
