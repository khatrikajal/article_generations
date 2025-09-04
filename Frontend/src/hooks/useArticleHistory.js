import { useState, useEffect } from "react";
import api from "../utils/apiHandler";

export const useArticleHistory = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await api.get("history/");

        // ✅ DRF view always returns a list
        const data = Array.isArray(response.data) ? response.data : [];
        console.log("Fetched history:", data);
        setHistory(data);
      } catch (err) {
        console.error("Error fetching history:", err);
        setError(err.message || "Failed to fetch history");
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  return { history, loading, error };
};
