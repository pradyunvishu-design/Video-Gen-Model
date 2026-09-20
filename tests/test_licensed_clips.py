import hashlib
import json

import pytest
from pydantic import ValidationError

from pipeline.licensed_clips import LicensedClipRequest, _verify_rights, ingest_licensed_clip


def _request(**overrides) -> LicensedClipRequest:
    payload = {
        "clip_id": "approved_clip",
        "url": "https://www.youtube.com/watch?v=abc123",
        "start_seconds": 10,
        "end_seconds": 22,
        "rights_basis": "creative_commons",
        "approved_by": "Editor",
        "attribution": "Example Creator — Example Video",
    }
    payload.update(overrides)
    return LicensedClipRequest(**payload)


def test_standard_youtube_license_is_not_treated_as_reusable():
    with pytest.raises(PermissionError, match="does not identify"):
        _verify_rights(_request(), {"license": "Standard YouTube License", "id": "abc123"})


def test_creative_commons_license_is_accepted_with_attribution():
    rights = _verify_rights(
        _request(),
        {"license": "Creative Commons Attribution license (reuse allowed)", "id": "abc123"},
    )
    assert rights["basis"] == "creative_commons"
    assert rights["attribution"].startswith("Example Creator")


def test_permissioned_clip_requires_a_local_proof_record():
    with pytest.raises(ValidationError, match="rights_proof_file"):
        _request(rights_basis="written_permission")


def test_automatic_clip_length_is_bounded():
    with pytest.raises(ValidationError, match="45 seconds"):
        _request(start_seconds=0, end_seconds=46)


def test_clip_id_cannot_be_reused_for_a_different_contract(tmp_path):
    request = _request()
    target = tmp_path / request.clip_id
    target.mkdir()
    request_hash = hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (target / "rights_ledger.json").write_text(
        json.dumps({"request_hash": request_hash}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="already bound"):
        ingest_licensed_clip(_request(end_seconds=23), tmp_path)
