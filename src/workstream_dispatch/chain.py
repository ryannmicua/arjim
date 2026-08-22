"""Chained follow-up proposal (U7).

Reconstructs chains at answer time by joining job records on ``follows``
and overlaying each predecessor's derived state from U6.  Proposes a
follow-on step whenever the predecessor is not ``running``, naming its
observed state.  Routes acceptance back through U5's draft-confirm-dispatch
path with ``follows`` set.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workstream_dispatch.activity import JobAnswer, _JOB_STATE_RUNNING


@dataclass(frozen=True)
class ChainProposal:
    """A proposed follow-on step for a chain."""

    predecessor_job_id: str
    predecessor_state: str
    successor_follows: str


def propose_follow_on(
    predecessor: JobAnswer,
) -> ChainProposal | None:
    """Propose a follow-on step if the predecessor is not running (R14, R15).

    A follow-on step is proposed only within an operator-initiated status
    answer.  No timer, daemon, or background thread advances a chain.
    """
    if predecessor.job_state == _JOB_STATE_RUNNING:
        return None

    return ChainProposal(
        predecessor_job_id=predecessor.job_id,
        predecessor_state=predecessor.job_state,
        successor_follows=predecessor.job_id,
    )


def build_chain_from_records(
    records: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Reconstruct chains from job records alone (R13).

    Joins records on ``follows`` and returns ordered chains.
    A chain of three records reconstructs in order from records alone.
    """
    if not records:
        return []

    # Pre-build reverse index: successor_id → record
    followers: dict[str, dict[str, Any]] = {}
    for r in records:
        follows = r.get("follows")
        if follows:
            followers[follows] = r

    # Find chain heads: records that do NOT follow any other record
    heads = [r for r in records if not r.get("follows")]

    chains: list[list[dict[str, Any]]] = []
    for head in heads:
        chain = [head]
        current_id = head["job_id"]
        while True:
            successor = followers.get(current_id)
            if successor is None:
                break
            chain.append(successor)
            current_id = successor["job_id"]
        chains.append(chain)

    return chains
