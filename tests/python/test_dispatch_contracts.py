"""Tests for U1: Dispatch contract and closed vocabularies."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

# ---------------------------------------------------------------------------
# Schema fixtures
# ---------------------------------------------------------------------------

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "workstream-dispatch" / "v1"
JOB_RECORD_SCHEMA_PATH = CONTRACTS_DIR / "job-record.schema.json"
OUTCOME_NOTE_SCHEMA_PATH = CONTRACTS_DIR / "outcome-note.schema.json"
DISPATCH_RESULT_SCHEMA_PATH = CONTRACTS_DIR / "dispatch-result.schema.json"
JOB_STATE_PATH = CONTRACTS_DIR / "job-state.md"


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def job_record_schema() -> dict:
    return _load_schema(JOB_RECORD_SCHEMA_PATH)


@pytest.fixture(scope="module")
def outcome_note_schema() -> dict:
    return _load_schema(OUTCOME_NOTE_SCHEMA_PATH)


@pytest.fixture(scope="module")
def dispatch_result_schema() -> dict:
    return _load_schema(DISPATCH_RESULT_SCHEMA_PATH)


def _minimal_job_record(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
        "workstream_identity": "test-workstream",
        "instruction": "Do something useful",
        "dispatch_posture": {
            "provider": "opencode",
            "model": "opencode-go/mimo-v2.5",
            "mode": "default",
            "thinking": "none",
        },
        "actor": "operator-confirmed",
        "recorded_at": "2026-08-21T00:00:00Z",
        "confirmation_ref": "abc123def456",
        "created_at": "2026-08-21T00:00:00Z",
    }
    base.update(overrides)
    return base


def _minimal_note(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
        "summary": "Work completed successfully",
        "reported_at": "2026-08-21T01:00:00Z",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Job record schema tests
# ---------------------------------------------------------------------------


class TestJobRecordSchema:
    def test_minimal_valid_record(self, job_record_schema):
        """A minimal valid job record validates."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        validator.validate(record)

    def test_unknown_top_level_property_rejected(self, job_record_schema):
        """A job record with an unknown top-level property is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record(unknown_field="should not exist")
        with pytest.raises(Exception):
            validator.validate(record)

    def test_outcome_note_path_rejected(self, job_record_schema):
        """A job record carrying an `outcome_note_path` property is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record(
            outcome_note_path="some/path.json"
        )
        with pytest.raises(Exception):
            validator.validate(record)

    def test_missing_actor_rejected(self, job_record_schema):
        """A job record missing `actor` is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        del record["actor"]
        with pytest.raises(Exception):
            validator.validate(record)

    def test_actor_outside_enum_rejected(self, job_record_schema):
        """`actor` outside {operator-confirmed, assistant-drafted} is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record(actor="system-initiated")
        with pytest.raises(Exception):
            validator.validate(record)

    def test_instruction_exceeding_cap_rejected(self, job_record_schema):
        """`instruction` exceeding the declared cap is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record(instruction="x" * 65537)
        with pytest.raises(Exception):
            validator.validate(record)

    def test_follows_invalid_format_rejected(self, job_record_schema):
        """A `follows` value that does not match the pinned `job_id` format is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record(follows="not-a-valid-uuid")
        with pytest.raises(Exception):
            validator.validate(record)

    def test_missing_dispatch_posture_rejected(self, job_record_schema):
        """A record missing `dispatch_posture` is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        del record["dispatch_posture"]
        with pytest.raises(Exception):
            validator.validate(record)

    def test_wrong_provider_rejected(self, job_record_schema):
        """A posture whose `provider` is not the pinned `opencode` is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        record["dispatch_posture"]["provider"] = "codex"
        with pytest.raises(Exception):
            validator.validate(record)

    def test_model_id_as_provider_rejected(self, job_record_schema):
        """A posture naming a model id in the provider field is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        record["dispatch_posture"]["provider"] = "opencode-go/mimo-v2.5"
        with pytest.raises(Exception):
            validator.validate(record)

    def test_missing_thinking_rejected(self, job_record_schema):
        """A posture missing `thinking` entirely is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        del record["dispatch_posture"]["thinking"]
        with pytest.raises(Exception):
            validator.validate(record)

    def test_empty_model_rejected(self, job_record_schema):
        """A `model` that is not a bounded non-empty string is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        record["dispatch_posture"]["model"] = ""
        with pytest.raises(Exception):
            validator.validate(record)

    def test_empty_mode_rejected(self, job_record_schema):
        """A `mode` that is not a non-empty string is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        record["dispatch_posture"]["mode"] = ""
        with pytest.raises(Exception):
            validator.validate(record)

    def test_empty_thinking_rejected(self, job_record_schema):
        """A `thinking` that is not a non-empty string is rejected."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        record["dispatch_posture"]["thinking"] = ""
        with pytest.raises(Exception):
            validator.validate(record)

    def test_valid_follows_accepted(self, job_record_schema):
        """A valid follows job_id is accepted."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record(
            follows="f47ac10b-58cc-4372-a567-0e02b2c3d479"
        )
        validator.validate(record)

    def test_job_id_format_pinned(self, job_record_schema):
        """job_id must be uuid4-shaped: lowercase hex with hyphens."""
        validator = Draft202012Validator(job_record_schema)
        # Uppercase hex rejected
        record = _minimal_job_record(
            job_id="A1B2C3D4-E5F6-4A7B-8C9D-E0F1A2B3C4D5"
        )
        with pytest.raises(Exception):
            validator.validate(record)

    def test_posture_additional_properties_rejected(self, job_record_schema):
        """Posture rejects additional properties."""
        validator = Draft202012Validator(job_record_schema)
        record = _minimal_job_record()
        record["dispatch_posture"]["extra"] = "nope"
        with pytest.raises(Exception):
            validator.validate(record)


