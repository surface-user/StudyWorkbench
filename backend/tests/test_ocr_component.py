import hashlib
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def component(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    module = importlib.import_module('prepare_ocr_runtime')
    sources, pins = {}, {}
    for name in module.FILES:
        source = tmp_path / 'input' / name
        source.parent.mkdir(parents=True, exist_ok=True)
        data = name.encode('ascii')
        source.write_bytes(data)
        sources[name] = source
        pins[name] = len(data), hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(module, 'FILES', pins)
    return module, tmp_path / 'OCR 组件', sources


def test_stage_and_verify_exact_bytes_without_overwrite(component):
    module, root, sources = component
    module.prepare(root, sources)
    assert all((root / name).read_bytes() == path.read_bytes() for name, path in sources.items())
    module.verify(root)
    with pytest.raises(FileExistsError):
        module.prepare(root, sources)


@pytest.mark.parametrize('name', ['bin/tesseract.exe', 'tessdata/chi_sim.traineddata', 'licenses/leptonica-license.txt'])
def test_reject_same_size_mutation_before_and_after_stage(component, name):
    module, root, sources = component
    original = sources[name].read_bytes()
    sources[name].write_bytes(b'z' * len(original))
    with pytest.raises(ValueError, match='bytes differ'):
        module.prepare(root, sources)
    assert not root.exists()
    sources[name].write_bytes(original)
    module.prepare(root, sources)
    (root / name).write_bytes(b'z' * len(original))
    with pytest.raises(ValueError, match='bytes differ'):
        module.verify(root)


@pytest.mark.parametrize('extra', ['build-inventory.json', 'bin/unexpected.dll', 'tessdata/configs'])
def test_reject_unexpected_files_and_directories(component, extra):
    module, root, sources = component
    module.prepare(root, sources)
    (root / extra).mkdir()
    with pytest.raises(ValueError, match='Unexpected'):
        module.verify(root)


def test_missing_model_preserves_input_files_and_destination(component):
    module, root, sources = component
    sources['tessdata/eng.traineddata'].unlink()
    with pytest.raises(FileNotFoundError):
        module.prepare(root, sources)
    assert not root.exists() and sources['bin/tesseract.exe'].exists()
