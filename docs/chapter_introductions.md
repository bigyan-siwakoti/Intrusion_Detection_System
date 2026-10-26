# Chapter introductions (supervisor feedback, 12 Oct 2026)

One short opening paragraph per chapter, inserted directly under the chapter heading, highlighted yellow in the
SharePoint document so the team can track additions. Adjust the section names to match the team's edited version.

## I. Introduction
This chapter sets out why the project was undertaken and what it set out to do. It explains the problem with
rule-based intrusion detection that motivated the work, defines the scope and constraints, states the research
question and four objectives, and outlines how the rest of the report is organised.

## II. Literature Review
This chapter reviews the work this project builds on. It begins with the foundations of intrusion detection and
the cost of writing detection rules, then examines recent systems that use large language models to generate
rules, the datasets used to evaluate them, and the practices real detection engineers follow, before identifying
the gap this project addresses.

## III. Approach
This chapter describes how the system was designed and why. It presents the overall architecture, the agentic loop
that lets a language model act through tools, the tools themselves and the technology stack, the safety and
evaluation-integrity measures, the hunt condition that replicates detection-engineering practice, and the three
experiments used to answer the research question.

## IV. Execution
This chapter reports how the system was run. It introduces the two datasets, describes the triage runs on
CIC-IDS2017 and UNSW-NB15, explains how the human-written baseline was strengthened, and summarises the AI
rule-writing rounds carried out against that baseline.

## V. Analysis and Discussion of Results
This chapter analyses the results against the research objectives. It evaluates the quality of the AI-authored
rules, the effect of context on triage, the gain over a strong human baseline once topology rules are excluded,
and the results on held-out traffic, before discussing what the findings mean and the threats to their validity.

## VI. Conclusions
This chapter draws the findings together. It answers the research question objective by objective and considers
what the results mean for the use of language models in security operations.

## VII. Lessons Learned
This chapter reflects on what the team learned while carrying out the project, both technically and in how the
work was managed.

## VIII. Future Work
This chapter outlines the work that would extend or strengthen the findings of this project.

---
Added length: about 290 words, bringing the body to roughly 4,500 words of prose (still inside 4,000–5,000
excluding captions, tables, references and appendices).
