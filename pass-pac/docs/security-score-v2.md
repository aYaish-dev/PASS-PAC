# PASS-PAC Credential and Access Path Security Score v2.1

Version: 2.1
Scale: 0-10
Engine identifier: `assurance-engine-v2.1`

## 1. Purpose

The Access Path Security Score summarizes observed security properties of one credential path. It is not a certification and must always be shown with evidence coverage, confidence, and an uncertainty range.

The score is stable across policy profiles. A policy selects the minimum acceptable score and evidence coverage; it does not change the underlying technical score.

PASS-PAC reports two related results:

- **Credential technical rating:** authentication, key management, and clone/replay resistance derived from the card and protocol evidence.
- **Complete access-path assurance:** the credential result plus reader/backend enforcement and lifecycle monitoring.

This separation allows a weak credential to be reported clearly without pretending that a card scan proves how a building controller or credential-management process operates.

## 2. Criteria

Five criteria receive equal maximum values of two points.

| Criterion | 0 points | 1 point | 2 points |
|---|---|---|---|
| Authentication strength | No cryptographic authentication or static identifier only | Legacy, weak, or capability-only authentication | Observed modern mutual or cryptographic authentication |
| Key management | No keys, default keys, or known shared transport keys | Custom but shared or incompletely governed keys | Verified diversified keys with managed lifecycle evidence |
| Clone and replay resistance | UID-modifiable, static replayable identifier, or equivalent critical indicator | Some resistance with a known legacy weakness or incomplete freshness evidence | Observed challenge-response, freshness, secure messaging, or transaction integrity |
| Reader and backend enforcement | UID-only authorization is verified | Partial application/backend validation | Cryptographic reader enforcement and backend binding are verified |
| Lifecycle and monitoring | No revocation, logging, or duplicate monitoring | Partial or manual controls | Verified revocation, audit logging, and credential anomaly monitoring |

`Unknown` is not a rating. It means the available evidence cannot justify 0, 1, or 2.

## 3. Evidence Rules

- Ratings must cite the exact normalized field, raw command evidence, authorized configuration record, or controlled reader result.
- A card-family label may establish known protocol capability or known absence of cryptography, but it must not prove reader enforcement or key diversification.
- Analyst review status cannot add security points.
- Simulator provenance cannot by itself prove a live deployment property.
- Absence of an authentication frame in an incomplete passive trace cannot prove UID-only authorization.
- A modern credential family with no observed configuration evidence receives at most a capability-level rating, not an automatic maximum.
- Operator-supplied reader or lifecycle evidence must include a source, assessment time, confidence, and optional notes.
- Operator evidence is stored separately from device output and never changes credential-derived criteria.

### Operator evidence states

Reader and backend enforcement uses one of three documented states:

- `uid_only` = 0 points;
- `partial` = 1 point; or
- `cryptographic` = 2 points.

Lifecycle and monitoring uses:

- `absent` = 0 points;
- `partial` = 1 point; or
- `managed` = 2 points.

An unselected state remains `Unknown`; it is never silently converted to zero.

## 4. Calculation

Let `r_i` be each known criterion rating and let `k` be the number of known criteria.

```text
provisional score = 5 * sum(r_i) / k
coverage percent = 100 * k / 5
minimum possible score = sum(r_i)
maximum possible score = sum(r_i) + 2 * (5 - k)
```

The provisional score is rounded to one decimal place. If no criterion is known, the score is null and the possible range is 0-10.

The credential technical rating applies the same normalized formula to the first three criteria and reports its own evidence coverage. It receives a descriptive credential grade only when at least two of those three criteria are known. Policy pass/fail decisions always use the complete five-criterion access-path result.

At 100 percent coverage, the provisional score equals the direct sum of the five ratings.

Example: ratings `[2, 1, Unknown, 0, Unknown]` produce a provisional score of `5.0/10`, 60 percent coverage, and a possible range of `3-7`.

## 5. Grades

Grades are issued only when evidence coverage is at least 80 percent.

| Score | Grade |
|---|---|
| 8.5-10 | Strong |
| 7.0-8.4 | Moderate |
| 5.0-6.9 | Limited |
| 0-4.9 | Weak |

Below 80 percent coverage, the grade is `Inconclusive` even when the provisional score is high.

## 6. Critical Failures

A critical failure is reported separately from the numeric score. Examples include:

- verified UID-only authorization for an access path;
- a UID-modifiable credential accepted by the scoped reader;
- a static LF identifier used without another authentication factor;
- observed default keys protecting access-relevant MIFARE data;
- conflicting credential identities indicating a duplicate or parser-integrity issue.

Critical failures do not activate an opaque score cap. Instead, policies can explicitly reject any path containing a critical failure.

## 7. Policy Profiles

| Policy | Minimum score | Minimum coverage | Critical failures |
|---|---:|---:|---|
| University Standard | 6.0 | 80% | Reject |
| Restricted Area | 8.0 | 100% | Reject |
| Legacy Transition | 4.0 | 60% | Reject for approval; retain for migration tracking |

Policy status is:

- `insufficient_evidence` when coverage is below the policy minimum;
- `fail` when a critical failure is rejected or the score is below the minimum; or
- `pass` when coverage, score, and critical-failure requirements are satisfied.

## 8. Confidence

Confidence describes evidence completeness and provenance, not security strength.

- High: at least 80 percent coverage supported by live device, trace, reader, or authorized configuration evidence.
- Medium: at least 60 percent coverage, or high coverage dominated by simulator/reference evidence.
- Low: less than 60 percent coverage.

## 9. Analyst Review

Analyst review is reported independently as:

- total findings;
- active findings;
- unresolved high or critical findings; and
- review status (`not_started`, `in_progress`, or `complete`).

Resolving a finding changes workflow status. The security score changes only after new technical or operational evidence demonstrates remediation.

## 10. Validation

The score must be validated using:

1. Unit tests for every rating branch and unknown-evidence behavior.
2. Reference profiles with known expected ratings.
3. Independent scoring by both project members on the same evidence set.
4. Agreement reporting and resolution of disagreements.
5. Sensitivity discussion showing how conclusions would change under alternative criterion importance.
6. Baseline-versus-remediation cases using the same engine and policy version.
