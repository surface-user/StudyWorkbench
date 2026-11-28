"""Two explicit site choices feed the ordinary queue using generated offline media only."""

import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from study_workbench import backup_store, media_download_worker, media_mux
from study_workbench.db import MediaDownloadAttempt, MediaDownloadJob
from study_workbench.media_downloads import MediaDownloads
from study_workbench.media_probes import ProbeMetadata
from study_workbench.media_sources import OutputReceipt
from test_bilibili_preview import source as source_fixture
from test_explorer import PREFIX, client
from test_media_download_http import Response, connections
from test_media_downloads import wait
from test_media_fragments import owned
from test_media_mux import pair_bytes
from test_media_sources import metadata
from test_site_pair_selection import ENDPOINT, choice, prepared
from test_site_pair_selection import tracks as tracks_fixture

source = source_fixture
tracks = tracks_fixture


def selected(api):
    key, public, refs = prepared(api)
    url = f"{ENDPOINT}/{key}"
    r = api.post(url + "/pair-selection", json=choice(refs))
    assert r.status_code == 200, r.text
    return url, dict(
        request_id="owned-pair-transfer-01",
        name="owned.mp4",
        rights_confirmed=True,
        selection_sha256=r.json()["selection_sha256"],
    )


def offline_transport(monkeypatch, bodies, *, fail_second=False, budget_case=None, native=False):
    # Execute the real acquisition and validation on two generated HTTPS response bodies.
    def child(self, job, operation, *, deadline=None, transfer=None, acquired=None):
        if transfer is not None:
            responses = [
                Response(
                    raw,
                    status=412 if i == 1 and fail_second else 200,
                    fields=[("Content-Type", "application/octet-stream"), ("Content-Length", str(len(raw)))],
                )
                for i, raw in enumerate(bodies)
            ]
            budget = vars(transfer.budget).copy()
            if budget_case == "redirects":
                budget["requests_left"] = 2
                responses.insert(0, Response(b"", status=302, fields=[("Location", "/redirected-video.m4s")]))
            elif budget_case == "bytes":
                budget["bytes_left"] = len(bodies[0]) + 1
            connections(monkeypatch, responses)
            options = dict(
                snapshot=job.source_snapshot,
                record=acquired.model_dump(mode="json"),
                root=str(self.root),
                job=job.id,
                workspace=job.workspace_id,
                attempt=job.attempt,
                generation=job.run_generation,
                urls=list(transfer.url),
                site_budget=budget,
            )
            return media_download_worker.fetch_pair(
                options, lambda: self.check(job.id), lambda progress: media_mux.progress(self, job, progress)
            )
        if native:
            return original(self, job, operation, deadline=deadline, acquired=acquired)
        # Persistence-only substitute. Native execution is checked independently with real input files.
        raw = pair_bytes()
        for frozen, role in zip(acquired.tracks, ("video", "audio"), strict=True):
            frozen.metadata = ProbeMetadata.model_validate(metadata(role))
            frozen.state = "probed"
        total = sum(t.received.size for t in acquired.tracks)
        media_mux.progress(
            self,
            job,
            dict(phase="probing", received=total, total=total, record=acquired.model_dump(mode="json")),
        )
        pending = operation / "output.pending.mp4"
        pending.write_bytes(raw)
        acquired.output = OutputReceipt.model_validate(
            dict(
                state="prepared",
                pending_path=pending.relative_to(self.root).as_posix(),
                final_path=job.relative_path,
                size=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
                metadata=dict(
                    container="mp4",
                    duration_ms=200,
                    streams=[
                        metadata("video")["streams"][0],
                        {**metadata("audio")["streams"][0], "index": 1},
                    ],
                ),
            )
        )
        return acquired.model_dump(mode="json")

    original = MediaDownloads.child
    monkeypatch.setattr(MediaDownloads, "child", child)


@pytest.mark.parametrize("declared", [True, False])
def test_two_selected_tracks_produce_one_queue_result_and_restore_without_addresses(
    tmp_path, monkeypatch, tracks, declared
):
    video, play, _ = tracks
    video["duration"], play["timelength"] = 1, 200
    play["dash"]["video"][0].update(width=16, height=16)
    bodies = [owned(role) for role in ("video", "audio")]
    for role, raw in zip(("video", "audio"), bodies, strict=True):
        play["dash"][role][0]["size"] = len(raw) if declared else None
    offline_transport(monkeypatch, bodies)
    root = tmp_path / "library"
    with client(root) as api:
        url, body = selected(api)
        one = api.post(url + "/confirm-pair", json=body)
        assert one.status_code == 200, one.text
        job = wait(api, one.json()["id"], {"ready", "failed"})
        assert job["status"] == "ready", job
        assert job["source_kind"] == "site_pair" and not job["can_resume"]
        assert api.post(url + "/confirm-pair", json=body).json()["id"] == job["id"]
        assert (
            api.post(url + "/confirm-pair", json={**body, "request_id": "different-queue-id-01"}).status_code
            == 409
        )
        assert api.post(url + "/confirm-pair", json={**body, "name": "another.mp4"}).status_code == 409
        with Session(api.app.state.engine) as session:
            assert len(list(session.scalars(select(MediaDownloadJob)))) == 1
            row = session.get(MediaDownloadAttempt, (job["id"], 1))
            for track, raw in zip(row.record["tracks"], bodies, strict=True):
                assert track["received"] == dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                assert (root / track["relative_path"]).read_bytes() == raw
    assert b"signature=" not in (root / "study.db").read_bytes()
    package = tmp_path / "backup.zip"
    backup_store.create_backup(root, package)
    target = tmp_path / "restored"
    backup_store.restore_backup(package, target, tmp_path / "config.json")
    with client(target) as api:
        assert api.get(url).status_code == 404
        assert api.post(url + "/confirm-pair", json=body).json()["id"] == job["id"]


