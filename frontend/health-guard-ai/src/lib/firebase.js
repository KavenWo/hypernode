import { initializeApp } from "firebase/app";
import { getAnalytics, isSupported as analyticsSupported } from "firebase/analytics";
import {
  browserLocalPersistence,
  getAuth,
  onAuthStateChanged,
  setPersistence,
  signInAnonymously,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || undefined,
};

function assertFirebaseConfig() {
  const missingKeys = Object.entries(firebaseConfig)
    .filter(([, value]) => !value)
    .map(([key]) => key)
    .filter((key) => key !== "measurementId");

  if (missingKeys.length > 0) {
    throw new Error(`Missing Firebase env vars: ${missingKeys.join(", ")}`);
  }
}

assertFirebaseConfig();

export const firebaseApp = initializeApp(firebaseConfig);
export const firebaseAuth = getAuth(firebaseApp);

let analyticsPromise = null;
let persistencePromise = null;

function ensureBrowser() {
  return typeof window !== "undefined";
}

export async function initializeFirebaseAuth() {
  if (!ensureBrowser()) {
    return firebaseAuth;
  }
  if (!persistencePromise) {
    persistencePromise = setPersistence(firebaseAuth, browserLocalPersistence).catch((error) => {
      persistencePromise = null;
      throw error;
    });
  }
  await persistencePromise;
  return firebaseAuth;
}

export async function initializeFirebaseAnalytics() {
  if (!ensureBrowser()) {
    return null;
  }
  if (!analyticsPromise) {
    analyticsPromise = analyticsSupported()
      .then((supported) => (supported ? getAnalytics(firebaseApp) : null))
      .catch(() => null);
  }
  return analyticsPromise;
}

export async function signInAnonymouslyIfNeeded() {
  await initializeFirebaseAuth();

  if (firebaseAuth.currentUser) {
    return firebaseAuth.currentUser;
  }

  const credential = await signInAnonymously(firebaseAuth);
  return credential.user;
}

export async function getCurrentFirebaseUser() {
  await initializeFirebaseAuth();

  if (firebaseAuth.currentUser) {
    return firebaseAuth.currentUser;
  }

  return new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(firebaseAuth, (user) => {
      unsubscribe();
      resolve(user);
    });
  });
}

export async function getFirebaseIdToken(forceRefresh = false) {
  const user = await getCurrentFirebaseUser();
  if (!user) {
    return null;
  }
  return user.getIdToken(forceRefresh);
}

export { firebaseConfig };
