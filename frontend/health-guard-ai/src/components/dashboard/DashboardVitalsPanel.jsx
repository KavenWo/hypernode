import HealthGauge from "../ui/HealthGauge";

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
    return { label: "Low", dot: "dot-crit", tag: "tag-crit", color: "var(--red)" };
  }
  if (systolic >= 140 || diastolic >= 90) {
    return { label: "High", dot: "dot-warn", tag: "tag-warn", color: "var(--amber)" };
  }
  return { label: "Stable", dot: "dot-ok", tag: "tag-ok", color: "var(--green)" };
}

function getTemperatureState(value) {
  if (value >= 38) {
    return { label: "High", dot: "dot-warn", tag: "tag-warn", color: "var(--amber)" };
  }
  return { label: "Normal", dot: "dot-ok", tag: "tag-ok", color: "var(--green)" };
}

export default function DashboardVitalsPanel({ vitals }) {
  const heartRateState = getHeartRateState(vitals.hr);
  const spo2State = getSpo2State(vitals.spo2);
  const bloodPressureState = getBloodPressureState(vitals.bp);
  const temperatureState = getTemperatureState(vitals.temp);

  const [systolic = 0, diastolic = 0] = (vitals.bp || "").split("/").map(Number);

  return (
    <div className="vitals-panel">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div className="card-title" style={{ marginBottom: 0 }}>LIVE VITALS - SENSOR CONTEXT</div>
      </div>

      <div style={{ fontSize: 10, color: "var(--text-sub)", lineHeight: 1.6, marginBottom: 16 }}>
        Monitor patient physiological stability. The marker indicates the current reading within established safety ranges.
      </div>

      <div className="vitals-grid">
        {/* HEART RATE */}
        <div className="vital-item">
          <span className="vital-label">Heart Rate</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.hr}</span>
            <span className="vital-unit">bpm</span>
          </div>
          <HealthGauge value={vitals.hr} min={40} max={160} low={60} high={100} color={heartRateState.color} />
          <div style={{ marginTop: "auto", paddingTop: 8 }}>
            <span className={`vital-status-dot ${heartRateState.dot}`} />
            <span className={`vital-tag ${heartRateState.tag}`}>{heartRateState.label}</span>
          </div>
        </div>

        {/* SPO2 */}
        <div className="vital-item">
          <span className="vital-label">SpO2</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.spo2}</span>
            <span className="vital-unit">%</span>
          </div>
          <HealthGauge value={vitals.spo2} min={80} max={100} low={92} high={100} color={spo2State.color} />
          <div style={{ marginTop: "auto", paddingTop: 8 }}>
            <span className={`vital-status-dot ${spo2State.dot}`} />
            <span className={`vital-tag ${spo2State.tag}`}>{spo2State.label}</span>
          </div>
        </div>

        {/* BLOOD PRESSURE */}
        <div className="vital-item">
          <span className="vital-label">Blood Pressure</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <div className="vital-val">{vitals.bp}</div>
            <span className="vital-unit">mmHg</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <HealthGauge value={systolic} min={80} max={200} low={95} high={140} color={bloodPressureState.color} />
            <HealthGauge value={diastolic} min={50} max={120} low={60} high={90} color={bloodPressureState.color} />
          </div>
          <div style={{ marginTop: "auto", paddingTop: 8 }}>
            <span className={`vital-status-dot ${bloodPressureState.dot}`} />
            <span className={`vital-tag ${bloodPressureState.tag}`}>{bloodPressureState.label}</span>
          </div>
        </div>

        {/* TEMPERATURE */}
        <div className="vital-item">
          <span className="vital-label">Temperature</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span className="vital-val">{vitals.temp}</span>
            <span className="vital-unit">°C</span>
          </div>
          <HealthGauge value={vitals.temp} min={34} max={42} low={36} high={38} color={temperatureState.color} />
          <div style={{ marginTop: "auto", paddingTop: 8 }}>
            <span className={`vital-status-dot ${temperatureState.dot}`} />
            <span className={`vital-tag ${temperatureState.tag}`}>{temperatureState.label}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
