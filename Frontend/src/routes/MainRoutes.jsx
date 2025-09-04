import { Routes, Route } from "react-router-dom";
import ArticleRequestPage from "../pages/ArticleRequestPage";
import ArticleHistoryPage from "../pages/ArticleHistoryPage";
export default function MainRoutes() {
  return (
    <Routes>
      <Route path="/" element={<ArticleRequestPage />} />
      <Route path="/history" element={<ArticleHistoryPage />} />
    </Routes>
  );
}
