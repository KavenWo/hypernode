export function getSeverityStyle(sev) {
  if (!sev || sev === "None" || sev === "Low") return "panel-low";
  if (sev === "Medium") return "panel-med";
  return "panel-high";
}

export function getSeverityIcon(sev) {
  if (!sev || sev === "None") return "✅";
  if (sev === "Low") return "🟡";
  if (sev === "Medium") return "🟠";
  return "🔴";
}
