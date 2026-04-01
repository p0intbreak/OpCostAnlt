# Classification Methodology

## Scope

This repository uses a configurable three-level taxonomy for IT department spend classification:

- `category_l1`: executive-level spend family
- `category_l2`: operational sub-domain
- `category_l3`: concrete analytical bucket

The classifier is designed to be extended through YAML configuration, not through code changes.

## Feature Sources

Classification rules may draw evidence from the following normalized fields:

- `bit_stati_oborotov_naimenovanie`: primary accounting article and usually the strongest structured signal
- `naznachenie_platezha`: free-text payment purpose or description
- `kontragenti_naimenovanie`: supplier or counterparty
- `dogovori_kontragentov_naimenovanie`: contract name or agreement context
- `proekti_naimenovanie`: linked project, implementation stream, or product initiative
- `podrazdeleniya_naimenovanie`: consuming department or owning team

These inputs represent a mix of structured accounting fields and semi-structured business context. The methodology assumes accounting article and vendor are usually the most stable features, while description and project provide disambiguation when article names are broad.

## Priority Rules

Rules are evaluated in ascending `priority` order:

1. More specific rules should have lower numeric priority.
2. Broader fallback rules should have higher numeric priority.
3. When multiple signals are available, rules that combine article plus vendor or article plus project should be preferred over single-field heuristics.
4. `other_it / unclassified / review_required` must remain the terminal fallback and should never outrank targeted rules.

Practical precedence guideline:

- First: article + vendor + contract combinations
- Second: article + project or article + department combinations
- Third: vendor-only or description-only heuristics
- Last: fallback review bucket

## Confidence Score

Each YAML rule carries a `confidence` value in the range `[0.0, 1.0]`.

Suggested interpretation:

- `0.90-1.00`: highly reliable pattern with strong vendor or article specificity
- `0.75-0.89`: acceptable auto-classification, but still worth periodic sampling
- `0.50-0.74`: weak or broad heuristic; should usually enter manual review
- `<0.50`: fallback, unresolved, or low-quality match

Confidence is rule-level, not model-derived. It reflects how trustworthy the rule is expected to be based on the underlying evidence pattern.

## Review Queue

A transaction should be routed to the review queue when any of the following is true:

- the matched rule confidence is below `review_required_below`
- only weak text evidence is available
- the record matches only the fallback rule
- multiple candidate rules have comparable specificity
- the source values are sparse, empty, or inconsistent

Recommended review queue fields:

- original article name
- normalized vendor
- contract name
- project name
- department name
- assigned `category_l1`, `category_l2`, `category_l3`
- `classification_rule_id`
- `classification_confidence`
- reviewer comment and final override

## Config-Driven Extension

To extend classification coverage:

1. Add or refine L2/L3 nodes in `config/category_taxonomy.yaml`.
2. Add new YAML rules in `config/classification_rules.yaml`.
3. Keep priorities unique and ordered by specificity.
4. Validate that each rule target points to an existing taxonomy branch.
5. Route low-confidence rules to the review queue instead of forcing precise labels.

This approach keeps business logic transparent, reviewable, and editable by analysts without requiring Python code changes.
