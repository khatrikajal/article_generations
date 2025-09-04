import React from "react";
import { useArticleHistory } from "../hooks/useArticleHistory";
import "./ArticleHistoryPage.css";

const ArticleHistoryPage = () => {
  const { history, loading, error } = useArticleHistory();

  if (loading) return <p className="loading">Loading history...</p>;
  if (error) return <p className="error">⚠️ {error}</p>;

  return (
    <div className="history-page">
      <h2>📜 Article History</h2>
      <table className="history-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Article Headline</th>
            <th>URL</th>
            <th>Changes</th>
            <th>Created At</th>
          </tr>
        </thead>
        <tbody>
          {Array.isArray(history) && history.length > 0 ? (
            history.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>
                  <a
                    href={`/article/${item.article?.id ?? ""}`}
                    className="headline-link"
                  >
                    {item.article?.headline ?? "Untitled"}
                  </a>
                </td>
                <td>
                  {item.article?.url ? (
                    <a
                      href={item.article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="url-link"
                    >
                      {item.article.url.length > 40
                        ? item.article.url.substring(0, 40) + "..."
                        : item.article.url}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  {item.changes && Object.keys(item.changes).length > 0
                    ? Object.entries(item.changes).map(([key, value]) => (
                        <div key={key}>
                          <strong>{key}</strong>: {value}
                        </div>
                      ))
                    : "—"}
                </td>
                <td>
                  {item.created_at
                    ? new Date(item.created_at).toLocaleString("en-GB", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })
                    : "—"}
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="5" className="no-data">
                No history found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default ArticleHistoryPage;
