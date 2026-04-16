import SparkBar from "../ui/SparkBar";

function getHeartRateState(value) {
  if (value >= 110) {
    return { label: "High", dot: "dot-crit", tag: "tag-crit", color: "var(--red)" };
  }
  if (value >= 95) {
    return { label: "Elevated", dot: "dot-warn", tag: "tag-warn", color: "var(--amber)" };
  }
  return { label: "Normal", dot: "dot-ok", tag: "tag-ok", color: "var(--green)" };
}

function getSpo2State(value) {
  if (value <= 92) {
    return { label: "Low", dot: "dot-crit", tag: "tag-crit", color: "var(--red)" };
  }
  if (value <= 95) {
    return { label: "Watch", dot: "dot-warn", tag: "tag-warn", color: "var(--amber)" };
  }
  return { label: "Normal", dot: "dot-ok", tag: "tag-ok", color: "var(--green)" };
}

function getBloodPressureState(bp) {
  const [systolicText = "0", diastolicText = "0"] = (bp || "").split("/");
  const systolic = Number(systolicText);
  const diastolic = Number(diastolicText);

  if (systolic <= 95 || diastolic <= 60) {
    return { label: "Low", dot: "dot-crit", tag: "tag-crit" };
  }
  if (systolic >= 140 || diastolic >= 90) {
    return { label: "High", dot: "dot-warn", tag: "tag-warn" };
  }
  return { label: "Stable", dot: "dot-ok", tag: "tag-ok" };
}

function getTemperatureState(value) {
  if (value >= 38) {
    return { label: "Elevated", dot: "dot-warn", tag: "tag-warn" };
  }
  return { label: "Normal", dot: "dot-ok", tag: "tag-ok" };
}

export default function DashboardVitalsPanel({ vitals, vitalsMode, setVitalsMode }) {
  const heartRateState = getHeartRateState(vitals.hr);
  const spo2State = getSpo2State(vitals.spo2);
  const bloodPressureState = getBloodPressureState(vitals.bp);
  const temperatureState = getTemperatureState(vitals.temp);

  return (
    <div className="vitals-panel">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div className="card-title" style={{ marginBottom: 0 }}>LIVE VITALS - SENSOR CONTEXT</div>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            ["normal", "Normal vitals"],
            ["abnormal", "Abnormal vitals"],
          ].map(([mode, label]) => (
            <button
              key={mode}
              className={`btn btn-sm ${vitalsMode === mode ? "btn-green" : "btn-ghost"}`}
              onClick={() => setVitalsMode(mode)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ fontSize: 12, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: 16 }}>
        This toggle changes the exact vitals payload sent to the communication and reasoning agents, so the dashboard can test both stable and escalated contexts.
      </div>

      <div className="vitals-grid">
        <div className="vital-item">
          <span className="vital-label">Heart Rate</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.hr}</span>
            <span className="vital-unit">bpm</span>
          </div>
          <SparkBar data={vitals.hrHistory} color={heartRateState.color} />
          <div>
            <span className={`vital-status-dot ${heartRateState.dot}`} />
            <span className={`vital-tag ${heartRateState.tag}`}>{heartRateState.label}</span>
          </div>
        </div>

        <div className="vital-item">
          <span className="vital-label">SpO2</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.spo2}</span>
            <span className="vital-unit">%</span>
          </div>
          <SparkBar data={vitals.spo2History} color={spo2State.color} />
          <div>
            <span className={`vital-status-dot ${spo2State.dot}`} />
            <span className={`vital-tag ${spo2State.tag}`}>{spo2State.label}</span>
          </div>
        </div>

        <div className="vital-item">
          <span className="vital-label">Blood Pressure</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val" style={{ fontSize: 20 }}>{vitals.bp}</span>
            <span className="vital-unit">mmHg</span>
          </div>
          <div style={{ height: 28 }} />
          <div>
            <span className={`vital-status-dot ${bloodPressureState.dot}`} />
            <span className={`vital-tag ${bloodPressureState.tag}`}>{bloodPressureState.label}</span>
          </div>
        </div>

        <div className="vital-item">
          <span className="vital-label">Temperature</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.temp}</span>
            <span className="vital-unit">C</span>
          </div>
          <div style={{ height: 28 }} />
          <div>
            <span className={`vital-status-dot ${temperatureState.dot}`} />
            <span className={`vital-tag ${temperatureState.tag}`}>{temperatureState.label}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
