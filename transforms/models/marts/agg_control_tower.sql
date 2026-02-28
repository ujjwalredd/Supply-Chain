{{
  config(
    materialized='table',
    schema='marts'
  )
}}

with shipments as (
    select * from {{ ref('fct_shipments') }}
),

suppliers as (
    select * from {{ ref('dim_suppliers') }}
),

kpis as (
    select
        count(*) as total_shipments,
        sum(order_value) as pipeline_value,
        sum(case when calculated_delay_days <= 0 then 1 else 0 end) as on_time_count,
        sum(case when calculated_delay_days > 0 then 1 else 0 end) as delayed_count,
        sum(case when calculated_delay_days > 7 then 1 else 0 end) as critical_delays,
        round(100.0 * sum(case when calculated_delay_days <= 0 then 1 else 0 end) / nullif(count(*), 0), 2) as on_time_pct
    from shipments
)

select
    total_shipments,
    pipeline_value,
    on_time_count,
    delayed_count,
    critical_delays,
    on_time_pct,
    current_timestamp as refreshed_at
from kpis
