import { motion } from 'framer-motion';
import { Database, Activity, Cpu, LineChart, History, Network } from 'lucide-react';

export function Capabilities() {
  const capabilities = [
    {
      title: 'Medallion Data Lakehouse',
      desc: 'Dagster orchestrated bronze-to-gold pipeline using Delta Lake and partitioned Parquet on MinIO object storage with freshness policies.',
      icon: Database,
    },
    {
      title: 'ksqlDB Real-Time Streaming',
      desc: 'Persistent 5-minute tumbling windows computing live supplier delay rates and regional demand directly from Kafka event streams.',
      icon: Activity,
    },
    {
      title: 'XGBoost & MLflow Registry',
      desc: 'Automated delay classification training pipeline. MLflow tracks metrics, artifacts, and manages model promotion to production.',
      icon: Cpu,
    },
    {
      title: 'Prophet Demand Forecasting',
      desc: 'A 30-day forward-looking time series forecast powered by Facebook Prophet, materialized as a gold asset for immediate API serving.',
      icon: LineChart,
    },
    {
      title: 'Event Sourcing Audit Trail',
      desc: 'Append-only event architecture in PostgreSQL allowing for full historical playback and point-in-time state recovery of any order.',
      icon: History,
    },
    {
      title: 'OpenTelemetry + Jaeger',
      desc: 'Auto-instrumented FastAPI and SQLAlchemy passing OTLP gRPC traces to Jaeger, providing deep observability into database queries and AI latency.',
      icon: Network,
    }
  ];

  return (
    <section className="py-24 bg-paper relative z-10 border-b border-black/5">
      <div className="max-w-7xl mx-auto px-6">

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="mb-16 max-w-3xl"
        >
          <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-4 font-semibold">Technical Capabilities</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-6">
            A 17-service production-grade data ecosystem.
          </h3>
          <p className="text-steel text-lg font-light leading-relaxed mb-8">
            The platform replicates the end-to-end architecture of a $100M+ enterprise operations tower.
            By connecting raw data pipelines directly to deterministic AI agents, we execute decisions the moment a signal drops.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-12">
          {capabilities.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: i * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col group"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-subtle border border-black/5 group-hover:bg-white group-hover:shadow-sm group-hover:border-black/10 transition-all">
                    <Icon size={18} className="text-ink" />
                  </div>
                  <h4 className="text-ink font-semibold">{cap.title}</h4>
                </div>
                <p className="text-steel text-sm leading-relaxed">{cap.desc}</p>
              </motion.div>
            );
          })}
        </div>

      </div>
    </section>
  );
}
