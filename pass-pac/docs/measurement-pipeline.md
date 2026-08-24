# PASS-PAC Controlled Measurement Pipeline

Version: 1.0
Methodology identifier: `controlled-measurement-v1.0`

## Purpose

The measurement pipeline separates controlled experimental trials from simulator records and ordinary device observations. A trial is one bounded presentation of one authorized credential under documented conditions.

## Data Model

### Experiment Batch

An experiment batch records conditions shared by a group of trials:

- baseline or post-remediation condition;
- authorization reference and pseudonymous operator label;
- location label;
- Proxmark model, client version, and firmware version;
- antenna configuration and host operating system;
- command profile and environmental notes; and
- start, completion, creation, and update timestamps.

A completed batch rejects new trials until an operator explicitly reopens it.

### Measurement Trial

Each trial records:

- session, batch, sequential trial number, and credential alias;
- optional link to a PASS-PAC card observation;
- technology and card family;
- distance, orientation, and presented face;
- detection success and classification result;
- identification duration in milliseconds;
- parsed metadata field count and extracted byte count;
- nearby-metal and RF-interference conditions;
- notes and timestamps; and
- a SHA-256 evidence hash when a source observation is linked.

The observation link is optional because a failed presentation may produce no card record. Failures must still be retained as trials.

## Evidence Linking

When a trial references a card observed in the same session, the backend:

1. verifies that the observation belongs to the session;
2. fills missing technology and card-family fields from the observation;
3. serializes normalized and raw observation data in canonical key order; and
4. stores the SHA-256 digest with the trial.

The hash supports integrity comparison without publishing raw credential evidence.

## Statistics

The session summary reports:

- batch, trial, and unique-credential counts;
- detection success rate across every trial, including failures;
- classification accuracy over `correct` and `incorrect` labels, excluding `inconclusive` labels;
- successful-identification timing count, minimum, maximum, median, first quartile, and third quartile;
- technology-level success, classification, timing, metadata, and extracted-byte summaries; and
- reliable read distance by credential, orientation, and presented face.

Reliable identification distance is the greatest tested distance with at least five attempts, at least four successful and correctly classified identifications, and a correct-identification rate of at least 80 percent for the same credential, orientation, and face. Partial protocol responses without a matching credential classification do not qualify.

## API

- `GET /api/v1/sessions/{session_id}/experiment-batches`
- `POST /api/v1/sessions/{session_id}/experiment-batches`
- `PATCH /api/v1/sessions/{session_id}/experiment-batches/{batch_id}`
- `GET /api/v1/sessions/{session_id}/measurement-trials`
- `POST /api/v1/sessions/{session_id}/measurement-trials`
- `PATCH /api/v1/sessions/{session_id}/measurement-trials/{trial_id}`
- `DELETE /api/v1/sessions/{session_id}/measurement-trials/{trial_id}`
- `GET /api/v1/sessions/{session_id}/measurement-summary`

## Operator Workflow

1. Open a session and select **Research Measurements**.
2. Create an experiment batch with authorization and equipment metadata.
3. Record every attempt, including failed or inconclusive attempts.
4. Link a source observation when one exists.
5. Complete the batch after its controlled trials finish.
6. Use the technology comparison and reliable-distance output in the research analysis.

CSV and PDF export consumes these trial-level records through the process documented in `docs/reporting-methodology.md`.
