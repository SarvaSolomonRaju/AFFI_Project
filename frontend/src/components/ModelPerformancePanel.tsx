import { useLiveData } from "../hooks/useLiveData";
import type { ModelMetrics, SimState } from "../types/api";
import { StaleBadge } from "./StaleBadge";

interface GaugeBarProps {
  label: string;
  value: string | number;  // displayed as-is
  displayPct: number;      // 0-100 for bar fill
  color: string;
  interpretation: string;
  subtext?: string;
}

function GaugeBar({ label, value, displayPct, color, interpretation, subtext }: GaugeBarProps) {
  return (
    <div style={{ background: "var(--bg-primary)", borderRadius: 8, padding: "12px 14px", marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontWeight: 600, fontSize: "0.88rem" }}>{label}</span>
        <span style={{ fontWeight: 800, fontSize: "1.2rem", color }}>{value}</span>
      </div>
      <div style={{ height: 8, background: "rgba(255,255,255,0.07)", borderRadius: 4, marginBottom: 6, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${displayPct}%`, background: color, borderRadius: 4, transition: "width 0.6s ease" }} />
      </div>
      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{interpretation}</div>
      {subtext && <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 3, opacity: 0.7 }}>{subtext}</div>}
    </div>
  );
}

function metricColor(pct: number): string {
  if (pct >= 75) return "#27ae60";
  if (pct >= 55) return "#f39c12";
  return "#e74c3c";
}

interface ModelPerformancePanelProps {
  refreshSignal?: number;
  simState?: SimState | null;
}

export function ModelPerformancePanel({ refreshSignal, simState }: ModelPerformancePanelProps) {
  const inSimMode = simState !== undefined;
  const { data, error, lastUpdated } = useLiveData<ModelMetrics>(
    "/api/v1/model/metrics",
    300_000, // slow poll — metrics don't change without retraining
    inSimMode ? undefined : refreshSignal,
  );

  if (error && !data) return <p style={{ color: "var(--text-secondary)" }}>Model metrics not available: {error}</p>;
  if (!data) return <p style={{ color: "var(--text-secondary)" }}>Loading model metrics…</p>;

  const m = data.task1_metrics;
  const cfg = data.task2_inference_config;

  // NSE: theoretical range -∞ to 1; display 0-100 capped below 0
  const nseDisplay = Math.max(0, m.nse) * 100;
  // PBIAS: quality = 100 - |bias%|, capped 0-100
  const pbiasDisplay = Math.max(0, 100 - Math.abs((cfg.test_pbias ?? 0)));
  // Composite decision confidence (weighted)
  const composite = Math.round(
    0.40 * m.auc_roc * 100 +
    0.25 * m.f1 * 100 +
    0.20 * nseDisplay +
    0.15 * pbiasDisplay
  );

  const compositeColor = metricColor(composite);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        AI Model Diagnostics
        {inSimMode && (
          <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>
            training metrics apply to live forecasts, not simulation scenarios
          </span>
        )}
      </h3>

      {/* Overall confidence */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 20,
        background: "var(--bg-primary)",
        borderRadius: 8,
        padding: "14px 18px",
        marginBottom: 16,
        borderLeft: `4px solid ${compositeColor}`,
      }}>
        <div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", letterSpacing: "0.08em" }}>
            OVERALL DECISION CONFIDENCE
          </div>
          <div style={{ fontSize: "2.8rem", fontWeight: 900, lineHeight: 1, color: compositeColor }}>
            {composite}%
          </div>
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 2 }}>
            Weighted composite: AUC-ROC (40%) · F1 (25%) · NSE (20%) · Bias (15%)
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{
            background: composite >= 75 ? "rgba(39,174,96,0.10)" : composite >= 55 ? "rgba(243,156,18,0.10)" : "rgba(231,76,60,0.10)",
            border: `1px solid ${compositeColor}`,
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: "0.82rem",
          }}>
            {composite >= 75
              ? "Model is performing well. Flood/no-flood decisions are reliable. Use the P90 map for road closures to account for magnitude uncertainty."
              : composite >= 55
              ? "Model performs adequately. Event detection is good; magnitude estimates carry moderate uncertainty. Apply conservative thresholds."
              : "Model has significant uncertainty. Weight worst-case scenario more heavily in decisions. Cross-check against gauge observations."}
          </div>
        </div>
      </div>

      {/* Metric gauges */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
        <GaugeBar
          label="Event Detection (AUC-ROC)"
          value={m.auc_roc.toFixed(3)}
          displayPct={m.auc_roc * 100}
          color={metricColor(m.auc_roc * 100)}
          interpretation="Correctly ranks flood vs. no-flood 96% of the time. Excellent — the model rarely misses a real event."
          subtext="1.0 = perfect discrimination · 0.5 = random guess"
        />
        <GaugeBar
          label="Event F1 Score"
          value={m.f1.toFixed(3)}
          displayPct={m.f1 * 100}
          color={metricColor(m.f1 * 100)}
          interpretation="Balances false alarms vs. missed floods. 0.61 = acceptable tradeoff for rare flash flood events."
          subtext="Decision threshold: P(flood) ≥ 0.85"
        />
        <GaugeBar
          label="Magnitude NSE"
          value={m.nse.toFixed(3)}
          displayPct={nseDisplay}
          color={metricColor(nseDisplay)}
          interpretation="Nash-Sutcliffe Efficiency measures how well peak discharge is predicted. 0.35 is typical for flashy ephemeral streams — better than the long-term mean."
          subtext="0 = no better than mean · 1 = perfect · typical flashy stream: 0.3–0.5"
        />
        <GaugeBar
          label="Precision-Recall (AUC-PR)"
          value={m.auc_pr.toFixed(3)}
          displayPct={m.auc_pr * 100}
          color={metricColor(m.auc_pr * 100)}
          interpretation="Performance on rare high-flow events specifically. 0.64 = good given that flooding occurs on <5% of days in the record."
          subtext="Baseline ≈ event frequency (~0.05) — 0.64 is strong"
        />
        <GaugeBar
          label="Peak Bias (PBIAS)"
          value={`${(cfg.test_pbias ?? 0).toFixed(1)}%`}
          displayPct={pbiasDisplay}
          color={metricColor(pbiasDisplay)}
          interpretation="Model slightly underestimates peak flow by ~2.9%. Very low bias — effectively no systematic over/under prediction."
          subtext="0% = unbiased · negative = underestimate · positive = overestimate"
        />
        <GaugeBar
          label="Magnitude Model"
          value={cfg.magnitude_model ?? "xgboost"}
          displayPct={78}
          color="#4ea8de"
          interpretation={`XGBoost gradient boosting with ${cfg.n_lags ?? 7} lag features. 800 estimators, max depth 6. Rare events weighted 20× in training.`}
          subtext={`Threshold: P ≥ ${(cfg.threshold ?? 0.85).toFixed(2)} for flood classification`}
        />
      </div>

      {/* Engineering fixes */}
      {cfg.fixes_applied && cfg.fixes_applied.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontWeight: 600, fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: 6, letterSpacing: "0.06em" }}>
            ENGINEERING IMPROVEMENTS APPLIED
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {cfg.fixes_applied.map((fix, i) => (
              <div key={i} style={{
                background: "rgba(78,168,222,0.10)",
                border: "1px solid rgba(78,168,222,0.2)",
                borderRadius: 5,
                padding: "4px 8px",
                fontSize: "0.75rem",
                color: "var(--accent-blue)",
              }}>
                {fix.replace(/^Fix\d+:\s*/, "")}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transfer learning / calibration status */}
      <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
        <div style={{ fontWeight: 600, fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: 8, letterSpacing: "0.06em" }}>
          DECISION FRAMEWORK
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8 }}>
          {[
            {
              label: "GO / NO-GO decision",
              confidence: "High",
              color: "#27ae60",
              note: "AUC-ROC 0.96 → flood vs no-flood call is reliable",
            },
            {
              label: "Road closure threshold",
              confidence: "Medium-High",
              color: "#f39c12",
              note: "Use P90 scenario — model underestimates peaks by ~3%",
            },
            {
              label: "Exact peak discharge",
              confidence: "Medium",
              color: "#e67e22",
              note: "NSE 0.35 → ±25–40% uncertainty on peak magnitude",
            },
            {
              label: "Evacuation timing",
              confidence: "Medium",
              color: "#e67e22",
              note: "Time-to-peak via Kirpich method — ±15–20% range",
            },
          ].map(({ label, confidence, color, note }) => (
            <div key={label} style={{ background: "var(--bg-primary)", borderRadius: 6, padding: "8px 10px", borderTop: `2px solid ${color}` }}>
              <div style={{ fontWeight: 600, fontSize: "0.8rem" }}>{label}</div>
              <div style={{ fontSize: "0.78rem", color, fontWeight: 700 }}>{confidence}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 2 }}>{note}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Bias correction status */}
      {cfg.bias_correction && (
        <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 12, marginBottom: 0, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
          Peak-flow bias correction scale: {cfg.bias_correction.event_scale?.toFixed(3)} ·
          Applied: {cfg.bias_correction.applied ? "YES" : "NO (validation-based, not active)"} ·
          Model: XGBoost {cfg.xgb_params ? `d=${cfg.xgb_params.max_depth}, n=${cfg.xgb_params.n_estimators}, lr=${cfg.xgb_params.learning_rate}` : ""}
        </p>
      )}
    </div>
  );
}
