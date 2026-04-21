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

        {loading ? <div className="video-modal-state">Loading demo videos...</div> : null}
        {error ? <div className="video-modal-error">{error}</div> : null}

        <div className="video-option-list">
          {videos.map((video, index) => {
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
                  <video src={video.videoUrl} autoPlay loop muted playsInline preload="metadata" />
                </div>
                <div className="video-option-body">
                  <div className="video-option-title">Clip {index + 1}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
