import React, { useState } from "react";
import useArticleRequest from "../hooks/useArticleRequest";
import ArticlePDFExporter from "./ArticlePDFExporter";
import FeedbackModal from "./FeedBackModel";
import "./FeedBackModel.css";
import "./ArticleRequestForm.css";

const ArticleRequestForm = () => {
  const [instruction, setInstruction] = useState("");
  const [rawContent, setRawContent] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);

  const { loading, error, article, requestArticle, setArticle, setError } =
    useArticleRequest();

  // Submit article request
  const handleSubmit = (e) => {
    e.preventDefault();

    if (!rawContent.trim()) {
      setError("Please enter a valid URL");
      return;
    }

    // Clear any previous errors
    setError(null);

    requestArticle({
      input_type: "url",
      input_value: rawContent.trim(),
      instruction: instruction.trim(),
      force_refresh: false,
      async: true,
    });

    setSubmitted(true);
  };

  // Reset form
  const handleReset = () => {
    setSubmitted(false);
    setShowFeedbackModal(false);
    setInstruction("");
    setRawContent("");
    setError(null);
  };

  // Handle successful feedback application
  const handleFeedbackApplied = (updatedArticle) => {
    setArticle(updatedArticle);
    setShowFeedbackModal(false);
  };

  // Handle modal close
  const handleCloseModal = () => {
    setShowFeedbackModal(false);
  };

  // Helper function to render article content as continuous text
  const renderArticleContent = (content) => {
    if (!content) return null;

    return content.split("\n").map((paragraph, index) => {
      // Skip empty paragraphs
      if (!paragraph.trim()) return null;

      return (
        <p key={index} className="article-paragraph">
          {paragraph}
        </p>
      );
    });
  };

  // Combine all article content into one cohesive article
  const getCombinedArticleContent = () => {
    if (!article) return null;

    let combinedContent = [];

    // Add main content first
    if (article.content) {
      combinedContent.push(article.content);
    }

    // Add other sections in logical order
    if (article.summary) {
      combinedContent.push(`\n\nSUMMARY:\n${article.summary}`);
    }

    if (article.project_details) {
      combinedContent.push(`\n\nPROJECT DETAILS:\n${article.project_details}`);
    }

    if (article.participants) {
      combinedContent.push(`\n\nPARTICIPANTS:\n${article.participants}`);
    }

    if (article.organizations) {
      combinedContent.push(`\n\nORGANIZATIONS:\n${article.organizations}`);
    }

    if (article.lots) {
      combinedContent.push(`\n\nLOTS:\n${article.lots}`);
    }

    if (article.key_points) {
      combinedContent.push(`\n\nKEY POINTS:\n${article.key_points}`);
    }

    return combinedContent.join("");
  };

  return (
    <div className="modern-page-container">
      {/* Request Form */}
      {!submitted && (
        <div className="modern-form-container">
          <div className="form-header">
            <div className="form-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                <path
                  d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <polyline
                  points="14,2 14,8 20,8"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <line
                  x1="16"
                  y1="13"
                  x2="8"
                  y2="13"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <line
                  x1="16"
                  y1="17"
                  x2="8"
                  y2="17"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <h1 className="form-title">AI Article Generator</h1>
            <p className="form-subtitle">
              Transform any web content into engaging, well-structured articles
            </p>
          </div>

          <form className="modern-form" onSubmit={handleSubmit}>
            <div className="form-step">
              <div className="step-number">1</div>
              <div className="form-group">
                <label className="modern-label">
                  <span className="label-text">Source URL</span>
                  <span className="label-required">*</span>
                </label>
                <div className="input-container">
                  <div className="input-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                  <input
                    type="url"
                    value={rawContent}
                    onChange={(e) => setRawContent(e.target.value)}
                    placeholder="https://example.com/blog-post-or-content"
                    className="modern-input"
                    required
                  />
                </div>
                <div className="input-help">
                  Enter the URL of any web content you want to transform into an
                  article
                </div>
              </div>
            </div>

            <div className="form-step">
              <div className="step-number">2</div>
              <div className="form-group">
                <label className="modern-label">
                  <span className="label-text">Writing Instructions</span>
                  <span className="label-optional">Optional</span>
                </label>
                <div className="textarea-container">
                  <textarea
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="Customize your article: writing style, tone, focus areas, target audience, or specific requirements (e.g., 'Make it more conversational', 'Focus on benefits for businesses', 'Include more examples')"
                    className="modern-textarea"
                    rows={4}
                    maxLength={5000}
                  />
                  <div className="textarea-counter">
                    <span
                      className={
                        instruction.length > 4500 ? "counter-warning" : ""
                      }
                    >
                      {instruction.length}/5000
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="form-actions">
              <button
                type="submit"
                disabled={loading || !rawContent.trim()}
                className="generate-button"
              >
                {loading ? (
                  <>
                    <div className="button-spinner"></div>
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span>Generate Article</span>
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="modern-error">
                <div className="error-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                    <line
                      x1="15"
                      y1="9"
                      x2="9"
                      y2="15"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                    <line
                      x1="9"
                      y1="9"
                      x2="15"
                      y2="15"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                  </svg>
                </div>
                <div className="error-content">
                  <p>{error}</p>
                  <button
                    type="button"
                    onClick={() => setError(null)}
                    className="error-dismiss"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}
          </form>

          <div className="form-features">
            <div className="feature">
              <div className="feature-icon">🤖</div>
              <div className="feature-text">
                <strong>AI-Powered Writing</strong>
                <span>Advanced natural language processing</span>
              </div>
            </div>
            <div className="feature">
              <div className="feature-icon">✨</div>
              <div className="feature-text">
                <strong>Smart Enhancement</strong>
                <span>Improves readability and engagement</span>
              </div>
            </div>
            <div className="feature">
              <div className="feature-icon">📄</div>
              <div className="feature-text">
                <strong>Export Ready</strong>
                <span>Professional PDF output</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading State - Enhanced for better engagement */}
      {submitted && loading && (
        <div className="modern-loading-container">
          <div className="loading-animation">
            <div className="loading-circle"></div>
            <div className="loading-circle"></div>
            <div className="loading-circle"></div>
          </div>
          <h2 className="loading-title">Creating Your Article</h2>
          <p className="loading-description">
            Our AI is analyzing the source content and crafting an engaging,
            well-structured article. This process may take up to 2-3 minutes for
            complex content.
          </p>

          <div className="loading-tips">
            <h4>💡 Did you know?</h4>
            <p>
              Our AI reads through the entire webpage, extracts key information,
              and creates a comprehensive article tailored to your instructions.
              The more detailed your instructions, the better the output!
            </p>
          </div>
          <div className="loading-progress">
            <div className="progress-bar">
              <div className="progress-fill"></div>
            </div>
            <div className="progress-text">Processing your request...</div>
          </div>
          <div className="loading-steps">
            <div className="loading-step active">
              <div className="step-dot"></div>
              <span>Analyzing content</span>
            </div>
            <div className="loading-step active">
              <div className="step-dot"></div>
              <span>AI writing</span>
            </div>
            <div className="loading-step">
              <div className="step-dot"></div>
              <span>Finalizing</span>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {submitted && error && !loading && (
        <div className="modern-error-container">
          <div className="error-illustration">
            <svg width="80" height="80" viewBox="0 0 24 24" fill="none">
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="2"
              />
              <line
                x1="15"
                y1="9"
                x2="9"
                y2="15"
                stroke="currentColor"
                strokeWidth="2"
              />
              <line
                x1="9"
                y1="9"
                x2="15"
                y2="15"
                stroke="currentColor"
                strokeWidth="2"
              />
            </svg>
          </div>
          <h2 className="error-title">Article Generation Failed</h2>
          <p className="error-description">{error}</p>
          <div className="error-actions">
            <button onClick={handleReset} className="retry-button">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <polyline
                  points="23 4 23 10 17 10"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <polyline
                  points="1 20 1 14 7 14"
                  stroke="currentColor"
                  strokeWidth="2"
                />
                <path
                  d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"
                  stroke="currentColor"
                  strokeWidth="2"
                />
              </svg>
              Try Again
            </button>
            <button onClick={() => setError(null)} className="dismiss-button">
              Dismiss Error
            </button>
          </div>
        </div>
      )}

      {/* Success State - Article Display */}
      {submitted && article && !loading && !error && (
        <div className="card response-card">
          {/* Article Header */}
          <div className="article-header">
            {article.headline && (
              <h1 className="article-title">{article.headline}</h1>
            )}
            <div className="article-meta">
              {article.generation_time && (
                <span className="meta-badge">
                  ⚡ Generated in {article.generation_time}s
                </span>
              )}
              {article.from_cache && <span className="cached-badge"></span>}
              {article.validation && (
                <span
                  className={`validation-badge ${article.validation.toLowerCase()}`}
                >
                  {article.validation === "valid"
                    ? "✅"
                    : article.validation === "invalid"
                    ? "❌"
                    : "⏳"}{" "}
                  {article.validation}
                </span>
              )}
              <span className="meta-badge"></span>
            </div>
          </div>

          {/* Single Article Content Section */}
          <div className="article-body">
            <div className="article-content">
              {renderArticleContent(getCombinedArticleContent())}
            </div>
          </div>

          {/* Action Buttons - Fixed positioning */}
          <div className="response-footer">
            <div className="action-buttons-container">
              <ArticlePDFExporter article={article} className="pdf-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <polyline
                    points="14,2 14,8 20,8"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Export PDF
              </ArticlePDFExporter>

              <button
                className="feedback-btn"
                onClick={() => setShowFeedbackModal(true)}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                </svg>
                Give Feedback
              </button>
            </div>
          </div>

          {/* Back Button */}
          <div className="back-section">
            <button className="back-btn" onClick={handleReset}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M19 12H5M12 19l-7-7 7-7"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Create Another Article
            </button>
          </div>
        </div>
      )}

      {/* Feedback Modal */}
      <FeedbackModal
        articleId={article?.article_id}
        onFeedbackApplied={handleFeedbackApplied}
        onClose={handleCloseModal}
        isOpen={showFeedbackModal}
      />
    </div>
  );
};

export default ArticleRequestForm;
