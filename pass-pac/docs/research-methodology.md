# PASS-PAC Research Methodology

Version: 1.0
Status: Experimental protocol for the final engineering study
Scope: Authorized, local RFID/NFC physical-access security assessment

## 1. Research Objective

PASS-PAC investigates whether heterogeneous physical-access credentials can be assessed through a repeatable, evidence-driven workflow that connects raw RFID/NFC observations to normalized measurements, explainable security scores, and actionable countermeasures.

The project is not intended to prove that every system using a named card family has the same security posture. Card configuration, reader behavior, backend enforcement, key management, and operational controls all affect the resulting access path.

## 2. Research Questions

- RQ1: How reliably can PASS-PAC identify and normalize different authorized LF and HF credential families from Proxmark3 evidence?
- RQ2: How do detection success, reliable read distance, identification time, accessible metadata, and observed authentication behavior differ between credential technologies?
- RQ3: Can a versioned 0-10 rubric produce repeatable and explainable security assessments while reporting missing evidence separately?
- RQ4: When multiple credential technologies provide equivalent access to the same protected asset, how does the weakest accepted credential affect the overall access path?
- RQ5: Which technical and human-centered countermeasures address each observed weakness, and can a later assessment demonstrate measurable improvement?

## 3. Research Contributions

PASS-PAC contributes an integrated method rather than a new RF attack:

1. A local-first evidence pipeline from raw device output to normalized research records.
2. A cross-technology experiment protocol for LF and HF credentials.
3. An explainable 0-10 Access Path Security Score with evidence coverage and uncertainty.
4. Traceable findings that map observed evidence to countermeasures.
5. A basis for baseline-versus-remediation comparison.

Claims of uniqueness must be presented as feature and methodology comparisons against related tools and literature. They must not claim that no similar system exists without a systematic related-work search.

## 4. Methodological Basis

The assessment process follows the planning, execution, analysis, and mitigation principles in NIST SP 800-115, Technical Guide to Information Security Testing and Assessment. RFID-specific threats and controls are organized using NIST SP 800-98, Guidelines for Securing Radio Frequency Identification Systems.

Relevant foundations:

- NIST SP 800-115: https://doi.org/10.6028/NIST.SP.800-115
- NIST SP 800-98: https://doi.org/10.6028/NIST.SP.800-98
- NIST SP 800-116 Rev. 1: https://doi.org/10.6028/NIST.SP.800-116r1
- Nohl et al., Reverse-Engineering a Cryptographic RFID Tag: https://www.usenix.org/legacy/event/sec08/tech/full_papers/nohl/nohl_html/
- de Koning Gans et al., A Practical Attack on the MIFARE Classic: https://arxiv.org/abs/0803.2285

## 5. Study Scope And Ethics

- Test only team-owned credentials, laboratory media, or credentials explicitly listed in written authorization.
- Use an isolated test reader for reproduction and reader-acceptance experiments.
- Do not covertly scan employees, visitors, or production badges.
- Do not publish operational UIDs, keys, personal identifiers, or door mappings.
- Assign research aliases such as `CARD-HF-01` and keep any identity mapping outside exported research data.
- Record unsuccessful trials and incomplete evidence; do not retain only favorable results.
- Stop testing if it could affect production availability, credential state, or access-control records.

Human-subject measurements require explicit approval and informed participation. Without that approval, the human layer is limited to a literature-backed threat model and countermeasure analysis.

## 6. Data Sources

PASS-PAC keeps three data classes separate:

### 6.1 Reference Corpus

Imported Flipper files and local simulator records validate parsers, normalization, and risk rules. They are not counted as cards tested in the empirical study.

### 6.2 Live Observations

Read-only Proxmark3 outputs provide device-derived evidence. Repeated observations of one UID are observations, not additional unique cards.

### 6.3 Controlled Measurement Trials

The primary research dataset consists of repeated trials performed under the protocol below. Only this dataset supports empirical timing, distance, success-rate, and technology-comparison claims.

## 7. Experimental Design

### 7.1 Unit Of Analysis

The primary unit is one controlled presentation of one credential to the Proxmark3 antenna. A credential must have a stable research alias and a declared technology family.

### 7.2 Minimum Sample

- At least three credential families when available: one basic LF identifier, one legacy HF credential, and one modern authenticated HF credential.
- At least ten identification trials per credential.
- At least five attempts at every tested distance and orientation combination.
- Report the number of unique physical credentials separately from the number of trials.

### 7.3 Controlled Conditions

Record the following for every experiment batch:

- Proxmark3 model, client version, firmware version, and antenna-tuning output.
- Host operating system and PASS-PAC engine versions.
- Credential alias and technology family.
- Card-to-antenna orientation and which card face is presented.
- Distance in centimeters using a fixed ruler or jig.
- Nearby metal, other cards, and notable RF interference.
- Operator and timestamp.

Do not compare technologies measured with undocumented changes in antenna, firmware, orientation, or environment.

## 8. Trial Procedure

