"""Attach verified Requires-Dist edges to the matching Windows frozen backend SBOM."""
import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
from collections import defaultdict
from email.parser import BytesParser
from pathlib import Path

from frozen_sbom import inventory, safe_name
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from source_sbom import no_links


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def declared_graph(packages, environment):
    # A dependency can request an extra on an already visited distribution.
    extras = {name: {''} for name in packages}
    edges = defaultdict(set)
    unresolved = set()
    inactive = set()
    while True:
        grew = False
        inactive.clear()
        for name, (version, provides, requirements) in packages.items():
            for req in requirements:
                if req.marker and not any(req.marker.evaluate({**environment, 'extra': x}) for x in extras[name]):
                    inactive.add((name, str(req)))
                    continue
                target = canonicalize_name(req.name)
                if req.url:
                    reason = 'direct-reference'
                elif target not in packages:
                    reason = 'not-in-mapped-subset'
                elif not req.specifier.contains(packages[target][0], prereleases=True):
                    reason = 'version-mismatch'
                else:
                    edges[name].add(target)
                    requested = {canonicalize_name(x) for x in req.extras}
                    absent = requested - packages[target][1]
                    if absent:
                        unresolved.add((name, target, 'undeclared-requested-extra'))
                    new = (requested & packages[target][1]) - extras[target]
                    if new:
                        extras[target].update(new)
                        grew = True
                    continue
                unresolved.add((name, target, reason))
        if not grew:
            return edges, sorted(unresolved), len(inactive), {k: sorted(v - {''}) for k, v in extras.items() if len(v) > 1}


def annotate(payload, sbom, origins_dir, output):
    if sys.platform != 'win32' or sys.version_info[:3] != (3, 13, 17):
        raise ValueError('Run with the pinned Windows 3.13.17 build interpreter')
    no_links(output.parent)
    if output.resolve().is_relative_to(payload.resolve()):
        raise ValueError('Keep exports outside the payload')
    raw = sbom.read_bytes()
    document = json.loads(raw)
    member_raw = (origins_dir / 'local-members/members.json').read_bytes()
    members = json.loads(member_raw)
    origins = json.loads((origins_dir / 'origins.json').read_bytes())
    actual = inventory(payload)
    fingerprint = digest(json.dumps(actual, sort_keys=True).encode())
    properties = {x['name']: x['value'] for x in document['metadata']['properties']}
    file_components = [c for c in document['components'] if c['type'] == 'file']
    by_path = {c['name']: c['hashes'] for c in file_components}
    expected = {k: [{'alg': 'SHA-256', 'content': v['sha256']}] for k, v in actual.items()}
    if (document.get('dependencies') or len(by_path) != len(file_components) or by_path != expected
            or fingerprint != properties.get('studyworkbench:payload-fingerprint-sha256')
            or fingerprint != members['payload_fingerprint'] or fingerprint != origins['payload_fingerprint']
            or digest(member_raw) != origins['base_members_sha256']
            or document['metadata']['component']['version'] != members['source_head_assertion']):
        raise ValueError('Expected the matching file-level SBOM and member report')
    verified = {k for k, v in members['build_packages'].items() if v['status'] == 'has_verified_local_members'}
    if not verified or verified != set(members['member_packages']):
        raise ValueError('Frozen membership list is incomplete')
    present = {c['purl'] for c in document['components'] if c['type'] == 'library'}
    packages, identities, sources = {}, {}, {}
    installed = defaultdict(list)
    for dist in importlib.metadata.distributions():
        installed[(canonicalize_name(dist.metadata['Name']), dist.version)].append(dist)
    for purl in members['member_packages']:
        match = re.fullmatch(r'pkg:pypi/([a-z0-9.-]+)@([a-zA-Z0-9.+-]+)', purl)
        if not match or purl not in present or match[1] in packages:
            raise ValueError('Missing or ambiguous package identity')
        name, version = match.groups()
        proof = members['build_packages'][purl]
        distributions = installed[(name, version)]
        if len(distributions) != 1 or proof['status'] != 'has_verified_local_members':
            raise ValueError('Missing or ambiguous build distribution')
        path = Path(distributions[0].locate_file(safe_name(proof['metadata_path'])))
        no_links(path)
        with path.open('rb') as stream:
            data = stream.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024 or digest(data) != proof['metadata_sha256']:
            raise ValueError('Package metadata changed')
        meta = BytesParser().parsebytes(data, headersonly=True)
        if canonicalize_name(meta['Name']) != name or meta['Version'] != version:
            raise ValueError('Package metadata identity differs')
        sources[path] = proof['metadata_sha256']
        provides = {canonicalize_name(x) for x in meta.get_all('Provides-Extra', [])}
        packages[name] = version, provides, [Requirement(x) for x in meta.get_all('Requires-Dist', [])]
        identities[name] = purl
    edges, unresolved, inactive, extras = declared_graph(packages, default_environment())
    # Record only established edges. Other component types and missing endpoints retain unknown relationships.
    document['dependencies'] = [{'ref': identities[k], 'dependsOn': sorted(identities[t] for t in targets)}
                                for k, targets in sorted(edges.items()) if targets]
    if inventory(payload) != actual or any(digest(p.read_bytes()) != h for p, h in sources.items()):
        raise ValueError('Build inputs changed during graph construction')
    report = dict(physical_files=len(actual), mapped_packages=len(packages), edges=sum(map(len, edges.values())),
                  active_unresolved=unresolved, inactive_declarations=inactive, requested_extras=extras,
                  input_sbom_sha256=digest(raw))
    props = document['metadata']['properties']
    props.append({'name': 'studyworkbench:dependency-scope',
                  'value': 'active Requires-Dist among mapped PyPI members, Windows CPython 3.13.17'})
    props.append({'name': 'studyworkbench:unresolved-active-declarations', 'value': str(len(unresolved))})
    encoded = (json.dumps(document, separators=(',', ':'), ensure_ascii=True) + '\n').encode()
    with output.open('xb') as stream:
        stream.write(encoded)
    return {**report, 'sha256': digest(encoded)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('payload', 'sbom', 'origins', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(annotate(args.payload, args.sbom, args.origins, args.output)))
