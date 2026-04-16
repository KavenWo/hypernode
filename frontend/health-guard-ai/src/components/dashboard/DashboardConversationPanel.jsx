function ChatBubble({ role, text }) {
  const isAssistant = role === "assistant";

  return (
    <div style={{ display: "flex", justifyContent: isAssistant ? "flex-start" : "flex-end" }}>
      <div
        className="dashboard-chat-bubble"
        style={{
          background: isAssistant
            ? "linear-gradient(135deg, var(--surface) 0%, #fef3c7 100%)"
            : "linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%)",
        }}
      >
        <div className="dashboard-chat-role">
          {isAssistant ? "Communication Agent" : role}
        </div>
        <div style={{ fontSize: 14, color: "var(--text)", lineHeight: 1.6 }}>{text}</div>
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start" }}>
      <div
        className="dashboard-chat-bubble dashboard-typing-bubble"
        style={{ background: "linear-gradient(135deg, var(--surface) 0%, #fef3c7 100%)" }}
      >
        <div className="dashboard-chat-role">Communication Agent</div>
        <div className="typing-dots" aria-label="Agent typing">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  );
}

export default function DashboardConversationPanel({
  profile,
  latestTurn,
  messages,
  draftMessage,
  setDraftMessage,
  phase,
  sendTurn,
}) {
  const isAgentTyping = phase === "starting" || phase === "sending";

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, padding: "24px", overflow: "hidden" }}>
      <div className="card-title" style={{ marginBottom: 20 }}>Conversation Loop</div>

      {latestTurn?.interaction && (
        <div style={{ marginBottom: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span className="tag">Target - {latestTurn.interaction.communication_target}</span>
          <span className="tag">Mode - {latestTurn.interaction.interaction_mode}</span>
          <span className="tag">Style - {latestTurn.interaction.guidance_style}</span>
          <span className="tag">Reasoning - {latestTurn.reasoning_status || "idle"}</span>
        </div>
      )}

      {messages.length === 0 && (
        <div className="empty-state" style={{ minHeight: 140, marginBottom: 14 }}>
          <span className="empty-icon">AI</span>
          <p>
            No active session for {profile.name}.<br />
            Start the agent flow from the setup card to begin.
          </p>
        </div>
      )}

      <div className="dashboard-chat-stream">
        {messages.map((message, index) => (
          <ChatBubble key={`${message.role}-${index}`} role={message.role} text={message.text} />
        ))}
        {isAgentTyping && <TypingBubble />}
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
        <div className="form-group">
          <label className="form-label">Next Patient or Bystander Message</label>
          <textarea
            className="form-input"
            rows="3"
            value={draftMessage}
            onChange={(event) => setDraftMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (draftMessage.trim() && phase !== "sending" && latestTurn) {
                  sendTurn();
                }
              }
            }}
            placeholder="Type what the patient or bystander says next..."
          />
        </div>

        {latestTurn?.quick_replies?.length > 0 && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {latestTurn.quick_replies.map((reply) => (
              <button key={reply} className="btn btn-ghost btn-sm" onClick={() => setDraftMessage(reply)}>
                {reply}
              </button>
            ))}
          </div>
        )}

        <button
          className="btn btn-green"
          style={{ width: "100%", justifyContent: "center" }}
          onClick={sendTurn}
          disabled={!draftMessage.trim() || phase === "sending" || !latestTurn}
        >
          {phase === "sending" ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}
