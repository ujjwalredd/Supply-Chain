{{
  config(
    materialized='table',
    schema='marts'
  )
}}

with suppliers as (
    select * from {{ ref('stg_suppliers') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

agg as (
    select
        s.supplier_id,
        s.name,
        s.region,
        s.trust_score,
        s.total_orders,
        s.delayed_orders,
        s.avg_delay_days,
        count(o.order_id) as order_count,
        sum(case when o.delay_days > 0 then 1 else 0 end) as delayed_count
    from suppliers s
    left join orders o on o.supplier_id = s.supplier_id
    group by 1, 2, 3, 4, 5, 6, 7
)

select
    supplier_id,
    name,
    region,
    trust_score,
    total_orders,
    delayed_orders,
    avg_delay_days,
    order_count,
    delayed_count,
    case
        when order_count > 0 then round(100.0 * delayed_count / order_count, 2)
        else 0
    end as delay_rate_pct
from agg