@pytest.mark.parametrize("reason", ["second_response", "redirects", "bytes"])
def test_partial_site_pair_keeps_first_track_and_requires_fresh_consent(tmp_path, monkeypatch, tracks, reason):
    _, play, _ = tracks
    bodies = [owned(role) for role in ("video", "audio")]
    for role, raw in zip(("video", "audio"), bodies, strict=True):
        play["dash"][role][0]["size"] = None if reason == "bytes" else len(raw)
    offline_transport(monkeypatch, bodies, fail_second=(reason == "second_response"), budget_case=reason)
    with client(tmp_path) as api:
        url, body = selected(api)
        job = api.post(url + "/confirm-pair", json=body).json()
        stopped = wait(api, job["id"], {"ready", "failed"})
        assert stopped["status"] == "failed" and not stopped["result"]
        if reason == "redirects":
            assert "请求" in stopped["error"]
        elif reason == "bytes":
            assert "字节额度" in stopped["error"]
        assert (
            api.post(
                PREFIX + "/media-downloads/" + job["id"] + "/retry", json={"mode": "restart"}
            ).status_code
            == 409
        )
        with Session(api.app.state.engine) as s:
            record = s.get(MediaDownloadAttempt, (job["id"], 1)).record
            assert [t["state"] for t in record["tracks"]] == ["copied", "pending"]
            assert (tmp_path / record["tracks"][0]["relative_path"]).read_bytes() == bodies[0]
        assert not (tmp_path / "workspaces/default/downloads" / job["id"] / "1.mp4").exists()


def test_refuses_unselected_changed_unpermitted_or_cross_workspace_pairs(tmp_path, tracks):
    state, _, _ = tracks
    with client(tmp_path) as api:
        key, _, refs = prepared(api)
        url = f"{ENDPOINT}/{key}"
        body = dict(
            request_id="owned-blocked-queue-01",
            name="x.mp4",
            rights_confirmed=True,
            selection_sha256="f" * 64,
        )
        assert api.post(url + "/confirm-pair", json=body).status_code == 409
        assert api.post(url + "/confirm-pair", json={**body, "rights_confirmed": False}).status_code == 422
        receipt = api.post(url + "/pair-selection", json=choice(refs)).json()
        body["selection_sha256"] = receipt["selection_sha256"]
        assert api.post(url + "/confirm-pair", json={**body, "name": "x.webm"}).status_code == 422
        other = api.post("/api/workspaces", json={"name": "other"}).json()["id"]
        assert (
            api.post(url.replace("/default/", "/" + other + "/") + "/confirm-pair", json=body).status_code
            == 404
        )
        state["rights"]["download"] = 0
        assert api.post(url + "/confirm-pair", json=body).status_code == 409
        assert api.get(PREFIX + "/media-downloads").json() == []


@pytest.mark.parametrize(
    "fault",
    [
        "change_path",
        "external_host",
        "one_request_left",
        "metadata_over_budget",
        "missing_usage",
        "same_resource",
        "expired",
    ],
)
def test_final_recheck_refuses_changed_authority_or_shared_allowance(tmp_path, monkeypatch, tracks, fault):
    from study_workbench.media_site_previews import MediaSitePreviews

    with client(tmp_path) as api:
        url, body = selected(api)
        original = MediaSitePreviews.child

        def altered(self, entry, refs):
            out = original(self, entry, refs)
            media = out["_selected_pair_urls"]
            if fault == "change_path":
                media[refs[0]] = media[refs[0]].replace("/video.m4s", "/other.m4s")
            elif fault == "external_host":
                media[refs[0]] = "https://media.example.org/video.m4s"
            elif fault == "one_request_left":
                out["metadata_usage"]["requests"] = 9
            elif fault == "metadata_over_budget":
                out["metadata_usage"]["bytes"] = 8 * 1024 * 1024 + 1
            elif fault == "missing_usage":
                del out["metadata_usage"]
            elif fault == "same_resource":
                media[refs[0]] = media[refs[1]]
            else:
                entry["expires"] = 0
            return out

        monkeypatch.setattr(MediaSitePreviews, "child", altered)
        result = api.post(url + "/confirm-pair", json=body)
        assert result.status_code == 409 and "signature=" not in result.text
        assert api.get(PREFIX + "/media-downloads").json() == []


def test_native_evidence_must_match_duration_and_video_dimensions(tmp_path, monkeypatch, tracks):
    _, play, _ = tracks
    bodies = [owned(role) for role in ("video", "audio")]
    for role, raw in zip(("video", "audio"), bodies, strict=True):
        play["dash"][role][0]["size"] = len(raw)
    offline_transport(monkeypatch, bodies)
    with client(tmp_path) as api:
        url, body = selected(api)
        key = api.post(url + "/confirm-pair", json=body).json()["id"]
        stopped = wait(api, key, {"failed", "ready"})
        assert stopped["status"] == "failed" and not stopped["result"]
        assert not (tmp_path / "workspaces/default/downloads" / key / "1.mp4").exists()
