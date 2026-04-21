# 🖥️ ElderGuard AI — Patient Monitoring Dashboard

ElderGuard is a high-fidelity monitoring interface designed to provide real-time situational awareness during emergency fall events.

## ✨ Key Features

- **High-Density Monitoring**: A technical, engine-style dashboard that prioritizes critical information.
- **Real-Time Vitals Visualization**: Dynamic display of detection signals and agent reasoning.
- **Agentic Workflow Synchronization**: Visual tracking of the reasoning, communication, and execution agents.
- **Interactive Emergency Interface**: Multi-turn conversation panel with clinical guided replies.
- **Autonomous Dispatch Simulation**: Real-time status tracking for emergency dispatch and family notifications.

## 🛠️ Tech Stack

- **Framework**: React 19 + Vite 6
- **Styling**: Vanilla CSS (Design Tokens & Custom Utilities)
- **State Management**: React Hooks + Firestore Real-time Sync
- **Animations**: CSS Keyframes for status pulses and smooth transitions
- **Icons**: Lucide React

## 🚀 Getting Started

### Local Development

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend/health-guard-ai
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure Environment**:
   Create a `.env` file based on `.env.example` and add your Firebase configuration:
   ```env
   VITE_FIREBASE_API_KEY=your_key
   VITE_FIREBASE_AUTH_DOMAIN=your_domain
   VITE_API_BASE_URL=http://localhost:8000
   ```

4. **Run the application**:
   ```bash
   npm run dev
   ```

## 📁 Project Structure

- **`src/components/dashboard`**: Core dashboard modules (Action Cards, Vitals, Conversation).
- **`src/components/pages`**: Main page views including the High-Density Dashboard and Patient Profile.
- **`src/components/ui`**: Reusable Design System components (Modals, Buttons, Alerts).
- **`src/lib`**: Firebase initialization and API client configurations.

---
*Developed by the **Hypernode Team** for Project 2030 (2026).*
