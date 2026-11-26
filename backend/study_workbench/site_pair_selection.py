"""Stable track choices for one preview. This module does not open media connections."""
import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .media_download_http import LIMIT, DownloadError, bilibili_media_host


class ConfirmPairSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    video_ref: str = Field(pattern=r'^video-[a-f0-9]{64}$')
    audio_ref: str = Field(pattern=r'^audio-[a-f0-9]{64}$')
    rights_confirmed: bool = Field(strict=True)

    @field_validator('rights_confirmed')
    @classmethod
    def consent(cls, value):
        if not value:
            raise ValueError('需要明确确认有权处理这份作品')
        return value


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('ascii')).hexdigest()


def mark_choices(result):
    """Called on parsed metadata only. No signed URL participates in a stable track identity."""
    rows = result['formats']
    marks = []
    for row in rows:
        role = {'dash_video': 'video', 'dash_audio': 'audio'}.get(row['delivery'])
        if role is None:
            continue
        quality, codec = row['source_format_id'], row['codecs']
        if not quality or not isinstance(codec, str):
            continue
        identity = [result['video_id'], result['source_aid'], result['source_cid'], role, quality, codec]
        ref = role + '-' + digest(identity)
        parts = urlsplit(row['url'] or '')
        supported = (row.pop('_pair_permitted', False) and bilibili_media_host(parts.hostname or '')
                     and parts.path.lower().endswith('.m4s') and
                     (row['size_bytes'] is None or 0 < row['size_bytes'] <= LIMIT))
        if role == 'video':
            supported = (supported and row['container'] == 'mp4' and re.fullmatch(r'avc1\.[0-9a-fA-F]{6}', codec)
                         and all(row[k] is None or row[k] > 0 for k in ('width', 'height')))
        else:
            supported = (supported and row['container'] == 'm4a' and codec == 'mp4a.40.2'
                         and all(row[k] in (None, 0) for k in ('width', 'height')) and row['fps'] is None)
        marks.append((row, role, ref, bool(supported), digest([parts.hostname, parts.path])))
    counts = Counter(ref for _, _, ref, _, _ in marks)
    choices = [(row, role, ref, path_id) for row, role, ref, supported, path_id in marks
               if supported and counts[ref] == 1]
    if {role for _, role, _, _ in choices} == {'video', 'audio'}:
        for row, _, ref, path_id in choices:
            row['pair_track_ref'], row['_pair_resource'] = ref, path_id
    for row in rows:
        if row['delivery'] in ('dash_video', 'dash_audio'):
            row.pop('_pair_permitted', None)
            row['url'] = None


def selected_pair(result, body):
    selections, resources = [], []
    for role, ref in [('video', body.video_ref), ('audio', body.audio_ref)]:
        matches = [row for row in result['formats'] if row.get('pair_track_ref') == ref
                   and row['delivery'] == 'dash_' + role]
        if len(matches) != 1:
            raise DownloadError('所选音视频轨道不存在、含歧义或不满足站点许可与格式条件')
        row = matches[0]
        selections.append(dict(role=role, track_ref=ref, **{key: row[key] for key in
                                ('source_format_id', 'container', 'codecs', 'width', 'height', 'fps', 'size_bytes')}))
        if role == 'audio':
            selections[-1].update(width=None, height=None)
        resources.append(row['_pair_resource'])
    if resources[0] == resources[1] or sum(row['size_bytes'] or 0 for row in selections) > LIMIT:
        raise DownloadError('两条轨道须来自不同资源，并共同满足大小预算')
    logical = dict(site='bilibili', extractor_version=result['extractor_version'], video_id=result['video_id'],
                   aid=result['source_aid'], cid=result['source_cid'], duration_seconds=result['duration_seconds'],
                   tracks=selections)
    return logical, resources
