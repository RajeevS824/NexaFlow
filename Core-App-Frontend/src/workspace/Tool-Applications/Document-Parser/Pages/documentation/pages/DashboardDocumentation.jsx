import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function DashboardDocumentation() {
  const workflowSteps = [
    "Dashboard",
    "Create Model",
    "Configure Fields",
    "Process Document",
    "Validate Results",
    "View History"
  ];

  return (
    <div className="doc-page">
      {/* Overview */}
      <DocumentationCard 
        title="Overview" 
        icon={<FaInfoCircle />}
      >
        <p>
          The Document Parser Dashboard is the starting point of the Document Parser module. It gives you a quick
          summary of all your process models, the documents that have been processed, and the current status of
          those documents. It also provides shortcuts so you can move to the most common tasks in just one click.
        </p>
      </DocumentationCard>

      {/* Purpose */}
      <DocumentationCard 
        title="Purpose" 
        icon={<FaBullseye />}
      >
        <p>
          The Dashboard is designed to:
        </p>
        <ul className="doc-list">
          <li>Show important numbers at a glance, such as how many models you have and how many documents were processed.</li>
          <li>Show charts that help you understand processing trends over time.</li>
          <li>Give you quick access to create a new model, process a document, or view history.</li>
          <li>Show how many documents are completed, still processing, waiting, or failed.</li>
        </ul>
      </DocumentationCard>

      {/* Page Purpose & Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Top Section:</strong> The page heading "Extraction Models Dashboard" with notification, home, and profile icons.</li>
          <li><strong>Statistics Row:</strong> Five cards that show key numbers about your models and documents.</li>
          <li><strong>Charts Section:</strong> Two charts — one showing documents processed over time and one showing the status of those documents.</li>
          <li><strong>Bottom Section:</strong> A "Quick Actions" area and a chart showing the distribution of document types.</li>
          <li><strong>Left Sidebar:</strong> The Document Parser menu for moving between pages.</li>
        </ul>
      </DocumentationCard>

      {/* Stat Cards */}
      <DocumentationCard 
        title="Statistics Cards" 
        icon={<FaDesktop />}
      >
        <p>
          The Dashboard shows five statistic cards. Each card has an icon, a label, and a number.
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Card</th>
              <th>What It Shows</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Total Models</td>
              <td>The number of process models you have created.</td>
            </tr>
            <tr>
              <td>Documents Processed</td>
              <td>The total number of documents that have been processed using your models.</td>
            </tr>
            <tr>
              <td>Successfully Extracted</td>
              <td>The number of documents where the information was extracted successfully.</td>
            </tr>
            <tr>
              <td>Pending Validation</td>
              <td>The number of documents that are still waiting to be processed or need manual review.</td>
            </tr>
            <tr>
              <td>STP</td>
              <td>A percentage showing how many documents were completed automatically without needing manual help.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Charts */}
      <DocumentationCard 
        title="Charts" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          Two charts appear in the middle of the Dashboard:
        </p>
        <ul className="doc-list">
          <li><strong>Documents Processed:</strong> A bar chart that shows how many documents were processed on each day (or month when "All Time" is selected).</li>
          <li><strong>Status Distribution:</strong> A circular chart (donut) that shows the share of documents that are Completed, Processing, Pending, or Failed.</li>
          <li><strong>Time Filter:</strong> Above the first chart you can choose <em>Today</em>, <em>Last 7 Days</em>, <em>Last 30 Days</em>, or <em>All Time</em> to change the dates shown on the chart.</li>
        </ul>
      </DocumentationCard>

      {/* Document Distribution */}
      <DocumentationCard 
        title="Document Distribution" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The <strong>Document Distribution</strong> section shows a circular chart and a legend that break down the
          processed documents by their type (for example, Invoice, Receipt, Contract, or Other). The center of the
          chart shows the total number of documents, and each colour in the legend represents one document type with
          its percentage of the total.
        </p>
      </DocumentationCard>

      {/* Quick Actions */}
      <DocumentationCard 
        title="Quick Actions" 
        icon={<FaMousePointer />}
      >
        <p>
          The Quick Actions area gives you one-click shortcuts:
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Action Card</th>
              <th>What It Does</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Create Model</td>
              <td>Takes you to the <strong>Create Process Model</strong> page where you can set up a new model.</td>
            </tr>
            <tr>
              <td>Process Document</td>
              <td>Takes you to the <strong>Document Process Model</strong> page where you can choose a model and start processing a document. This card is available only when you have at least one model.</td>
            </tr>
            <tr>
              <td>History</td>
              <td>Takes you to the <strong>History Extraction Model</strong> page where you can see all processed documents. This card is available only when you have at least one model.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Header Icons */}
      <DocumentationCard 
        title="Header Icons" 
        icon={<FaHandPointer />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Icon</th>
              <th>What It Does</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Notification Bell</td>
              <td>Shows notifications about your processing activities.</td>
            </tr>
            <tr>
              <td>Home</td>
              <td>Takes you back to your main workspace home page.</td>
            </tr>
            <tr>
              <td>Profile Avatar</td>
              <td>Shows your profile letter. This represents your logged-in user.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

    
      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Start at the Dashboard:</strong> This is where you land when you open the Document Parser module.</li>
          <li><strong>Look at your numbers:</strong> Check the statistics cards to understand how many models and documents you have.</li>
          <li><strong>Review the charts:</strong> Use the time filters to see your processing activity for the day, week, month, or all time.</li>
          <li><strong>Create a model:</strong> Click <em>Create Model</em> to start building a new process model.</li>
          <li><strong>Process a document:</strong> Click <em>Process Document</em> after you have at least one model.</li>
          <li><strong>View history:</strong> Click <em>History</em> to see the documents you have already processed.</li>
        </ul>
      </DocumentationCard>

      {/* Validation Rules */}
      <DocumentationCard 
        title="Validation Rules" 
        icon={<FaCheckCircle />}
      >
        <ul className="doc-list">
          <li>You must be signed in to view the Dashboard.</li>
          <li>The Document Parser product must be enabled for your account.</li>
          <li>Statistic cards and charts show "No data available yet" when there are no models or processed documents.</li>
          <li>The <em>Process Document</em> and <em>History</em> shortcuts are unavailable until you create at least one model.</li>
          <li>If you try to use these shortcuts without a model, a message tells you to create an extraction model first.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> The Dashboard loads automatically when you open the Document Parser module.
            All numbers and charts are calculated using your saved models and processing history.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> Use the chart time filters (<em>Today</em>, <em>Last 7 Days</em>, <em>Last 30 Days</em>,
            <em>All Time</em>) to compare your document processing activity over different periods.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default DashboardDocumentation;