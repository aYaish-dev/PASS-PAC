# PASS-PAC Reporting And Remediation Comparison

Version: 1.2
Report identifier: `measurement-report-v1.2`

## Research Outputs

PASS-PAC generates three local research artifacts from controlled measurement records:

- a UTF-8 CSV containing one row per trial for Excel, Python, R, or other analysis tools; and
- a UTF-8 analysis CSV containing one row per credential, distance, orientation, and face condition; and
- a paginated PDF containing the method, controlled setup, Wilson 95% intervals, timing quartiles, quality flags, Credential and Access Path Security Score v2.1, optional remediation comparison, limitations, and anonymized trial appendix.

Both files are saved under `reports/session-{session_id}/`. The browser also downloads the selected artifact. Every HTTP response includes the artifact SHA-256 digest in the `X-PASS-PAC-SHA256` header.

## Privacy Boundary

Research exports include:

- research credential alias;
- controlled setup and authorization reference;
- technology and card family;
- trial conditions and outcomes;
- timing and metadata quantities; and
- evidence SHA-256 digest.

Research exports exclude:

- operational UID;
- raw Proxmark output;
- card keys or memory contents;
- personal identity; and
- reader, controller, or door mappings.

The source database remains local. An exported evidence digest supports integrity comparison but cannot reconstruct the omitted source evidence.

## CSV Data Dictionary

The CSV groups fields into:

1. Report provenance: report version, methodology version, session ID, and session name.
2. Controlled batch: condition, authorization reference, pseudonymous operator, location, equipment, versions, antenna, host, and command profile.
3. Trial identity: internal trial ID, sequential number, and credential alias.
4. Independent variables: technology, family, distance, orientation, presented face, metal, and RF interference.
5. Dependent variables: detection outcome, classification result, duration, metadata field count, and extracted byte count.
6. Integrity and audit: evidence digest, notes, and recording timestamp.

Failed and inconclusive attempts are exported. Empty values remain empty and must not be silently interpreted as zero.

## Analysis CSV

The condition-level analysis CSV reports:

1. Credential alias, technology, card family, distance, orientation, and presented face.
2. Attempt count and whether the minimum five repetitions was reached.
3. Detection count, rate, and Wilson 95% confidence interval.
4. Correct-identification count, rate, and Wilson 95% confidence interval.
5. Partial, incorrect, and inconclusive response counts.
6. Correct-identification median, first quartile, and third quartile timing.
7. Reliable-identification distance under the documented 4-of-5 threshold.

The analysis CSV excludes UIDs, raw device output, key material, and memory contents.

## Baseline Comparison

The comparison accepts exactly one batch labeled `baseline` and one batch labeled `post_remediation` from the same session. It reports:

- trial and unique-credential count changes;
- detection-rate change in percentage points;
- classification-accuracy change in percentage points;
- successful-identification median-time change in milliseconds; and
- reliable-distance change for matching credential, orientation, and face groups.

Delta is calculated as:

```text
delta = post-remediation value - baseline value
```

For readable distance, a negative delta may represent reduced passive exposure after a countermeasure. For detection and classification, interpretation depends on the experimental objective. PASS-PAC therefore reports values and context rather than automatically labeling every positive delta as an improvement.

## Interpretation Rules

- Detection rate denominator: all trials.
- Classification accuracy denominator: only correct and incorrect classifications.
- Timing population: successful identifications only.
- Reliable identification distance: at least five attempts, at least four successful and correctly classified identifications, and at least 80 percent correct identification under the same position condition.
- Missing baseline or post values produce an unavailable delta, not zero.
- Descriptive deltas do not establish statistical significance.
- Comparisons are valid only when equipment, procedure, positioning, environment, and credential scope are sufficiently controlled and documented.

## API

- `GET /api/v1/sessions/{session_id}/measurement-comparison`
- `GET /api/v1/sessions/{session_id}/measurement-analysis`
- `POST /api/v1/sessions/{session_id}/reports/measurements.csv`
- `POST /api/v1/sessions/{session_id}/reports/measurement-analysis.csv`
- `POST /api/v1/sessions/{session_id}/reports/research-report.pdf`

The PDF endpoint accepts optional `baseline_batch_id` and `post_remediation_batch_id` query parameters. Both must be supplied together.
