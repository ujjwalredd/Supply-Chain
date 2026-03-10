-- Test: delay_days should never be negative
SELECT
    order_id,
    delay_days
FROM {{ ref('fct_shipments') }}
WHERE delay_days < 0
