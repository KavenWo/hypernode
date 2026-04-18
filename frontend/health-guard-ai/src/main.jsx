import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { initializeFirebaseAnalytics, initializeFirebaseAuth } from './lib/firebase.js'

initializeFirebaseAuth().catch((error) => {
  console.error("Failed to initialize Firebase Auth", error);
});

initializeFirebaseAnalytics().catch((error) => {
  console.error("Failed to initialize Firebase Analytics", error);
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
