import { useEffect, useRef } from "react";

function ChatBubble({ message }) {
  const { role, text, reasoning_input_version, comm_reasoning_required, comm_reasoning_reason, session_version } = message;
  const isAssistant = role === "assistant";
  const showCommDecision = role !== "assistant" && comm_reasoning_required !== null && comm_reasoning_required !== undefined;

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
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
          {reasoning_input_version != null && <span className="tag">V{reasoning_input_version}</span>}
          {session_version != null && <span className="tag">S{session_version}</span>}
          {showCommDecision && (
            <span className={`tag ${comm_reasoning_required ? "tag-red" : ""}`}>
              Rerun {comm_reasoning_required ? "Yes" : "No"}
            </span>
          )}
        </div>
        <div style={{ fontSize: 14, color: "var(--text)", lineHeight: 1.6 }}>{text}</div>
        {showCommDecision && comm_reasoning_reason && (
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-sub)", lineHeight: 1.5 }}>
            Comm decision: {comm_reasoning_reason}
          </div>
        )}
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
  const hasAssistantMessage = messages.some((message) => message.role === "assistant" && message.text?.trim());
  const isAgentTyping = phase === "sending" || (phase === "starting" && !hasAssistantMessage);
  const canonicalState = latestTurn?.state;
  const latestPrompt = latestTurn?.canonical_communication_state?.latest_prompt;
  const streamEndRef = useRef(null);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAgentTyping]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, padding: "24px", overflow: "hidden" }}>
      <div className="card-title" style={{ marginBottom: 20 }}>Conversation Loop</div>

      {latestTurn?.interaction && (
        <div style={{ marginBottom: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span className="tag">Target - {latestTurn.interaction.communication_target}</span>
          <span className="tag">Mode - {latestTurn.interaction.interaction_mode}</span>
          <span className="tag">Style - {latestTurn.interaction.guidance_style}</span>
          <span className="tag">Reasoning - {latestTurn.reasoning_status || "idle"}</span>
          {canonicalState && <span className="tag">State - {canonicalState}</span>}
        </div>
      )}

      {latestPrompt && (
        <div
          style={{
            marginBottom: 14,
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: 13,
            color: "var(--text-sub)",
            lineHeight: 1.6,
          }}
        >
          <strong style={{ color: "var(--text)" }}>Current Prompt:</strong> {latestPrompt}
        </div>
      )}

      {canonicalState === "optional_flags_check" && (
        <div
          style={{
            marginBottom: 14,
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: 13,
            color: "var(--text-sub)",
            lineHeight: 1.6,
          }}
        >
          <strong style={{ color: "var(--text)" }}>Signal Extraction:</strong> At this step the communication agent is still using AI to interpret the reply, but it is only collecting the allowed flags: bleeding, pain, or mobility issues.
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
          <ChatBubble key={`${message.role}-${message.session_version ?? "na"}-${index}`} message={message} />
        ))}
        {isAgentTyping && <TypingBubble />}
        <div ref={streamEndRef} />
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
            placeholder={latestPrompt || "Type what the patient or bystander says next..."}
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
