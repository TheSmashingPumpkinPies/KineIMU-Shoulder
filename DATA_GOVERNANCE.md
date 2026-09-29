# Data Governance and Human-Data Rules

## Default

The public repository must contain only:

- synthetic data;
- non-identifying sample data;
- explicitly approved de-identified research data.

## Video

Human video is potentially identifiable.

Do not commit identifiable video to the public Git repository.

Keep:

- raw video
- derived annotations
- public sample data

as separate data classes.

## IDs

Use pseudonymous IDs such as:

``` text
sub-001
session-001
device-001
```

Do not encode names, student numbers, emails, phone numbers, or other direct identifiers.

## Self-testing

Self-testing is useful for engineering validation but does not automatically establish population-level validity.

Label self-data clearly.

## Other Participants

Before collecting data from other people for research/publication:

- check institutional ethics/IRB requirements;
- obtain appropriate consent;
- define storage/access;
- define whether video can be retained/shared;
- define withdrawal/deletion procedure if applicable.

## Clinical Claims

This project is not a medical device.

Do not output:

- diagnosis
- treatment recommendation
- injury prediction
- clinical risk score

without a separate validated and appropriately governed research program.
