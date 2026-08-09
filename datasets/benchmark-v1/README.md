# KYC Synthetic Golden Benchmark v1

This versioned benchmark contains only synthetic entities and customers. Names, identifiers, programs, and countries
used by the sanctions fixture are invented for testing and do not assert that any real person or organization is
sanctioned, high risk, or otherwise adverse.

## Scope

- 40 sanctions-screening labels: 24 positives and 16 negatives.
- Positive segments cover exact Latin names, aliases, reordered individual names, and Chinese aliases.
- Negative segments include easy controls and deliberately difficult shared-token names.
- 10 policy-bound risk-category labels.
- 16 entity-resolution records: six duplicate pairs and four unique controls.

## Label policy

- A screening positive means the customer should trigger an analyst alert for the specified synthetic entity.
- A screening negative means the customer should not trigger any analyst alert at the evaluated threshold.
- Risk labels are bound to risk policy `2026.08-demo.1`; policy changes require a new benchmark version or relabeling.
- Duplicate labels describe customer clusters. Evaluation expands clusters into all expected positive pairs and treats
  all cross-cluster pairs in the labeled subset as negative pairs.

## Limitations

This is an engineering regression benchmark, not evidence of production sanctions-screening effectiveness. It is
small, synthetic, and intentionally transparent. A regulated deployment still needs legally authorized data,
independent labeling, representative languages and entity types, threshold approval, and ongoing false-negative
analysis.
