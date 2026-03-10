-- ============================================================
-- ksqlDB Streaming Aggregations — Supply Chain AI OS
-- Feature 3: Real-time delay rate aggregations per supplier
-- ============================================================
-- These persistent queries run continuously on the Kafka topic
-- and materialise 5-minute tumbling window stats.
-- ============================================================

-- Step 1: Create a stream over the raw Kafka topic
CREATE STREAM IF NOT EXISTS supply_chain_events (
    event_type  VARCHAR,
    order_id    VARCHAR,
    supplier_id VARCHAR,
    product     VARCHAR,
    region      VARCHAR,
    quantity    INT,
    unit_price  DOUBLE,
    order_value DOUBLE,
    delay_days  INT,
    status      VARCHAR,
    inventory_level DOUBLE
) WITH (
    KAFKA_TOPIC = 'supply-chain-events',
    VALUE_FORMAT = 'JSON',
    TIMESTAMP_FORMAT = 'yyyy-MM-dd''T''HH:mm:ss.SSSSSSZ'
);

-- Step 2: Filter ORDER events only
CREATE STREAM IF NOT EXISTS order_events AS
    SELECT *
    FROM supply_chain_events
    WHERE event_type = 'ORDER'
EMIT CHANGES;

-- Step 3: Materialise a table: 5-minute rolling delay rate per supplier
-- delay_count = orders where delay_days > 0
-- total_count = all orders in the window
-- delay_rate  = delay_count / total_count
CREATE TABLE IF NOT EXISTS supplier_delay_rate_5m AS
    SELECT
        supplier_id,
        COUNT(*) AS total_orders,
        SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) AS delayed_orders,
        CAST(SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) AS delay_rate,
        AVG(delay_days) AS avg_delay_days,
        AVG(inventory_level) AS avg_inventory_level,
        WINDOWSTART AS window_start,
        WINDOWEND AS window_end
    FROM order_events
    WINDOW TUMBLING (SIZE 5 MINUTES, RETENTION 24 HOURS)
    GROUP BY supplier_id
EMIT CHANGES;

-- Step 4: Region-level demand aggregation (5-minute tumbling)
CREATE TABLE IF NOT EXISTS region_demand_5m AS
    SELECT
        region,
        COUNT(*) AS order_count,
        SUM(order_value) AS total_order_value,
        AVG(order_value) AS avg_order_value,
        SUM(quantity) AS total_quantity,
        WINDOWSTART AS window_start,
        WINDOWEND AS window_end
    FROM order_events
    WINDOW TUMBLING (SIZE 5 MINUTES, RETENTION 24 HOURS)
    GROUP BY region
EMIT CHANGES;

-- Step 5: High-delay alert stream (delay_days >= 7 → critical)
CREATE STREAM IF NOT EXISTS critical_delay_alerts AS
    SELECT
        order_id,
        supplier_id,
        region,
        delay_days,
        status,
        inventory_level,
        ROWTIME AS event_time
    FROM order_events
    WHERE delay_days >= 7
EMIT CHANGES;

-- Step 6: DEMAND_SPIKE stream
CREATE STREAM IF NOT EXISTS demand_spike_events (
    event_type              VARCHAR,
    product                 VARCHAR,
    region                  VARCHAR,
    forecast_delta_pct      DOUBLE,
    current_inventory_days  DOUBLE
) WITH (
    KAFKA_TOPIC = 'supply-chain-events',
    VALUE_FORMAT = 'JSON'
);

CREATE STREAM IF NOT EXISTS demand_spikes_filtered AS
    SELECT *
    FROM demand_spike_events
    WHERE event_type = 'DEMAND_SPIKE'
      AND forecast_delta_pct >= 20.0
EMIT CHANGES;
