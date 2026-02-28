{{
  config(
    materialized='table',
    schema='marts'
  )
}}

with orders as (
    select * from {{ ref('stg_orders') }}
),

shipments as (
    select
        order_id,
        supplier_id,
        product,
        region,
        quantity,
        unit_price,
        order_value,
        expected_delivery,
        actual_delivery,
        delay_days,
        status,
        inventory_level,
        created_at,
        case
            when actual_delivery is not null and expected_delivery is not null
            then extract(day from (actual_delivery - expected_delivery))
            else delay_days
        end as calculated_delay_days
    from orders
    where status in ('DELIVERED', 'DELAYED', 'IN_TRANSIT')
)

select * from shipments
