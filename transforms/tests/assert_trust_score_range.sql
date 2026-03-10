-- Test: trust_score must be between 0 and 1
SELECT
    supplier_id,
    trust_score
FROM {{ ref('dim_suppliers') }}
WHERE trust_score < 0 OR trust_score > 1