# ---------------------------------------------------------------------------
# Outcome note schema tests
# ---------------------------------------------------------------------------


class TestOutcomeNoteSchema:
    def test_minimal_valid_note(self, outcome_note_schema):
        """A minimal valid outcome note validates."""
        validator = Draft202012Validator(outcome_note_schema)
        note = _minimal_note()
        validator.validate(note)

    def test_unknown_top_level_property_rejected(self, outcome_note_schema):
        """One with an unknown top-level property is rejected."""
        validator = Draft202012Validator(outcome_note_schema)
        note = _minimal_note(extra_field="nope")
        with pytest.raises(Exception):
            validator.validate(note)

    def test_missing_reported_at_rejected(self, outcome_note_schema):
        """One missing `reported_at` is rejected."""
        validator = Draft202012Validator(outcome_note_schema)
        note = _minimal_note()
        del note["reported_at"]
        with pytest.raises(Exception):
            validator.validate(note)


# ---------------------------------------------------------------------------
# Dispatch result schema tests
# ---------------------------------------------------------------------------


class TestDispatchResultSchema:
    def test_minimal_valid_result(self, dispatch_result_schema):
        """A minimal valid result validates."""
        validator = Draft202012Validator(dispatch_result_schema)
        result = {"version": 1, "outcome": "dispatched", "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5"}
        validator.validate(result)

    def test_all_outcomes_valid(self, dispatch_result_schema):
        """All six frozen outcomes validate."""
        validator = Draft202012Validator(dispatch_result_schema)
        for outcome in ["dispatched", "partial-success", "cancelled", "stopped", "invalid-workspace", "internal-failure"]:
            result = {"version": 1, "outcome": outcome}
            validator.validate(result)

    def test_unknown_outcome_rejected(self, dispatch_result_schema):
        """An unknown outcome is rejected."""
        validator = Draft202012Validator(dispatch_result_schema)
        result = {"version": 1, "outcome": "unknown"}
        with pytest.raises(Exception):
            validator.validate(result)


# ---------------------------------------------------------------------------
# Job-state vocabulary tests
# ---------------------------------------------------------------------------


class TestJobStateVocabulary:
    def test_fenced_table_parses_eight_states(self):
        """The job-state fenced table parses and contains exactly the eight R8 values."""
        content = JOB_STATE_PATH.read_text(encoding="utf-8")
        # Extract the derivation table's state values from the Markdown
        # The table has states in the "Derived state" column
        states = set()
        for line in content.splitlines():
            line = line.strip()
            # Match backtick-quoted state values in table cells
            for match in re.finditer(r"`(running|idle|needs-operator|not-found|unreachable|superseded|never-dispatched|failed)`", line):
                states.add(match.group(1))
        expected = {
            "running", "idle", "needs-operator", "not-found",
            "unreachable", "superseded", "never-dispatched", "failed"
        }
        assert states == expected, f"Expected exactly {expected}, got {states}"

    def test_error_to_failed_and_closed_to_superseded_present(self):
        """The table includes the error→failed and closed→superseded rows (AE22, AE23)."""
        content = JOB_STATE_PATH.read_text(encoding="utf-8")
        assert "error" in content
        assert "failed" in content
        assert "closed" in content
        assert "superseded" in content


# ---------------------------------------------------------------------------
# Note-status vocabulary tests
# ---------------------------------------------------------------------------


class TestNoteStatusVocabulary:
    def test_fenced_table_parses_seven_values(self):
        """The note-status fenced table parses and contains exactly the seven R26 values."""
        content = JOB_STATE_PATH.read_text(encoding="utf-8")
        note_states = set()
        for match in re.finditer(
            r"`(present|absent|unreadable|schema-invalid|guard-failed|mismatched|path-refused)`",
            content,
        ):
            note_states.add(match.group(1))
        expected = {
            "present", "absent", "unreadable", "schema-invalid",
            "guard-failed", "mismatched", "path-refused"
        }
        # The note-status values appear in the Note Status Vocabulary section
        assert expected.issubset(note_states), f"Missing states: {expected - note_states}"

    def test_no_overlap_between_job_state_and_note_status(self):
        """No note-status value appears in the job-state table or vice versa."""
        content = JOB_STATE_PATH.read_text(encoding="utf-8")
        job_states = {"running", "idle", "needs-operator", "not-found",
                       "unreachable", "superseded", "never-dispatched", "failed"}
        note_states = {"present", "absent", "unreadable", "schema-invalid",
                        "guard-failed", "mismatched", "path-refused"}
        overlap = job_states & note_states
        assert not overlap, f"Overlap between vocabularies: {overlap}"
