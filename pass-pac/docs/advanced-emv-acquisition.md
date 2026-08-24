# Advanced EMV Acquisition

## Objective

The Advanced EMV profile collects deeper ISO 14443-A and ISO 7816 evidence than a general `hf search`. It is intended for owned or explicitly authorized contactless payment test cards in a controlled laboratory.

## Command Sequence

| Stage | Command | Evidence |
|---|---|---|
| Transport discovery | `hf search` | Credential family and UID |
| ISO 14443-A metadata | `hf 14a info` | ATQA, SAK, ATS, timing capabilities, UID classification |
| Directory discovery | `emv pse -s2` | PPSE availability, AIDs, priorities |
| Application enumeration | `emv search -s` | Installed known EMV applications and payment-system mapping |
| Application read | `emv reader` | Application labels, language/currency metadata, effective/expiration dates, masked PAN, PAN sequence, GPO and record-read evidence |
| Protocol history | `emv list` | Redacted ISO 7816 command sequence and status words |

The workflow does not call `genac`, `challenge`, `intauth`, `exec`, `scan`, or any simulation/write command.

## Data Processing

1. The Proxmark client runs with `--incognito`, disabling its history, preferences, and session-log files.
2. The Windows bridge captures output in a temporary file.
3. Full PAN, cardholder name, track data, and verification values are replaced with explicit redaction markers. Only the PAN's last four digits are retained; PAN sequence is retained as non-secret application metadata.
4. EMV command-history payloads are reduced to reader APDU headers and card status words.
5. The backend applies the same redaction again before parsing or persistence.
6. Structured metadata is stored with the card observation and assessment timeline.

## Retained Research Fields

- AID list and application count
- inferred payment systems from registered AID prefixes
- application labels
- language and currency metadata
- effective and expiration dates
- masked PAN (last four digits only) and PAN sequence
- Track 2 presence indicator (content redacted)
- PPSE and AID-search results
- application-reader and record-read evidence flags
- APDU frame count and status words
- list of sensitive field categories that were redacted

## Interpretation Limits

- Finding an AID proves application availability, not transaction approval.
- GPO and record-read success do not demonstrate issuer authentication or authorization.
- The profile does not create an application cryptogram or perform a payment transaction.
- Redaction deliberately prevents PASS-PAC from being used as a payment-credential collection system.
- EMV evidence should not be used to score a physical-access deployment unless that deployment actually uses the observed application.
