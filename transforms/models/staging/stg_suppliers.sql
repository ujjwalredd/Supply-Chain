{{
  config(
    materialized='view',
    schema='staging'
  )
}}

with source as (
    select * from {{ source('raw', 'suppliers') }}
),

cleaned as (
    select
        supplier_id,
        name,
        region,
        coalesce(trust_score, 1.0) as trust_score,
        coalesce(total_orders, 0) as total_orders,
        coalesce(delayed_orders, 0) as delayed_orders,
        coalesce(avg_delay_days, 0) as avg_delay_days,
        contract_terms,
        capacity_limits
    from source
    where supplier_id is not null
)

select * from cleaned
