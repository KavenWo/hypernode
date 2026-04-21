export const DEMO_PROFILES = [
  {
    id: 1,
    userId: "user_001",
    name: "Amina Rahman",
    age: 78,
    bloodType: "B+",
    gender: "Female",
    avatar: "🙂",
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
  user_001: {
    normal: { hr: 82, spo2: 96, bp: "122/78", temp: 36.9 },
    abnormal: { hr: 118, spo2: 91, bp: "92/58", temp: 37.8 },
  },
};

export function getVitalsPreset(profileUserId, mode = "normal") {
  const profilePresets = PROFILE_VITAL_PRESETS[profileUserId] || PROFILE_VITAL_PRESETS.user_001;
  return profilePresets[mode] || profilePresets.normal;
}
