import React from "react";
import jsPDF from "jspdf";
import "jspdf-autotable";

const ArticlePDFExporter = ({ article }) => {
  const handleExportPDF = () => {
    if (!article) return;

    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const pageWidth = doc.internal.pageSize.width;
    const pageHeight = doc.internal.pageSize.height;

    // -------- COVER HEADER --------
    doc.setFont("times", "bold");
    doc.setFontSize(20);

    // Wrap headline
    const headline = article.headline || "Generated News Article";
    const headlineLines = doc.splitTextToSize(headline, 500);
    doc.text(headlineLines, pageWidth / 2, 60, { align: "center" });

    let y = 60 + headlineLines.length * 22;

    doc.setFont("times", "italic");
    doc.setFontSize(12);
    doc.text(`Generated on: ${new Date().toLocaleString()}`, pageWidth / 2, y, {
      align: "center",
    });

    // Divider line
    y += 20;
    doc.setDrawColor(0);
    doc.setLineWidth(0.5);
    doc.line(40, y, pageWidth - 40, y);

    y += 25;

    // -------- UTILITY FOR SECTIONS --------
    const addSection = (title, content, feedback) => {
      if (!content) return;

      doc.setFont("times", "bold");
      doc.setFontSize(14);

      // Page break check
      if (y > pageHeight - 120) {
        doc.addPage();
        y = 60;
      }

      doc.text(title, 40, y);
      y += 20;

      doc.setFont("times", "normal");
      doc.setFontSize(12);

      const splitContent = doc.splitTextToSize(content, 500);

      splitContent.forEach((line) => {
        if (y > pageHeight - 80) {
          doc.addPage();
          y = 60;
        }
        doc.text(line, 40, y, { maxWidth: 500, align: "justify" });
        y += 16;
      });

      if (feedback) {
        doc.setFont("times", "italic");
        doc.setTextColor(120);
        const fbText = `Editor's Note: ${feedback}`;
        const fbLines = doc.splitTextToSize(fbText, 480);

        fbLines.forEach((line) => {
          if (y > pageHeight - 80) {
            doc.addPage();
            y = 60;
          }
          doc.text(line, 60, y, { maxWidth: 480, align: "justify" });
          y += 16;
        });

        doc.setTextColor(0);
      }

      y += 15;
      doc.setDrawColor(200);
      doc.line(40, y, pageWidth - 40, y);
      y += 20;
    };

    // -------- MAIN CONTENT --------
    addSection(
      "Project Details",
      article.project_details,
      article.feedback_applied?.project_details
    );
    addSection(
      "Participants",
      article.participants,
      article.feedback_applied?.participants
    );
    addSection("Lots", article.lots, article.feedback_applied?.lots);
    addSection(
      "Organizations",
      article.organizations,
      article.feedback_applied?.organizations
    );

    // -------- FOOTER (Page Numbers) --------
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(10);
      doc.setFont("times", "italic");
      doc.text(`Page ${i} of ${pageCount}`, pageWidth / 2, pageHeight - 30, {
        align: "center",
      });
    }

    doc.save("news_article.pdf");
  };

  return (
    <button className="feedback-btn" onClick={handleExportPDF}>
      {/* <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        style={{ marginRight: "8px" }}
      >
        <path
          d="M12 3v18m0 0l-6-6m6 6l6-6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg> */}
      Export as PDF
    </button>
  );
};

export default ArticlePDFExporter;
