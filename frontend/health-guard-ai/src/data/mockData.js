export const DEMO_PROFILES = [
  {
    id: 1,
    userId: "user_healthy_001",
    name: "Daniel Tan",
    age: 34,
    bloodType: "O+",
    gender: "Male",
    avatar: "🙂",
    scenarioLabel: "Healthy baseline",
    profileNote: "Independent adult with no major fall-risk modifiers and no chronic medication use.",
    conditions: [],
    medications: [],
    allergies: [],
    contacts: [{ name: "Melissa Tan", relation: "Sister", phone: "+60 12-220 1445" }],
    bloodThinners: false,
    mobilitySupport: false,
    riskProfile: { cardiovascular: 18, fall: 8, respiratory: 12 },
  },
  {
    id: 2,
    userId: "user_mobility_001",
    name: "Puan Salmah Yusof",
    age: 76,
    bloodType: "A+",
    gender: "Female",
    avatar: "🧓",
    scenarioLabel: "Age-related mobility issues",
    profileNote: "Uses a cane outdoors and has slower gait from osteoarthritis and sarcopenia.",
    conditions: ["Osteoarthritis", "Sarcopenia", "History of prior fall"],
    medications: ["Paracetamol 500mg", "Vitamin D3", "Losartan 50mg"],
    allergies: ["NSAIDs"],
    contacts: [{ name: "Farid Yusof", relation: "Son", phone: "+60 16-998 2104" }],
    bloodThinners: false,
    mobilitySupport: true,
    riskProfile: { cardiovascular: 46, fall: 74, respiratory: 24 },
  },
  {
    id: 3,
    userId: "user_001",
    name: "Amina Rahman",
    age: 78,
    bloodType: "B+",
    gender: "Female",
    avatar: "👵",
    scenarioLabel: "Blood thinners",
    profileNote: "Higher-risk case because anticoagulants increase concern after any head strike or hidden bleed.",
    conditions: ["Hypertension", "Osteoporosis", "History of prior fall"],
    medications: ["Amlodipine", "Warfarin"],
    allergies: ["Penicillin"],
    contacts: [{ name: "Nur Rahman", relation: "Daughter", phone: "+60 12-345 6789" }],
    bloodThinners: true,
    mobilitySupport: true,
    riskProfile: { cardiovascular: 72, fall: 81, respiratory: 36 },
  },
];

export const PROFILE_VITAL_PRESETS = {
  user_healthy_001: {
    normal: { hr: 72, spo2: 98, bp: "118/76", temp: 36.7 },
    abnormal: { hr: 126, spo2: 92, bp: "88/58", temp: 38.1 },
  },
  user_mobility_001: {
    normal: { hr: 78, spo2: 97, bp: "132/84", temp: 36.8 },
    abnormal: { hr: 112, spo2: 93, bp: "96/62", temp: 37.7 },
  },
  user_001: {
    normal: { hr: 82, spo2: 96, bp: "136/86", temp: 36.9 },
    abnormal: { hr: 118, spo2: 91, bp: "92/58", temp: 37.8 },
  },
};

export function getVitalsPreset(profileUserId, mode = "normal") {
  const profilePresets = PROFILE_VITAL_PRESETS[profileUserId] || PROFILE_VITAL_PRESETS.user_healthy_001;
  return profilePresets[mode] || profilePresets.normal;
}

export const HISTORY_SEED = [
  {
    id: "h1",
    timestamp: "2026-04-14 14:32",
    profile: "Puan Salmah Yusof",
    event: "Fall Conversation Escalated",
    severity: "High",
    action: "Family Contact Queued",
    summary: "Mobility-risk scenario escalated after the patient reported hip pain and difficulty standing.",
  },
  {
    id: "h2",
    timestamp: "2026-04-13 09:14",
    profile: "Amina Rahman",
    event: "Blood Thinner Safety Alert",
    severity: "Critical",
    action: "EMS Dispatched",
    summary: "Possible head strike while on warfarin triggered emergency dispatch and hospital pre-alert.",
  },
];