1. Verify authorization, equipment identity, firmware, and antenna status.
2. Remove unrelated cards and metal objects from the immediate test area.
3. Position the credential using the documented orientation and distance.
4. Start one bounded read-only identification operation.
5. Record command start, command completion, success, normalized identity, and raw evidence hash.
6. Record family-specific metadata obtained by the approved read-only recipe.
7. Mark parser output as correct, incorrect, or inconclusive against the known test-card label.
8. Return the device and card to the initial state before the next trial.
9. Repeat failures as new trials; never overwrite them.

Reliable identification distance is the greatest tested distance at which at least four of five trials both detect and correctly classify the expected credential under the same documented orientation. Partial protocol responses without matching identity evidence do not qualify. This is a property of the tested setup, not a universal range for the technology.

## 9. Variables

### Independent Variables

- Credential technology and card family.
- Distance in centimeters.
- Orientation and presented face.
- Reader/antenna configuration.
- Baseline or post-remediation condition.

### Dependent Variables

- Detection success.
- Correct family classification.
- Identification duration in milliseconds.
- Reliable read distance.
- Parsed metadata completeness.
- Observed authentication and secure-messaging indicators.
- Default/shared/diversified key evidence when explicitly authorized and verifiable.
- Controlled reproduction and isolated-reader acceptance outcomes when in scope.
- Access Path Security Score, score range, and evidence coverage.

### Controlled Variables

- Device, firmware, antenna, host, command profile, room, card orientation, and measurement procedure.

## 10. Data Processing

The processing pipeline is:

```text
raw device output
  -> immutable evidence hash
  -> parser validation
  -> normalized protocol and metadata fields
  -> duplicate observation handling
  -> scoring criteria
  -> aggregate statistics
  -> findings and countermeasures
  -> CSV/PDF research output
```

UIDs are normalized for matching but pseudonymized in publication. Invalid parser classifications must be corrected in the labeled validation corpus before they are included in research results.

## 11. Statistical Analysis

For every credential and technology group, report:

- Number of physical credentials and number of trials.
- Detection and correct-identification success rates as separate outcomes.
- Wilson 95% confidence intervals for every binomial rate.
- Median, minimum, maximum, and interquartile range for identification time.
- Reliable read distance under each tested orientation.
- Counts and proportions of observed findings.
- Security score, possible score range, and evidence coverage.

Use medians and interquartile ranges because timing samples may be skewed by device initialization and command timeouts. Do not describe a difference as statistically significant without an appropriate test and adequate sample size.

PASS-PAC uses the Wilson score interval instead of the normal approximation because controlled conditions may contain only five attempts and may produce rates near 0% or 100%. The interval is reported as an uncertainty range for the tested setup, not as evidence that the sampled card represents every deployment of its technology family.

Correct-identification timing excludes failed detections and responses classified as incorrect or inconclusive. A detected protocol response is therefore not automatically counted as a successful credential identification.

## 12. Security Scoring

The score is defined in `docs/security-score-v2.md`. The score uses five equal technical and deployment criteria, each rated from 0 to 2. Evidence quality, analyst review, and missing evidence do not directly add security points.

When criteria are unknown, PASS-PAC reports:

- a provisional score based on observed criteria;
- a minimum-to-maximum possible score range;
- evidence coverage; and
- an inconclusive policy result when coverage is below the selected policy threshold.

## 13. Mixed-Credential Environments

The weakest-path claim is conditional. If multiple credential classes provide equivalent access to the same asset, the asset-level credential score is the minimum score among those accepted paths:

```text
asset credential score = minimum(path score for each equivalent accepted credential)
```

Credentials with different privileges, doors, schedules, or additional factors must not be grouped as equivalent paths.

## 14. Countermeasure Evaluation

Every confirmed finding must map to:

- an immediate containment or configuration action;
- a medium-term engineering control;
- a long-term migration option;
- a validation procedure; and
- an owner and target date when used operationally.

Examples include eliminating default keys, implementing per-card diversification, rejecting UID-only authorization, enabling duplicate-identifier monitoring, improving revocation, migrating legacy credentials, and strengthening badge/tailgating awareness.

## 15. Validity Threats

### Internal Validity

- Antenna placement, card orientation, RF interference, device warm-up, and operator timing can affect measurements.
- Controls: fixed positioning, automated timestamps, repeated trials, and preserved failures.

### Construct Validity

- Card family does not prove reader or backend behavior.
- Controls: separate credential capability, observed transaction evidence, reader enforcement, and unknown fields.

### External Validity

- A small card sample cannot represent every deployment of a technology.
- Controls: restrict conclusions to the tested cards and configurations and compare cautiously with literature.

### Reliability

- Parser changes or scoring changes can alter results.
- Controls: version parsers, rules, policies, fixtures, firmware, and report manifests.

## 16. Reproducibility Checklist

- Authorization and scope recorded.
- Credential aliases and sample counts recorded.
- Device, client, firmware, and software versions recorded.
- Experimental environment and positioning documented.
- Raw outputs and hashes preserved.
- Failed and inconclusive trials retained.
- Parser validation tests passed.
- Score engine and policy versions included.
- Trial CSV contains all individual attempts.
- Analysis CSV contains condition-level rates, Wilson intervals, timing quartiles, and reliable-identification distances.
- PDF states limitations, statistical method, score coverage, and does not expose sensitive credential data.
