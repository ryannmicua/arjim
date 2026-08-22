# Job State Vocabulary — v1

## Job State Enum

The closed job-state vocabulary for dispatched jobs. Eight values (R8):

```
running | idle | needs-operator | not-found | unreachable | superseded | never-dispatched | failed
```

Each job reports exactly one value from this set. The vocabulary is independent of the registration outcome vocabulary and the note-status vocabulary.

## Job-State Derivation Table

The single owner of the R8 mapping. Inputs: whether the local binding exists, whether a label lookup resolves an agent, the agent's `status`, whether its pending-permission list is non-empty, and whether it is archived.

| Local binding | Label resolves an agent | Agent condition | Derived state |
|---|---|---|---|
| any | Paseo unreachable | — | `unreachable` |
| any | yes | pending permissions non-empty | `needs-operator` |
| any | yes | `status = running` | `running` |
| any | yes | `status = idle`, not archived | `idle` |
| any | yes | `status = error` | `failed` |
| any | yes | `status = closed` | `superseded` |
| any | yes | `status = archived` | `superseded` |
| any | yes | status outside the observed set | `needs-operator` |
| present | no | — | `not-found` |
| absent | no | — | `never-dispatched` |

`unreachable` is evaluated first so a dead daemon can never be mistaken for absent work.

### Rationale for key rows

- **`error` → `failed`:** A failed agent must never render as idle (R9). `failed` asserts only that Paseo reported a fault; it asserts no retry, recovery, or outcome.
- **`closed` → `superseded`:** A closed agent's run ended without Paseo asserting a fault. `superseded` claims nothing about the work's outcome, which `failed` would. `superseded` is distinct from `not-found` (the agent existed) and from `idle` (the agent is no longer available).
- **Unrecognized status → `needs-operator`:** The table never guesses a state that could render a failed or unclassifiable agent as idle (R9). An unrecognized status is surfaced to the operator.

## Note Status Vocabulary

The closed note-status vocabulary for outcome notes. Seven values (R26):

```
present | absent | unreadable | schema-invalid | guard-failed | mismatched | path-refused
```

### Orthogonality to Job State

Note status is reported per job in addition to its job state and never substitutes for one. No note status changes a derived job state. The two vocabularies are independent:

- `present` means the note exists, passes schema validation, passes the guard, and has a matching `job_id`. It is attached as an unverified workspace note associated with the job.
- `absent` means no note file exists at the derived path.
- `unreadable` means the note file exists but cannot be read (permission error, I/O error).
- `schema-invalid` means the note file exists and is readable but fails the outcome-note schema validation.
- `guard-failed` means the note file exists, is readable, and passes schema validation, but its content is rejected by the dispatch-local guard (C0/C1, bidi, Tag block, zero-width, variation selectors). It renders as "note present, unrenderable — open the agent" with a stable code, distinct from `absent` (the operator learns a claim exists that Arjim will not repeat).
- `mismatched` means the note's `job_id` differs from its record's. The note is never rendered under any job.
- `path-refused` means the derived note path failed the containment or reparse-point check so its bytes were never read. It is distinct from `guard-failed` (a note was read and its content rejected), distinct from `absent` (something occupies the path and Arjim declined to open it), and distinct from `unreadable` (the path check itself refused, not an I/O error).
