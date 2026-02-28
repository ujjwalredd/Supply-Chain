{{
  config(
    materialized='view',
    schema='staging'
  )
}}

with source as (
    select * from {{ source('raw', 'orders') }}
),

cleaned as (
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
        coalesce(delay_days, 0) as delay_days,
        status,
        inventory_level,
        created_at
    from source
    where order_id is not null
      and order_id != ''
      and status in ('PENDING', 'IN_TRANSIT', 'DELIVERED', 'DELAYED', 'CANCELLED')
)

select * from cleaned
