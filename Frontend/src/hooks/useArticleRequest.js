import { useState } from "react";
import api from "../utils/apiHandler"; // Axios instance

const useArticleRequest = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [article, setArticle] = useState(null);

  /**
   * Request article generation
   * @param {object} requestData - The request payload
   * @param {string} requestData.input_type - Type of input ("url" or "text")
   * @param {string} requestData.input_value - The URL or text content
   * @param {string} requestData.instruction - Optional instruction
   * @param {boolean} requestData.force_refresh - Whether to force refresh
   * @param {boolean} requestData.async - Whether to use async processing
   */
  const requestArticle = async (requestData) => {
    setLoading(true);
    setError(null);
    setArticle(null);

    try {
      // Default values
      const payload = {
        input_type: requestData.input_type,
        input_value: requestData.input_value,
        instruction: requestData.instruction || "",
        force_refresh: requestData.force_refresh || false,
        async: requestData.async !== false, // Default to true
      };

      console.log("Making API request with payload:", payload);
      const response = await api.post("generate/", payload);

      if (response.data.success) {
        const responseData = response.data.data;
        console.log("API response received:", responseData);

        if (responseData.async && responseData.task_id) {
          console.log("Starting async polling for task:", responseData.task_id);
          // Handle async processing - poll for results
          await pollTaskStatus(responseData.task_id);
        } else {
          console.log("Processing synchronous response");
          // Handle synchronous response
          handleArticleResponse(responseData);
        }
      } else {
        console.error("API request failed:", response.data);
        setError(response.data.message || "Article generation failed");
        setLoading(false); // Important: Set loading to false on error
      }
    } catch (err) {
      console.error("Article request error:", err);
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          err.message ||
          "Failed to generate article"
      );
      setLoading(false); // Important: Set loading to false on error
    }
    // Don't set loading to false here - it should only be set to false after success or error
  };

  /**
   * Poll task status for async requests
   */
  const pollTaskStatus = async (taskId, maxAttempts = 60, interval = 3000) => {
    let attempts = 0;
    console.log(
      "Starting polling with max attempts:",
      maxAttempts,
      "interval:",
      interval
    );

    const poll = async () => {
      try {
        console.log(
          `Polling attempt ${attempts + 1}/${maxAttempts} for task:`,
          taskId
        );
        const response = await api.get(`tasks/${taskId}/status/`);

        if (response.data.success) {
          const taskData = response.data.data;
          console.log("Task status:", taskData.status);

          if (taskData.status === "completed") {
            // Task completed successfully
            console.log("Task completed, processing result");
            if (taskData.result && taskData.result.success) {
              handleArticleResponse(taskData.result);
              return; // Exit polling
            } else {
              console.error("Task completed with errors:", taskData.result);
              setError(taskData.result?.error || "Task completed with errors");
              setLoading(false);
              return; // Exit polling
            }
          } else if (taskData.status === "failed") {
            // Task failed
            console.error("Task failed:", taskData.error);
            setError(taskData.error || "Task execution failed");
            setLoading(false);
            return; // Exit polling
          } else if (
            taskData.status === "processing" ||
            taskData.status === "pending"
          ) {
            // Still processing, continue polling
            attempts++;
            if (attempts < maxAttempts) {
              console.log("Task still processing, continuing to poll...");
              setTimeout(poll, interval);
            } else {
              console.error("Task timed out after", maxAttempts, "attempts");
              setError(
                "Task timed out - please try again with a shorter URL or simpler content"
              );
              setLoading(false);
            }
          } else {
            // Unknown status
            console.warn("Unknown task status:", taskData.status);
            attempts++;
            if (attempts < maxAttempts) {
              setTimeout(poll, interval);
            } else {
              setError("Unknown task status - please try again");
              setLoading(false);
            }
          }
        } else {
          console.error("Failed to check task status:", response.data);
          setError("Failed to check task status");
          setLoading(false);
        }
      } catch (err) {
        console.error("Task polling error:", err);
        attempts++;
        if (attempts < maxAttempts) {
          // Continue polling on network errors (API might be temporarily unavailable)
          console.log("Polling error, retrying...");
          setTimeout(poll, interval);
        } else {
          setError("Failed to check task status - please try again");
          setLoading(false);
        }
      }
    };

    // Start polling immediately
    poll();
  };

  /**
   * Handle successful article response
   */
  const handleArticleResponse = (responseData) => {
    console.log("Processing article response:", responseData);

    if (responseData.article_data) {
      // Map the response data to match your component's expected structure
      const articleData = {
        ...responseData.article_data,
        article_id: responseData.article_id,
        request_id: responseData.request_id,
        validation: responseData.validation,
        generation_time: responseData.generation_time,
        from_cache: responseData.from_cache,
      };

      console.log("Setting article data:", articleData);
      setArticle(articleData);
      setLoading(false); // Important: Set loading to false after successful article processing
    } else {
      console.error("Invalid article data received:", responseData);
      setError("Invalid article data received");
      setLoading(false);
    }
  };

  return {
    loading,
    error,
    article,
    requestArticle,
    setArticle,
    setError,
  };
};

export default useArticleRequest;
