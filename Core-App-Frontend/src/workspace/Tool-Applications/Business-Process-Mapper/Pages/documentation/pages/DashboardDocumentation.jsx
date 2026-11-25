import React from "react";
import { FaInfoCircle, FaDesktop, FaThLarge, FaChartLine, FaTable, FaBell } from "react-icons/fa";
import { DocumentationCard, DocList, DocTable, Figure, InfoPanel } from "../components/DocComponents";
import "../../../Styles/documentation.css";

export default function DashboardDocumentation() {
  return (
    <div className="bm-doc-page">
      <DocumentationCard title="Overview" icon={<FaInfoCircle />}>
        <p>
          The Dashboard is the home page of Business Map Process. It summarises the files <strong>you</strong> have
          uploaded — how many there are, what state they are in, and when they were processed. The numbers refresh
          automatically every 5 seconds, so a job you just started appears without reloading the page.
        </p>
      </DocumentationCard>

      <DocumentationCard title="Page Layout" icon={<FaDesktop />}>
        <p>The page is arranged in three rows below the header:</p>
        <DocList items={[
          <><strong>Row 1 — Statistic cards:</strong> six cards in a single row.</>,
          <><strong>Row 2 — Charts:</strong> Uploads Over Time, Processing Status Distribution and Daily Activity side by side.</>,
          <><strong>Row 3 — Recent Files:</strong> a full-width table below the charts.</>,
        ]} />
        <Figure caption="Illustration of the Dashboard layout (not a live screenshot).">
          <div className="bm-fig-bar">
            <span className="bm-fig-tab-active">Dashboard</span>
            <span className="bm-fig-dots"><span /><span /><span /></span>
          </div>
          <div className="bm-fig-row six">
            {["Total Uploaded", "Processing", "Completed", "Cancelled", "Failed", "Success Rate"].map((l) => <div key={l} className="bm-fig-box">{l}</div>)}
          </div>
          <div className="bm-fig-row three">
            {["Uploads Over Time", "Status Distribution", "Daily Activity"].map((l) => <div key={l} className="bm-fig-box tall">{l}</div>)}
          </div>
          <div className="bm-fig-box wide">Recent Files — search box, sortable table, pagination</div>
        </Figure>
      </DocumentationCard>

      <DocumentationCard title="Statistic Cards" icon={<FaThLarge />}>
        <DocTable
          columns={["Card", "What it shows"]}
          rows={[
            ["Total Uploaded", "Every file you have uploaded for processing."],
            ["Processing", "Jobs that are queued, running, or waiting for your answer to the “No Audio Detected” question."],
            ["Completed", "Jobs that finished and produced their documents (including jobs that finished with partial results)."],
            ["Cancelled", "Jobs that were cancelled — by you with Cancel Processing, by leaving the page, or by logging out while a job was running."],
            ["Failed", "Jobs that stopped because of an error."],
            ["Success Rate", "Completed jobs as a percentage of completed + failed jobs. Cancelled jobs are not counted."],
          ]}
        />
      </DocumentationCard>

      <DocumentationCard title="Charts" icon={<FaChartLine />}>
        <DocTable
          columns={["Chart", "What it shows"]}
          rows={[
            ["Uploads Over Time", "A line chart of how many files you uploaded on each of the last 14 days (days with no uploads show 0)."],
            ["Processing Status Distribution", "A bar chart with one bar each for Uploaded (total), Processing, Completed, Cancelled and Failed."],
            ["Daily Activity", "An area chart by time of day in two-hour blocks: uploads (when files arrived) versus processed (when jobs finished)."],
          ]}
        />
        <InfoPanel>Hover over a chart to see the exact value for that point.</InfoPanel>
      </DocumentationCard>

      <DocumentationCard title="Recent Files" icon={<FaTable />}>
        <p>The table lists your uploads, newest first, with these columns:</p>
        <DocList items={[
          <><strong>File</strong> — the original video file name.</>,
          <><strong>Uploader</strong> — the username entered under “Provide user details”, or “anonymous”.</>,
          <><strong>Status</strong> — Uploaded, Processing, Completed, Failed or Cancelled.</>,
          <><strong>Size</strong> and <strong>Duration</strong> — file size, and how long processing took.</>,
          <><strong>Uploaded</strong> — the upload date.</>,
        ]} />
        <p>
          Click a column heading to sort by it (click again to reverse). Use the search box to filter by file name,
          uploader or status. The table shows 8 rows per page; use the arrows under it to move between pages.
        </p>
      </DocumentationCard>

      <DocumentationCard title="Header: Notifications, Home and Profile" icon={<FaBell />}>
        <DocTable
          columns={["Button", "What it does"]}
          rows={[
            ["Bell (Notifications)", "Opens your Business Map notifications: upload started, processing completed, processing failed and processing cancelled. Filter by Day, Week, Month or All; delete one notification or all shown. Deleting only hides the notification — your files and statistics are not affected."],
            ["Home", "Takes you to the Business Map Dashboard."],
            ["Profile (your initial)", "Shows your name, email, role, organization and your upload statistics, with a Logout button."],
          ]}
        />
        <p>The page name on the left of the header and these three buttons stay in place on both pages. Use the sidebar to switch between Dashboard and Business Flow.</p>
      </DocumentationCard>
    </div>
  );
}
