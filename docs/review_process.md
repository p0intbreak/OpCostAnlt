# Review Process

## Purpose

Semi-automatic review queue is used for low-confidence and unclassified payment records.
Its goal is to let an analyst review suggested categories and progressively expand
`config/classification_rules.yaml` without editing Python code.

## Output Artifact

After classification the pipeline saves:

- `data/interim/classifier_training_sample.csv`

The file contains:

- `raw_article`
- `raw_description`
- `raw_vendor`
- `suggested_l1`
- `suggested_l2`
- `suggested_l3`
- `confidence`
- `reason`

## Analyst Workflow

1. Open `data/interim/classifier_training_sample.csv`.
2. Review rows with `confidence=low` or `confidence=unclassified`.
3. Adjust `suggested_l1`, `suggested_l2`, `suggested_l3` to the correct taxonomy labels.
4. Save the updated CSV.
5. Apply the reviewed labels back into the ruleset with the utility function:

```python
from pathlib import Path
from it_spend_dashboard.classification.manual_labeling import apply_manual_labels_to_rules

apply_manual_labels_to_rules(
    review_csv_path=Path("data/interim/classifier_training_sample.csv"),
    rules_yaml_path=Path("config/classification_rules.yaml"),
)
```

## Rule Generation Logic

The utility generates a new YAML rule from reviewed rows using available evidence:

- `raw_article` -> `bit_stati_oborotov_naimenovanie`
- `raw_description` -> `naznachenie_platezha`
- `raw_vendor` -> `kontragenti_naimenovanie`

It appends rules with increasing priority values and preserves the existing ruleset.

## Review Guidance

- Prefer consistent taxonomy labels already present in `config/category_taxonomy.yaml`.
- Do not invent new L1/L2/L3 values without first updating the taxonomy.
- Keep article or vendor text short and representative.
- Avoid turning one-off noisy descriptions into overly specific rules.
- Re-run QA and inspect classification coverage after applying new labels.

## Known Limitations

- The utility appends simple `contains_any` rules and does not yet deduplicate semantically similar patterns.
- Manual labels are not versioned independently from the YAML file.
- Review queue currently focuses on low-confidence and unclassified rows only.
