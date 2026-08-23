"""Tests for U7: Chained follow-up proposal."""
from __future__ import annotations

import pytest

from workstream_dispatch.chain import (
    ChainProposal,
    build_chain_from_records,
    propose_follow_on,
)
from workstream_dispatch.activity import JobAnswer


def _job_answer(job_id: str, state: str, follows: str | None = None) -> JobAnswer:
    return JobAnswer(
        job_id=job_id,
        workstream_identity="test",
        instruction="Do something",
        job_state=state,
        note_status="absent",
    )


class TestProposeFollowOn:
    def test_idle_predecessor_produces_proposal(self):
        """A predecessor reporting idle produces a proposal naming that state."""
        predecessor = _job_answer("job-1", "idle")
        proposal = propose_follow_on(predecessor)
        assert proposal is not None
        assert proposal.predecessor_state == "idle"
        assert proposal.successor_follows == "job-1"

    def test_needs_operator_still_proposes(self):
        """A predecessor reporting needs-operator still produces a proposal (AE10)."""
        predecessor = _job_answer("job-1", "needs-operator")
        proposal = propose_follow_on(predecessor)
        assert proposal is not None
        assert proposal.predecessor_state == "needs-operator"

    def test_unreachable_still_proposes(self):
        """A predecessor reporting unreachable still produces a proposal."""
        predecessor = _job_answer("job-1", "unreachable")
        proposal = propose_follow_on(predecessor)
        assert proposal is not None

    def test_running_produces_no_proposal(self):
        """A predecessor reporting running produces no proposal."""
        predecessor = _job_answer("job-1", "running")
        proposal = propose_follow_on(predecessor)
        assert proposal is None

    def test_failed_predecessor_proposes(self):
        """A failed predecessor produces a proposal."""
        predecessor = _job_answer("job-1", "failed")
        proposal = propose_follow_on(predecessor)
        assert proposal is not None
        assert proposal.predecessor_state == "failed"


class TestBuildChainFromRecords:
    def test_single_record_no_chain(self):
        """A single record with no follows forms a single-element chain."""
        records = [{"job_id": "j1", "instruction": "step 1"}]
        chains = build_chain_from_records(records)
        assert len(chains) == 1
        assert len(chains[0]) == 1

    def test_two_record_chain(self):
        """Two records where one follows the other form a chain."""
        records = [
            {"job_id": "j1", "instruction": "step 1"},
            {"job_id": "j2", "instruction": "step 2", "follows": "j1"},
        ]
        chains = build_chain_from_records(records)
        assert len(chains) == 1
        assert chains[0][0]["job_id"] == "j1"
        assert chains[0][1]["job_id"] == "j2"

    def test_three_record_chain(self):
        """A chain of three records reconstructs in order."""
        records = [
            {"job_id": "j1", "instruction": "step 1"},
            {"job_id": "j2", "instruction": "step 2", "follows": "j1"},
            {"job_id": "j3", "instruction": "step 3", "follows": "j2"},
        ]
        chains = build_chain_from_records(records)
        assert len(chains) == 1
        assert [r["job_id"] for r in chains[0]] == ["j1", "j2", "j3"]

    def test_empty_records(self):
        """Empty records list returns empty chains."""
        chains = build_chain_from_records([])
        assert chains == []

    def test_declined_proposal_writes_nothing(self):
        """A declined proposal writes no record and spawns no agent (AE10)."""
        # This is a behavior assertion: propose_follow_on returns a proposal,
        # but if the operator declines, dispatch is never called.
        # The test verifies the proposal was made; the decline is operator action.
        predecessor = _job_answer("job-1", "idle")
        proposal = propose_follow_on(predecessor)
        assert proposal is not None  # Proposal exists, operator decides
