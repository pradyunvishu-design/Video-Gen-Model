from types import SimpleNamespace

from pipeline import media_qc


def test_media_qc_parses_black_freeze_silence_and_scene_changes(monkeypatch, tmp_path):
    log = """
    [blackdetect] black_start:1 black_end:4 black_duration:3
    [freezedetect] freeze_start:8
    [freezedetect] freeze_end:21 freeze_duration:13
    [silencedetect] silence_start:30
    [silencedetect] silence_end:35 silence_duration:5
    [Parsed_showinfo_4] n:1 pts:100 pts_time:3.2
    [Parsed_showinfo_4] n:2 pts:200 pts_time:8.4
    """
    monkeypatch.setattr(
        media_qc.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=log, stdout=""),
    )

    report = media_qc.analyze_media(tmp_path / "episode.mp4", duration_seconds=60, has_audio=True)

    assert report["passed"] is False
    assert report["scene_change_count"] == 2
    assert len(report["failures"]) == 3


def test_media_qc_warns_when_actual_visual_changes_are_sparse(monkeypatch, tmp_path):
    monkeypatch.setattr(
        media_qc.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )

    report = media_qc.analyze_media(tmp_path / "episode.mp4", duration_seconds=120, has_audio=False)

    assert report["passed"] is True
    assert report["warnings"]
