-- Test: no order should have a negative value
-- This test fails if any row is returned
SELECT
    order_id,
    order_value
FROM {{ ref('fct_shipments') }}
WHERE order_value < 0
