import { Play, RotateCcw, Video, Square } from "lucide-react";

export default function DashboardSessionControlCard({
  runtimeStatus,
  selectedVideo,
  onOpenVideoSelector,
  phase,
  startSession,
  stopSession,
  resetConversation,
}) {
  const isSessionActive = phase !== "idle" && phase !== "starting" && phase !== "analyzing_video";

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden", display: "flex" }}>
      {/* Left Section: Video Preview */}
      <div
        style={{
          width: 180,
          background: "transparent",
          borderRight: "1px solid var(--border)",
          padding: 12,
          flexShrink: 0
        }}
      >
        <div
          onClick={onOpenVideoSelector}
          style={{
            aspectRatio: "3/4",
            borderRadius: 12,
            overflow: "hidden",
            position: "relative",
            cursor: "pointer",
            background: "var(--surface2)",
            border: "1px solid var(--border)"
          }}
        >
          {selectedVideo ? (
            <video
              src={selectedVideo.videoUrl}
              autoPlay
              muted
              loop
              playsInline
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyItems: "center", justifyContent: "center", color: "var(--text-muted)", textAlign: "center", padding: 10 }}>
              <Video size={20} style={{ marginBottom: 6 }} />
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>No Video</div>
            </div>
          )}
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, padding: 8, background: "linear-gradient(to top, rgba(0,0,0,0.6), transparent)", color: "white", fontSize: 10, fontWeight: 600, textAlign: "center" }}>
            {selectedVideo ? "Change Video" : "Select Clip"}
          </div>
        </div>
      </div>

      {/* Right Section: Info & Controls */}
      <div style={{ flex: 1, padding: 14, display: "flex", flexDirection: "column" }}>
        <div className="card-title" style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <Video size={14} />
          Workflow Launcher
        </div>

        <div style={{ fontSize: 11, color: "var(--text-sub)", lineHeight: 1.5, marginBottom: 16 }}>
          {selectedVideo ? (
            <>Ready to analyze <span style={{ color: "var(--text)", fontWeight: 600 }}>{selectedVideo.label}</span>. Start the session to begin the clinical response chain.</>
          ) : (
            <>Select a demo clip or use the default simulation to begin the autonomous fall flow.</>
          )}
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: "auto" }}>
          <button
            className={`btn ${isSessionActive ? "btn-red" : "btn-green"}`}
            style={{ flex: 1, justifyContent: "center", borderRadius: "10px", height: 40, fontSize: 11 }}
            onClick={isSessionActive ? stopSession : startSession}
            disabled={!isSessionActive && (phase === "starting" || phase === "analyzing_video")}
          >
            {phase === "analyzing_video" ? (
              "Analyzing..."
            ) : phase === "starting" ? (
              "Launching..."
            ) : isSessionActive ? (
              <>
                <Square size={14} fill="white" />
                Stop Session
              </>
            ) : (
              <>
                <Play size={14} fill="white" />
                Start Session
              </>
            )}
          </button>
          <button
            className="btn btn-ghost"
            style={{ padding: "0 12px", height: 40, justifyContent: "center", borderRadius: "10px", fontSize: 11 }}
            onClick={resetConversation}
            title="Stop and Reset current session"
          >
            <RotateCcw size={14} />
            Reset
          </button>
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border-bright)", opacity: 0.7 }}>
          <div style={{
            width: 5, height: 5, borderRadius: "50%",
            background: runtimeStatus?.backend_ok ? "var(--green)" : "var(--red)",
            marginTop: 5
          }} />
          <div style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Ready: {runtimeStatus?.backend_ok ? "Yes" : "No"} · Model: Gemini
          </div>
        </div>
      </div>
    </div>
  );
}
