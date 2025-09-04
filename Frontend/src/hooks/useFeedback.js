import { useState } from "react";
import api from "../utils/apiHandler"; // Axios instance

const useFeedback = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Send feedback for a specific article section
   * @param {string} articleId - ID of the article
   * @param {string} section - Section to apply feedback (headline, project_details, etc.)
   * @param {string} feedbackText - Feedback text
   * @returns {object|null} - Updated article data or null if failed
   */
  const sendFeedback = async (articleId, section, feedbackText) => {
    setLoading(true);
    setError(null);

    try {
      // Map frontend section names to backend field names based on your serializer
      const sectionMapping = {
        headline: "headline",
        project_details: "details", // Backend expects 'details' according to FeedbackApplicationSerializer
        participants: "participants",
        lots: "lots",
        organizations: "organizations",
      };

      const backendSection = sectionMapping[section] || section;

      // Construct payload according to FeedbackApplicationSerializer
      const payload = {
        article_id: articleId,
        feedback: { [backendSection]: feedbackText },
        async_processing: false, // Use synchronous processing for immediate feedback (your backend uses 'async_processing' not 'async')
      };

      console.log("Sending feedback payload:", payload); // Debug log

      const response = await api.post("feedback/", payload);

      if (response.data.success) {
        const responseData = response.data.data;

        // Check if backend returned async task
        if (responseData.async && responseData.task_id) {
          // Handle async processing - poll for results
          return await pollFeedbackTask(responseData.task_id);
        } else {
          // Handle synchronous response
          return handleFeedbackResponse(responseData);
        }
      } else {
        setError(response.data.message || "Feedback application failed");
        return null;
      }
    } catch (err) {
      console.error("Feedback error:", err);
      
      // Handle different types of errors from your backend
      let errorMessage = "Failed to apply feedback";
      
      if (err.response?.data) {
        // Backend returned structured error
        errorMessage = err.response.data.message || 
                     err.response.data.detail || 
                     err.response.data.error ||
                     errorMessage;
        
        // Handle validation errors from your serializer
        if (err.response.data.data && typeof err.response.data.data === 'object') {
          const validationErrors = Object.values(err.response.data.data).flat();
          if (validationErrors.length > 0) {
            errorMessage = validationErrors.join(', ');
          }
        }
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  };

  /**
   * Poll task status for async feedback requests
   * Based on your TaskStatusView endpoint: tasks/<task_id>/status/
   */
  const pollFeedbackTask = async (
    taskId,
    maxAttempts = 15,
    interval = 2000 // Increase interval to 2s to match typical backend processing time
  ) => {
    let attempts = 0;

    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          // Use the correct endpoint from your URLs
          const response = await api.get(`tasks/${taskId}/status/`);

          if (response.data.success) {
            const taskData = response.data.data;

            if (taskData.status === "completed") {
              // Task completed successfully
              if (taskData.result && taskData.result.success) {
                resolve(handleFeedbackResponse(taskData.result));
              } else {
                const errorMsg = taskData.result?.error || "Task completed with errors";
                setError(errorMsg);
                reject(new Error(errorMsg));
              }
            } else if (taskData.status === "failed") {
              // Task failed
              const errorMsg = taskData.error || "Task execution failed";
              setError(errorMsg);
              reject(new Error(errorMsg));
            } else if (taskData.status === "processing") {
              // Still processing, continue polling
              attempts++;
              if (attempts < maxAttempts) {
                setTimeout(poll, interval);
              } else {
                const timeoutMsg = "Feedback task timed out - please try again";
                setError(timeoutMsg);
                reject(new Error(timeoutMsg));
              }
            } else {
              // Unknown status
              const unknownMsg = `Unknown task status: ${taskData.status}`;
              setError(unknownMsg);
              reject(new Error(unknownMsg));
            }
          } else {
            const statusMsg = "Failed to check task status";
            setError(statusMsg);
            reject(new Error(statusMsg));
          }
        } catch (err) {
          console.error("Task polling error:", err);
          const pollMsg = err.response?.data?.message || "Failed to check task status";
          setError(pollMsg);
          reject(err);
        }
      };

      // Start polling immediately
      poll();
    });
  };

  /**
   * Handle successful feedback response
   * Based on your ApplyFeedbackView response structure
   */
  const handleFeedbackResponse = (responseData) => {
    if (responseData.article && responseData.article_id) {
      // Return the updated article data in the expected format
      // Map your backend response to frontend format
      return {
        ...responseData.article,
        article_id: responseData.article_id,
        feedback_applied: responseData.feedback_applied || true,
        // Ensure all expected fields are present
        headline: responseData.article.headline || "",
        project_details: responseData.article.project_details || "",
        participants: responseData.article.participants || "",
        lots: responseData.article.lots || "",
        organizations: responseData.article.organizations || "",
      };
    } else if (responseData.article_data) {
      // Alternative response structure
      return {
        ...responseData.article_data,
        article_id: responseData.article_id,
        feedback_applied: responseData.feedback_applied || true,
      };
    } else {
      console.error("Invalid response structure:", responseData);
      setError("Invalid article data received from server");
      return null;
    }
  };

  /**
   * Send feedback for multiple sections at once
   * @param {string} articleId - ID of the article
   * @param {object} feedbackObj - Object with multiple sections and feedback
   * @returns {object|null} - Updated article data or null if failed
   */
  const sendMultipleFeedback = async (articleId, feedbackObj) => {
    setLoading(true);
    setError(null);

    try {
      // Map all sections
      const sectionMapping = {
        headline: "headline",
        project_details: "details",
        participants: "participants", 
        lots: "lots",
        organizations: "organizations",
      };

      const mappedFeedback = {};
      Object.entries(feedbackObj).forEach(([section, feedback]) => {
        const backendSection = sectionMapping[section] || section;
        mappedFeedback[backendSection] = feedback;
      });

      const payload = {
        article_id: articleId,
        feedback: mappedFeedback,
        async_processing: false,
      };

      const response = await api.post("feedback/", payload);

      if (response.data.success) {
        const responseData = response.data.data;
        
        if (responseData.async && responseData.task_id) {
          return await pollFeedbackTask(responseData.task_id);
        } else {
          return handleFeedbackResponse(responseData);
        }
      } else {
        setError(response.data.message || "Feedback application failed");
        return null;
      }
    } catch (err) {
      console.error("Multiple feedback error:", err);
      const errorMessage = err.response?.data?.message || 
                          err.response?.data?.detail || 
                          err.message || 
                          "Failed to apply feedback";
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return {
    sendFeedback,
    sendMultipleFeedback,
    loading,
    error,
    setError,
  };
};

export default useFeedback;