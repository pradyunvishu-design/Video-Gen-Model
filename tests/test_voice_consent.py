import hashlib

import pytest

from pipeline import production
from pipeline.production import validate_voice_consent, voice_rights_record


def test_voice_consent_must_be_explicit_and_match_sample(tmp_path):
    sample = tmp_path / "voice.mp3"
    sample.write_bytes(b"voice sample")
    consent = tmp_path / "consent.txt"
    consent.write_text(
        "VOICE_OWNER=Test Speaker\n"
        "CONSENT_TO_AI_VOICE_CLONING=YES\n"
        "CONSENT_TO_COMMERCIAL_PUBLICATION=YES\n"
        "SERVICE=Magic Hour\n"
        "DATE=2026-08-05\n"
        "SIGNATURE=Test Speaker\n"
        f"SAMPLE_SHA256={hashlib.sha256(sample.read_bytes()).hexdigest()}\n",
        encoding="utf-8",
    )

    values = validate_voice_consent(consent, sample)

    assert values["VOICE_OWNER"] == "Test Speaker"


def test_voice_consent_rejects_placeholder_or_wrong_hash(tmp_path):
    sample = tmp_path / "voice.mp3"
    sample.write_bytes(b"voice sample")
    consent = tmp_path / "consent.txt"
    consent.write_text(
        "VOICE_OWNER=<name>\n"
        "CONSENT_TO_AI_VOICE_CLONING=YES\n"
        "CONSENT_TO_COMMERCIAL_PUBLICATION=YES\n"
        "SERVICE=Magic Hour\n"
        "DATE=2026-08-05\n"
        "SIGNATURE=<name>\n"
        "SAMPLE_SHA256=wrong\n",
        encoding="utf-8",
    )

    with pytest.raises(PermissionError):
        validate_voice_consent(consent, sample)


def test_user_attestation_allows_voice_clone_before_form_is_filed(tmp_path, monkeypatch):
    sample = tmp_path / "voice.mp3"
    sample.write_bytes(b"approved synthetic voice sample")
    monkeypatch.setattr(production, "VOICE_CONSENT_ATTESTED", True)

    record = voice_rights_record(tmp_path / "not-filed-yet.txt", sample)

    assert record["status"] == "consent_attested_documentation_pending"
    assert record["documentation_pending"] is True
    assert record["sample_sha256"] == hashlib.sha256(sample.read_bytes()).hexdigest()


def test_missing_form_and_missing_attestation_still_fail(tmp_path, monkeypatch):
    sample = tmp_path / "voice.mp3"
    sample.write_bytes(b"voice sample")
    monkeypatch.setattr(production, "VOICE_CONSENT_ATTESTED", False)

    with pytest.raises(PermissionError):
        voice_rights_record(tmp_path / "missing.txt", sample)
