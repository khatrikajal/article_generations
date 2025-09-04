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

      const response = await api.post("generate/", payload);

      if (response.data.success) {
        const responseData = response.data.data;

        if (responseData.async && responseData.task_id) {
          // Handle async processing - poll for results
          await pollTaskStatus(responseData.task_id);
        } else {
          // Handle synchronous response
          handleArticleResponse(responseData);
        }
      } else {
        setError(response.data.message || "Article generation failed");
      }
    } catch (err) {
      console.error("Article request error:", err);
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          err.message ||
          "Failed to generate article"
      );
    } finally {
      setLoading(false);
    }
  };

  /**
   * Poll task status for async requests
   */
  const pollTaskStatus = async (taskId, maxAttempts = 30, interval = 2000) => {
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await api.get(`tasks/${taskId}/status/`);

        if (response.data.success) {
          const taskData = response.data.data;

          if (taskData.status === "completed") {
            // Task completed successfully
            if (taskData.result && taskData.result.success) {
              handleArticleResponse(taskData.result);
              return;
            } else {
              setError(taskData.result?.error || "Task completed with errors");
              return;
            }
          } else if (taskData.status === "failed") {
            // Task failed
            setError(taskData.error || "Task execution failed");
            return;
          } else if (taskData.status === "processing") {
            // Still processing, continue polling
            attempts++;
            if (attempts < maxAttempts) {
              setTimeout(poll, interval);
            } else {
              setError("Task timed out - please try again");
            }
          }
        } else {
          setError("Failed to check task status");
        }
      } catch (err) {
        console.error("Task polling error:", err);
        setError("Failed to check task status");
      }
    };

    // Start polling
    poll();
  };

  /**
   * Handle successful article response
   */
  const handleArticleResponse = (responseData) => {
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

      setArticle(articleData);
    } else {
      setError("Invalid article data received");
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
