"""Versioned local-pair selection and attempt receipts, never URLs, headers or CLI arguments."""
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .backup_archive import archive_path
from .media_probe_runtime import SNAPSHOT, strict_json
from .media_probes import ProbeMetadata

SOURCE_LIMIT = 16384
ATTEMPT_LIMIT = 8192
INPUT_LIMIT = 512 * 1024 * 1024
RECIPE = 'mp4-copy-pair-v1'


class TrackSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    media_id: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    size: int = Field(ge=1, le=INPUT_LIMIT)
    mime: Literal['video/mp4', 'audio/mp4']
    role: Literal['video', 'audio']
    stream_index: int = Field(ge=0, le=1)


class LocalPairSource(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: Literal[1]
    kind: Literal['local_pair']
    recipe_version: Literal['mp4-copy-pair-v1']
    component_snapshot_sha256: str
    tracks: list[TrackSelection] = Field(min_length=2, max_length=2)

    @model_validator(mode='before')
    @classmethod
    def integer_version(cls, value):
        if not isinstance(value, dict) or type(value.get('schema_version')) is not int:
            raise ValueError('Source version must be an integer')
        return value

    @model_validator(mode='after')
    def selected_pair(self):
        if (self.component_snapshot_sha256 != SNAPSHOT or [t.role for t in self.tracks] != ['video', 'audio'] or
                len({(t.media_id, t.stream_index) for t in self.tracks}) != 2 or
                sum(t.size for t in self.tracks) > INPUT_LIMIT):
            raise ValueError('Unsupported selection, duplicate stream or shared input budget')
        return self


class FrozenTrack(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    ordinal: int = Field(ge=0, le=1)
    state: Literal['pending', 'copied', 'probed']
    relative_path: str = Field(min_length=1, max_length=2048)
    metadata: ProbeMetadata | None = None

    @model_validator(mode='after')
    def observed_metadata(self):
        if (self.state == 'probed') != (self.metadata is not None):
            raise ValueError('Probe state and observed metadata disagree')
        if self.metadata is not None:
            streams = self.metadata.streams
            if [s.index for s in streams] != list(range(len(streams))) or len({s.role for s in streams}) != len(streams):
                raise ValueError('Ambiguous observed streams')
        return self


class OutputReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    state: Literal['prepared', 'committed']
    pending_path: str = Field(min_length=1, max_length=2048)
    final_path: str = Field(min_length=1, max_length=2048)
    size: int = Field(ge=1, le=INPUT_LIMIT)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    metadata: ProbeMetadata

    @model_validator(mode='after')
    def copied_pair(self):
        if [(s.index, s.role) for s in self.metadata.streams] != [(0, 'video'), (1, 'audio')]:
            raise ValueError('Output must contain the selected video/audio pair')
        return self


class AttemptRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: Literal[1]
    source_snapshot_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    tracks: list[FrozenTrack] = Field(min_length=2, max_length=2)
    output: OutputReceipt | None = None

    @model_validator(mode='before')
    @classmethod
    def integer_version(cls, value):
        if not isinstance(value, dict) or type(value.get('schema_version')) is not int:
            raise ValueError('Receipt version must be an integer')
        return value

    @model_validator(mode='after')
    def ordered_tracks(self):
        if [t.ordinal for t in self.tracks] != [0, 1]:
            raise ValueError('Receipt ordinals must match the selected pair')
        if self.output is not None and any(t.state != 'probed' for t in self.tracks):
            raise ValueError('Output cannot precede both input probes')
        return self


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def source_snapshot(value):
    raw = value.encode('utf-8') if isinstance(value, str) else canonical(value)
    return LocalPairSource.model_validate(strict_json(raw, SOURCE_LIMIT))


def source_digest(source):
    # Only the selection enters the preimage; its derived digest is a separate job column.
    return hashlib.sha256(canonical(source.model_dump(mode='json'))).hexdigest()


def attempt_record(value):
    raw = value.encode('utf-8') if isinstance(value, str) else canonical(value)
    return AttemptRecord.model_validate(strict_json(raw, ATTEMPT_LIMIT))


def attempt_context(workspace, job, attempt, generation, source, record, *, ready=False):
    if (not isinstance(workspace, str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', workspace) or
            not isinstance(job, str) or not re.fullmatch('[a-f0-9]{32}', job) or
            type(attempt) is not int or attempt < 1 or type(generation) is not int or generation < 1 or
            record.source_snapshot_sha256 != source_digest(source)):
        raise ValueError('Attempt identity or source snapshot differs')
    parent = archive_path(f'workspaces/{workspace}/downloads/{job}')
    directory = f'{parent}/{attempt}/{generation}'
    for selection, track in zip(source.tracks, record.tracks, strict=True):
        suffix = '.m4a' if selection.mime == 'audio/mp4' else '.mp4'
        if track.relative_path != f'{directory}/input{track.ordinal}{suffix}':
            raise ValueError('Frozen input is outside this attempt')
        if track.metadata is not None:
            streams = track.metadata.streams
            if selection.stream_index >= len(streams) or streams[selection.stream_index].role != selection.role:
                raise ValueError('Selected stream differs from actual probe')
    if record.output is not None and (record.output.pending_path != f'{directory}/output.pending.mp4' or
                                      record.output.final_path != f'{parent}/{attempt}.mp4'):
        raise ValueError('Output is outside this attempt')
    if ready and (record.output is None or record.output.state != 'committed'):
        raise ValueError('Ready attempt has no committed output receipt')
    return directory


def stored_source(job):
    """Validate a local job independently of SQL CHECKs, including restored databases."""
    source = source_snapshot(job['source_snapshot'])
    if (job['source_kind'] != 'local_pair' or job['source_url'] is not None or
            source_digest(source) != job['source_snapshot_sha256'] or
            type(job['attempt']) is not int or job['attempt'] < 1 or
            type(job['run_generation']) is not int or job['run_generation'] < 0 or
            not isinstance(job['id'], str) or not re.fullmatch('[a-f0-9]{32}', job['id']) or
            not isinstance(job['workspace_id'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', job['workspace_id']) or
            job['relative_path'] != f"workspaces/{job['workspace_id']}/downloads/{job['id']}/{job['attempt']}.mp4"):
        raise ValueError('Invalid local source identity')
    archive_path(job['relative_path'])
    return source


def stored_attempt(job, row, source):
    record = attempt_record(row['record'])
    if (row['job_id'] != job['id'] or row['workspace_id'] != job['workspace_id'] or
            row['source_snapshot_sha256'] != job['source_snapshot_sha256'] or
            type(row['attempt']) is not int or type(row['generation']) is not int or
            row['attempt'] > job['attempt'] or row['generation'] > job['run_generation'] or
            row['status'] not in {'running', 'paused', 'interrupted', 'failed', 'ready'} or
            row['phase'] not in {'copying', 'probing', 'muxing', 'validating', 'publishing', 'ready'} or
            (row['status'] == 'ready') != (row['phase'] == 'ready')):
        raise ValueError('Invalid attempt identity or lifecycle')
    if row['generation'] == job['run_generation'] and (row['status'] == 'ready') != (job['status'] == 'ready'):
        raise ValueError('Current job and execution completion disagree')
    attempt_context(row['workspace_id'], row['job_id'], row['attempt'], row['generation'],
                    source, record, ready=row['status'] == 'ready')
    if (record.output is not None and record.output.state == 'committed') != (row['status'] == 'ready'):
        raise ValueError('Committed output and attempt status disagree')
    return record


def retained_files(source, record):
    """Yield alternative paths, expected hash/size, optional. Prepared publication may have moved."""
    for selection, track in zip(source.tracks, record.tracks, strict=True):
        full = track.state != 'pending'
        yield (track.relative_path,), selection.sha256 if full else None, selection.size if full else None, not full
    if record.output is not None:
        output = record.output
        paths = (output.final_path,) if output.state == 'committed' else (output.pending_path, output.final_path)
        yield paths, output.sha256, output.size, False
