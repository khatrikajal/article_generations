import { useState } from "react";
import useFeedback from "../hooks/useFeedback";
import "./FeedBackModel.css";

const FeedbackModal = ({ articleId, onFeedbackApplied, onClose, isOpen }) => {
  const [section, setSection] = useState("headline");
  const [feedbackText, setFeedbackText] = useState("");
  const [success, setSuccess] = useState(false);
  const { sendFeedback, loading, error, setError } = useFeedback();

  const sections = [
    { value: "headline", label: "Headline" },
    { value: "project_details", label: "Project Details" },
    { value: "participants", label: "Participants" },
    { value: "lots", label: "Lots" },
    { value: "organizations", label: "Organizations" },
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!articleId || !feedbackText.trim()) {
      setError("Article ID and feedback text are required");
      return;
    }

    setSuccess(false);
    setError(null);

    try {
      const updatedArticle = await sendFeedback(
        articleId,
        section,
        feedbackText.trim()
      );

      if (updatedArticle) {
        setSuccess(true);
        onFeedbackApplied(updatedArticle);
        
        // Auto-close modal after success
        setTimeout(() => {
          setSuccess(false);
          setFeedbackText("");
          onClose();
        }, 2000);
      }
    } catch (err) {
      console.error("Error sending feedback:", err);
      setError(err.message || "Failed to apply feedback");
    }
  };

  const handleClose = () => {
    setFeedbackText("");
    setError(null);
    setSuccess(false);
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="feedback-modal-backdrop" onClick={handleBackdropClick}>
      <div className="feedback-modal">
        <div className="feedback-modal-header">
          <h3>Improve Article Section</h3>
          <button 
            className="feedback-modal-close"
            onClick={handleClose}
            disabled={loading}
          >
            ×
          </button>
        </div>

        <div className="feedback-modal-body">
          {success && (
            <div className="feedback-success-message">
              <div className="feedback-success-icon">✓</div>
              <p>Feedback applied successfully! The article has been updated.</p>
            </div>
          )}

          {!success && (
            <>
              <div className="feedback-intro">
                <p>Help us improve this article section by providing specific feedback.</p>
              </div>

              <form onSubmit={handleSubmit} className="feedback-modal-form">
                <div className="feedback-form-group">
                  <label htmlFor="section-select">Section to improve:</label>
                  <select
                    id="section-select"
                    value={section}
                    onChange={(e) => setSection(e.target.value)}
                    disabled={loading}
                    className="feedback-select"
                  >
                    {sections.map((sec) => (
                      <option key={sec.value} value={sec.value}>
                        {sec.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="feedback-form-group">
                  <label htmlFor="feedback-textarea">
                    Your feedback:
                    <span className="feedback-required">*</span>
                  </label>
                  <textarea
                    id="feedback-textarea"
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    required
                    placeholder={`Enter specific feedback for the ${sections
                      .find((s) => s.value === section)
                      ?.label.toLowerCase()} section...`}
                    rows={4}
                    maxLength={2000}
                    disabled={loading}
                    className="feedback-textarea"
                  />
                  <div className="feedback-char-count">
                    <small>{feedbackText.length}/2000 characters</small>
                  </div>
                </div>

                {error && (
                  <div className="feedback-error-message">
                    <div className="feedback-error-icon">⚠</div>
                    <div className="feedback-error-content">
                      <p>{error}</p>
                      <button
                        type="button"
                        onClick={() => setError(null)}
                        className="feedback-error-dismiss"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                )}

                <div className="feedback-modal-actions">
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={loading}
                    className="feedback-cancel-btn"
                  >
                    Cancel
                  </button>
                  
                  <button
                    type="submit"
                    disabled={loading || !feedbackText.trim()}
                    className="feedback-submit-btn"
                  >
                    {loading ? (
                      <>
                        <div className="feedback-spinner"></div>
                        Applying...
                      </>
                    ) : (
                      "Apply Feedback"
                    )}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>

        {loading && (
          <div className="feedback-loading-overlay">
            <div className="feedback-loading-content">
              <div className="feedback-loader"></div>
              <p>Applying your feedback...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FeedbackModal;