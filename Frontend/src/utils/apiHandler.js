import axios from "axios";

// Create axios instance
const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/", // Correct base URL
  timeout: 30000, // Increased timeout for long-running tasks
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`, {
      data: config.data,
      params: config.params,
    });
    return config;
  },
  (error) => {
    console.error("API Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor for handling common errors
api.interceptors.response.use(
  (response) => {
    console.log(
      `API Response: ${response.config.method?.toUpperCase()} ${
        response.config.url
      }`,
      {
        status: response.status,
        data: response.data,
      }
    );
    return response;
  },
  (error) => {
    console.error("API Response Error:", {
      url: error.config?.url,
      method: error.config?.method?.toUpperCase(),
      status: error.response?.status,
      data: error.response?.data,
      message: error.message,
    });

    // Handle common error cases
    if (error.response?.status === 404) {
      console.error("API endpoint not found - check your URL paths");
    } else if (error.response?.status === 500) {
      console.error("Server error - check Django logs");
    } else if (error.code === "ECONNREFUSED") {
      console.error("Connection refused - is Django server running?");
    }

    return Promise.reject(error);
  }
);

export default api;
