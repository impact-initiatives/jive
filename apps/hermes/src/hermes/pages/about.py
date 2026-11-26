import streamlit as st

st.title("Hermes and Argus")
st.markdown("""
Hermes is a frontend for the Argus validation framework. It allows users to easily run programme
and dataset specific checks on an ad-hoc basis prior to or part of submitting a dataset for any 
formal review process.

## What is Argus
Argus is designed to allow for the review and validation of different excel based datasets. 
This is performed through the construction of a dataset schema and specifying a list of validation 
rules that are required to be run against the data.

It provides a standardised and rapid data validation pipeline. 
Datasets are automatically assessed against strict organisational Minimum Standards (schemas) 
when they are uploaded, delivering immediate feedback to the user without any 
manual intervention.

###  How Argus Knows What to Check: Schema & Validation Rules

These are the two building blocks that define what ARGUS checks and how it checks 

#### The Dataset Schema - The blueprint

The schema is a formal description of what a valid dataset should look like. 
It answers the question: **what am I expecting to find?**

It defines:

- Which **sheets** must be present, which are optional, and which should exist 
but don't need to be analysed
- Which **columns** are required in each sheet
- Accepted **alternative names** for sheets and columns 
(to handle naming variations across countries or teams)
- Whether a column should contain **unique values**
- Special values used by certain checks — for example, 
which values in the consent column count as "consent given"



#### Validation Rules — the checks

Each validation rule is an independent check that answers a specific question about the data. 
For example:

- Are all required sheets present?
- Do all records in clean data have a matching entry in raw data?
- Are all cleaning log changes reflected in clean data?
- Does the data contain possible personal information (PII)?

Rules are **modular** — each one does exactly one thing, and a dataset can use any 
combination of them.

### How they work together

The schema is the **shared reference** that most rules rely on. A rule asks the schema: 
*where should I look, and what should I find there?* Then it checks the actual data 
against that expectation.

This separation is intentional. It means:

- Adding a new dataset only requires writing a new schema — the existing rules can be reused as-is
- Adding a new check only requires writing one new rule — it can immediately be applied to any 
dataset type
- Rules and schemas can evolve independently

### Argus is Open Source

Every aspect of Argus is open source and available on GitHub. See the 
[Argus code here](https://github.com/impact-initiatives/jive/tree/hermes/common/argus). 

Details on the currently supported schemas is 
[available here](https://github.com/impact-initiatives/jive/tree/hermes/common/argus_schemas).

Details on the currently supported validation rules is 
[available here](https://github.com/impact-initiatives/jive/tree/hermes/common/argus/src/docs/validators).


""")
