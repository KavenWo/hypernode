export default function VideoSelectionModal({
  videos,
  selectedVideoId,
  loading,
  error,
  onClose,
  onSelect,
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal video-modal" style={{ position: "relative" }} onClick={(event) => event.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>x</button>
        <h2>Select Demo Fall Video</h2>
        <div className="modal-section">
          <h4>Controlled Input</h4>
          <p className="video-modal-copy">
            Choose a preset local clip so the vision agent starts with deterministic fall-detection behavior.
          </p>
        </div>

        {loading ? <div className="video-modal-state">Loading demo videos...</div> : null}
        {error ? <div className="video-modal-error">{error}</div> : null}

        <div className="video-option-list">
          {videos.map((video) => {
            const selected = video.id === selectedVideoId;

            return (
              <button
                key={video.id}
                type="button"
                className={`video-option-card ${selected ? "selected" : ""}`}
                onClick={() => onSelect(video)}
                disabled={!video.available}
              >
                <div className="video-option-preview">
                  <video src={video.videoUrl} controls muted preload="metadata" />
                </div>
                <div className="video-option-body">
                  <div className="video-option-top">
                    <div>
                      <div className="video-option-title">{video.label}</div>
                      <div className="video-option-subtitle">{video.description}</div>
                    </div>
                    <span className="tag">
                      AI analyzed at start
                    </span>
                  </div>
                  <div className="video-option-meta">
                    <span className={`tag ${video.available ? "tag-green" : "tag-amber"}`}>
                      {video.available ? "Available" : "Missing file"}
                    </span>
                    <span className="tag">Source - {video.sourceType?.replaceAll("_", " ")}</span>
                  </div>
                  <div className="video-option-summary">{video.summary}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
