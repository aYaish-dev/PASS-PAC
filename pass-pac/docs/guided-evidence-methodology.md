# Guided Evidence Methodology

## Purpose

The Guided Evidence Engine converts the current assessment state into a ranked, repeatable evidence-acquisition sequence. It does not predict risk with a language model and does not award points merely because a card family is capable of a security feature. Recommendations are derived from recorded evidence, explicit assurance unknowns, experiment state, and a versioned command registry.

## Inputs

- scan session mode and lifecycle state
- detected credential type, protocol, and normalized Proxmark metadata
- completed operator and automated-assessment commands
- five-criterion assurance results and evidence coverage
- critical findings, transaction traces, experiment batches, and trials
- selected assurance policy

## Deterministic Sequence

1. Establish device identity, status, and antenna tuning evidence.
2. Acquire an HF or LF identity observation when the session has no credentials.
3. Complete the matching family metadata recipe for each observed credential.
4. Surface unknown assurance criteria as evidence gaps rather than assumed failures or strengths.
5. Prioritize explicit critical indicators before general evidence completion.
6. Require a controlled baseline before remediation claims.
7. Recommend a matched post-remediation batch only after the baseline is complete.
8. Recommend passive transaction analysis where static metadata cannot establish authentication or replay resistance.

Ranking is stable: lower numerical rank is shown first. Priority labels (`now`, `next`, and `later`) communicate workflow order but do not change the security score.

## Command Safety Boundary

`backend/app/core/proxmark_capabilities.json` is the single source of truth for commands and recipes. Every Phase A command must declare:

- `read_only: true`
- `changes_state: false`
- protocol, operation, safety tier, selector, and expected evidence

The registry loader rejects duplicate commands, unknown recipe references, and any command that violates the Phase A safety invariant. The backend adapter and Windows host bridge both derive their allowlists from the same registry.

## Evidence Interpretation

- Missing evidence remains unknown and lowers coverage; it is not automatically scored as insecure.
- Card metadata alone cannot prove reader/controller enforcement, key diversification, revocation, or monitoring.
- A passive trace can show protocol behavior but cannot prove the access controller's final decision.
- A completed recipe records session-level command evidence. The operator must present the intended authorized credential while the recipe runs.
- Manual evidence steps require authorized configuration, governance, or isolated-reader records and cannot be executed automatically.

## Outputs

`GET /api/v1/sessions/{session_id}/evidence-guidance` returns:

- engine and registry versions
- overall evidence status and coverage metrics
- credential-level score range, policy result, critical indicator, and unknown criteria
- ordered recommendations with rationale, expected evidence, safety tier, action type, and blockers

The UI renders the same output in the Session Operator Panel under **Guided Evidence**.

## Current Limitation

Operator command records are session-scoped and do not yet identify which physical credential was present for each command. Phase A therefore treats successful recipe execution as session evidence and depends on the operator instruction to present the intended card. A future evidence-provenance migration should add `card_id`, acquisition context, and evidence hashes to each command run.
