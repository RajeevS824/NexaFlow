import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../../../components/WorkspaceHeader";
import {
  FaCogs,
  FaPlusCircle,
  FaHistory,
  FaLayerGroup,
  FaFileAlt,
  FaCheckCircle,
  FaClock,
  FaPercent,
  FaBell,
  FaArrowUp,
  FaHome,
} from "react-icons/fa";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import { API_BASE_URL, authFetch } from "../../../config/api";
import { useBasePath } from "../../../utils/useBasePath";
import { useAuth } from "../../../../context/AuthContext.jsx";
import { useDocumentParserHistorySocket } from "../../../hooks/useDocumentParserHistorySocket";
import ProfilePopup from "../Components/ProfilePopup";
import NotificationPopup from "../Components/NotificationPopup";
import "../Styles/commonstyle.css";
import "../Styles/documentParser.css";

const TIME_FILTERS = [
  { key: "today", label: "Today" },
  { key: "7days", label: "Last 7 Days" },
  { key: "30days", label: "Last 30 Days" },
  { key: "all", label: "All Time" },
];

export default function DocumentParser() {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;

  const [stats, setStats] = useState({
    totalModels: 0,
    totalHistory: 0,
    completed: 0,
    processing: 0,
    pending: 0,
    failed: 0,
    stp: 0,
  });
  const [history, setHistory] = useState([]);
  const [timeFilter, setTimeFilter] = useState("7days");
  const [showProfilePopup, setShowProfilePopup] = useState(false);
  const [showNotificationPopup, setShowNotificationPopup] = useState(false);
  const { user, logout } = useAuth();

  // First letter of the logged-in user's name (fetched from the DB via
  // /api/auth/me in AuthContext) shown on the profile avatar.
  const userInitial = (user?.fullName || user?.email || "U").trim().charAt(0).toUpperCase();

  const loadStats = useCallback(async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/document/models`);
      const modelData = await response.json();
      const models = Array.isArray(modelData?.models) ? modelData.models : [];

      const historyResponse = await authFetch(`${API_BASE_URL}/document/history`);
      const historyData = await historyResponse.json();
      const historyArr = Array.isArray(historyData?.history)
        ? historyData.history
        : [];

      const completed = historyArr.filter((h) => {
        const s = (h.status || "").toLowerCase().trim();
        return ["completed", "success", "done", "extracted"].includes(s);
      }).length;

      const processing = historyArr.filter((h) => {
        const s = (h.status || "").toLowerCase().trim();
        return ["processing", "running", "in progress"].includes(s);
      }).length;

      const pending = historyArr.filter((h) => {
        const s = (h.status || "").toLowerCase().trim();
        return ["pending", "queued"].includes(s);
      }).length;

      const failed = historyArr.filter((h) => {
        const s = (h.status || "").toLowerCase().trim();
        return ["failed", "cancelled"].includes(s);
      }).length;

      // STP percentage: (total STP / total jobs) * 100
      const autoProcessed = historyArr.filter((h) => {
        const stpValue = h.stp ?? h.stp_completed;
        return stpValue === true || stpValue === 1 || stpValue === "1";
      }).length;
      const totalJobs = historyArr.length;
      const stp = totalJobs > 0
        ? ((autoProcessed / totalJobs) * 100).toFixed(0)
        : 0;

      setStats({
        totalModels: models.length,
        totalHistory: historyArr.length,
        completed,
        processing,
        pending,
        failed,
        stp,
      });
      setHistory(historyArr);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useDocumentParserHistorySocket(undefined, () => {
    loadStats();
  });

  useEffect(() => {
    const handleFocus = () => loadStats();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [loadStats]);

  const extractISODate = (h) => {
    const raw = h.createddate || h.processdate || "";
    if (!raw) return null;
    const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return iso[0];
    const dmy = raw.match(/^(\d{2})-(\d{2})-(\d{4})/);
    if (dmy) return `${dmy[3]}-${dmy[2]}-${dmy[1]}`;
    const dmy2 = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
    if (dmy2) return `${dmy2[3]}-${dmy2[2]}-${dmy2[1]}`;
    return null;
  };

  const getISTTodayStr = () => {
    const now = new Date();
    const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
    const istDate = new Date(utcMs + 5.5 * 3600000);
    return istDate.toISOString().split("T")[0];
  };

  const getBarChartData = () => {
    const todayStr = getISTTodayStr();
    const todayMs = new Date(todayStr + "T00:00:00Z").getTime();
    const msPerDay = 86400000;

    let numDays;
    if (timeFilter === "today") numDays = 1;
    else if (timeFilter === "7days") numDays = 7;
    else if (timeFilter === "30days") numDays = 30;
    else numDays = 0;

    if (timeFilter === "all") {
      const monthMap = {};
      history.forEach((h) => {
        const isoDate = extractISODate(h);
        if (isoDate) {
          const monthKey = isoDate.slice(0, 7);
          monthMap[monthKey] = (monthMap[monthKey] || 0) + 1;
        }
      });
      const sortedMonths = Object.keys(monthMap).sort();
      return sortedMonths.map((m) => {
        const [y, mo] = m.split("-");
        const d = new Date(parseInt(y), parseInt(mo) - 1, 1);
        return {
          name: d.toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
          date: d.toLocaleDateString("en-US", { month: "long", year: "numeric" }),
          day: "-",
          documents: monthMap[m],
        };
      });
    }

    const targetDates = [];
    for (let offset = numDays - 1; offset >= 0; offset--) {
      const d = new Date(todayMs - offset * msPerDay);
      targetDates.push(d.toISOString().split("T")[0]);
    }

    const dateCount = {};
    targetDates.forEach((dt) => { dateCount[dt] = 0; });
    history.forEach((h) => {
      const entryDate = extractISODate(h);
      if (entryDate && dateCount.hasOwnProperty(entryDate)) {
        dateCount[entryDate]++;
      }
    });

    return targetDates.map((dt) => {
      const d = new Date(dt + "T00:00:00Z");
      let label;
      if (timeFilter === "30days") {
        label = d.toLocaleDateString("en-US", { day: "2-digit", month: "short", timeZone: "UTC" });
      } else {
        label = d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
      }
      return {
        name: label,
        date: d.toLocaleDateString("en-US", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }),
        day: d.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" }),
        documents: dateCount[dt],
      };
    });
  };

  const getStatusData = () => [
    { name: "Completed", value: stats.completed, color: "#10B981" },
    { name: "Processing", value: stats.processing, color: "#2563EB" },
    { name: "Pending", value: stats.pending, color: "#F59E0B" },
    { name: "Failed", value: stats.failed, color: "#EF4444" },
  ];

  const getDocTypeData = () => {
    const typeCount = {};
    history.forEach((h) => {
      const dt = (h.documenttype || "Unknown").trim();
      typeCount[dt] = (typeCount[dt] || 0) + 1;
    });
    const colors = ["#2563EB", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4"];
    return Object.entries(typeCount).map(([name, value], i) => ({
      name,
      value,
      color: colors[i % colors.length],
    }));
  };

  const barData = getBarChartData();
  const statusData = getStatusData();
  const statusTotal = statusData.reduce((sum, d) => sum + d.value, 0);
  const docTypeData = getDocTypeData();
  const docTypeTotal = docTypeData.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="dp-dashboard">
          <Header
            title="Extraction Models Dashboard"
            actions={
              <>
                <button
                  className="dp-notification-btn"
                  title="Notifications"
                  onClick={() => setShowNotificationPopup(true)}
                >
                  <FaBell />
                </button>
                <button
                  className="dp-home-btn"
                  title="Go to Home"
                  onClick={() => navigate(basePath)}
                >
                  <FaHome />
                </button>
                <button
                  type="button"
                  className="dp-profile-avatar"
                  title={user?.fullName || user?.email || "Profile"}
                  onClick={() => setShowProfilePopup(true)}
                >
                  {userInitial}
                </button>
              </>
            }
          />

          {showProfilePopup && (
            <ProfilePopup
              user={user}
              stats={stats}
              onClose={() => setShowProfilePopup(false)}
              onLogout={() => logout()}
            />
          )}
          {showNotificationPopup && (
            <NotificationPopup
              history={history}
              unread={0}
              userId={user?.id}
              onClose={() => setShowNotificationPopup(false)}
            />
          )}

          <main className="dp-main">
            <div className="dp-content-wrapper">
              <div className="dp-stats-row">
                <StatCard icon={<FaLayerGroup />} iconClass="dp-stat-icon-blue" label="Total Models" value={stats.totalModels} trendClass="dp-stat-trend-up" />
                <StatCard icon={<FaFileAlt />} iconClass="dp-stat-icon-green" label="Documents Processed" value={stats.totalHistory} trendClass="dp-stat-trend-neutral" />
                <StatCard icon={<FaCheckCircle />} iconClass="dp-stat-icon-purple" label="Successfully Extracted" value={stats.completed} trendClass="dp-stat-trend-up" />
                <StatCard icon={<FaClock />} iconClass="dp-stat-icon-amber" label="Pending Validation" value={stats.pending + stats.processing} trendClass={stats.pending + stats.processing > 0 ? "dp-stat-trend-down" : "dp-stat-trend-up"} />
                <StatCard icon={<FaPercent />} iconClass="dp-stat-icon-cyan" label="STP" value={`${stats.stp}%`} trendClass={Number(stats.stp) >= 80 ? "dp-stat-trend-up" : Number(stats.stp) >= 50 ? "dp-stat-trend-up" : "dp-stat-trend-down"} />
              </div>

              <div className="dp-charts-section">
                <div className="dp-chart-card">
                  <div className="dp-chart-header">
                    <span className="dp-chart-title">Documents Processed</span>
                    <div className="dp-chart-time-filters">
                      {TIME_FILTERS.map((f) => (
                        <button key={f.key} className={`dp-time-filter-btn ${timeFilter === f.key ? "active" : ""}`} onClick={() => setTimeFilter(f.key)}>
                          {f.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="dp-chart-body">
                    {history.length > 0 ? (
                      <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={barData} margin={{ top: 5, right: 5, left: -5, bottom: 2 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94A3B8" }} axisLine={false} tickLine={false} interval={timeFilter === "30days" ? 4 : 0} height={16} />
                          <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} axisLine={false} tickLine={false} allowDecimals={false} width={24} />
                          <Tooltip
                            formatter={(value) => [`${value}`, "Documents"]}
                            labelFormatter={(label, payload) => {
                              if (!payload || !payload.length) return label;
                              const data = payload[0].payload;
                              return (<>{`Date: ${data.date} | Day: ${data.day}`}</>);
                            }}
                            contentStyle={{ borderRadius: "8px", border: "1px solid #E2E8F0", fontSize: "12px" }}
                            cursor={{ fill: "rgba(37,99,235,0.06)" }}
                          />
                          <Bar dataKey="documents" radius={[3, 3, 0, 0]} maxBarSize={timeFilter === "30days" ? 14 : 20}>
                            {barData.map((entry, index) => (
                              <Cell key={index} fill={entry.documents > 0 ? "#2563EB" : "#E2E8F0"} fillOpacity={entry.documents > 0 ? 0.85 : 0.5} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="dp-empty-state">No data available yet</div>
                    )}
                  </div>
                </div>

                <div className="dp-chart-card">
                  <div className="dp-chart-header">
                    <span className="dp-chart-title">Status Distribution</span>
                  </div>
                  <div className="dp-chart-body">
                    {history.length > 0 ? (
                      <div className="dp-donut-section">
                        <div className="dp-donut-chart-wrap">
                          <ResponsiveContainer width="100%" height={180}>
                            <PieChart>
                              <Pie
                                data={statusData}
                                cx="50%"
                                cy="50%"
                                innerRadius={55}
                                outerRadius={75}
                                paddingAngle={3}
                                dataKey="value"
                                startAngle={90}
                                endAngle={-270}
                              >
                                {statusData.map((entry, index) => (<Cell key={index} fill={entry.color} />))}
                              </Pie>
                              <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #E2E8F0", fontSize: "12px" }} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>

                        <div className="dp-donut-legend">
                          {statusData.map((entry, i) => {
                            const pct = statusTotal > 0 ? Math.round((entry.value / statusTotal) * 100) : 0;
                            return (
                              <div className="dp-donut-legend-item" key={i}>
                                <div className="dp-donut-legend-row">
                                  <span className="dp-donut-legend-dot" style={{ background: entry.color }} />
                                  <span className="dp-donut-legend-name">{entry.name}</span>
                                  <span className="dp-donut-legend-pct">{pct}%</span>
                                </div>
                                <div className="dp-donut-legend-bar-track">
                                  <div
                                    className="dp-donut-legend-bar-fill"
                                    style={{ width: `${pct}%`, background: entry.color }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="dp-empty-state">No data available yet</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="dp-bottom-grid">
                <div className="dp-section-card">
                  <div className="dp-section-header">
                    <span className="dp-section-title">Quick Actions</span>
                  </div>
                  <div className="dp-quick-actions-stack">
                    <ActionHeroCard
                      icon={<FaPlusCircle />}
                      title="Create Model"
                      description="Train the AI on a custom document structure."
                      onClick={() => {
                        localStorage.removeItem("tempModel_selectModel");
                        localStorage.removeItem("tempModel_modelName");
                        localStorage.removeItem("tempModel_description");
                        localStorage.removeItem("tempModel_documentType");
                        localStorage.removeItem("tempModel_language");
                        localStorage.removeItem("draftExtractionFields");
                        localStorage.removeItem("modelName");
                        localStorage.removeItem("editModelId");
                        navigate(`${docBase}/create-process-model`);
                      }}
                    />

                    <div className="dp-actions-mini-grid">
                      <ActionMiniCard
                        icon={<FaCogs />}
                        accentClass="dp-accent-blue"
                        title="Process Document"
                        description="Upload document for extraction"
                        disabled={stats.totalModels === 0}
                        onClick={() => {
                          if (stats.totalModels === 0) { alert("Please create an extraction model first."); return; }
                          navigate(`${docBase}/document-process-model`);
                        }}
                      />
                      <ActionMiniCard
                        icon={<FaHistory />}
                        accentClass="dp-accent-green"
                        title="History"
                        description="View all processed documents"
                        disabled={stats.totalModels === 0}
                        onClick={() => {
                          if (stats.totalModels === 0) { alert("Please create an extraction model first."); return; }
                          localStorage.removeItem("historyModelId");
                          navigate(`${docBase}/history-process-model`);
                        }}
                      />
                    </div>
                  </div>
                </div>

                <div className="dp-section-card">
                  <div className="dp-section-header">
                    <div>
                      <span className="dp-section-title">Document Distribution</span>
                      <div className="dp-section-subtitle">Volume by classification type</div>
                    </div>
                  </div>
                  <div className="dp-chart-body">
                    {docTypeData.length > 0 ? (
                      <div className="dp-donut-section">
                        <div className="dp-donut-chart-wrap">
                          <ResponsiveContainer width="100%" height={180}>
                            <PieChart>
                              <Pie
                                data={docTypeData}
                                cx="50%"
                                cy="50%"
                                innerRadius={55}
                                outerRadius={75}
                                paddingAngle={3}
                                dataKey="value"
                                startAngle={90}
                                endAngle={-270}
                              >
                                {docTypeData.map((entry, index) => (<Cell key={index} fill={entry.color} />))}
                              </Pie>
                              <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #E2E8F0", fontSize: "12px" }} />
                            </PieChart>
                          </ResponsiveContainer>
                          <div className="dp-donut-center">
                            <div className="dp-donut-center-value">
                              {docTypeTotal >= 1000 ? `${(docTypeTotal / 1000).toFixed(1)}k` : docTypeTotal}
                            </div>
                            <div className="dp-donut-center-label">TOTAL</div>
                          </div>
                        </div>

                        <div className="dp-donut-legend">
                          {docTypeData.map((entry, i) => {
                            const pct = docTypeTotal > 0 ? Math.round((entry.value / docTypeTotal) * 100) : 0;
                            return (
                              <div className="dp-donut-legend-item" key={i}>
                                <div className="dp-donut-legend-row">
                                  <span className="dp-donut-legend-dot" style={{ background: entry.color }} />
                                  <span className="dp-donut-legend-name">{entry.name}</span>
                                  <span className="dp-donut-legend-pct">{pct}%</span>
                                </div>
                                <div className="dp-donut-legend-bar-track">
                                  <div
                                    className="dp-donut-legend-bar-fill"
                                    style={{ width: `${pct}%`, background: entry.color }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="dp-empty-state">
                        No document type data available
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </main>
    </div>
  );
}

function StatCard({ icon, iconClass, label, value, trend, trendClass }) {
  return (
    <div className="dp-stat-card">
      <div className={`dp-stat-icon-wrap ${iconClass}`}>{icon}</div>
      <div className="dp-stat-info">
        <div className="dp-stat-label">{label}</div>
        <div className="dp-stat-value">{value}</div>
        {trend && (
          <div className={`dp-stat-trend ${trendClass}`}>
            <FaArrowUp />
            {trend}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionHeroCard({ icon, title, description, onClick }) {
  return (
    <div className="dp-action-hero" onClick={onClick}>
      <div className="dp-action-hero-text">
        <div className="dp-action-hero-title">{title}</div>
        <div className="dp-action-hero-desc">{description}</div>
      </div>
      <div className="dp-action-hero-icon">{icon}</div>
    </div>
  );
}

function ActionMiniCard({ icon, accentClass, title, description, disabled, onClick }) {
  return (
    <div
      className={`dp-action-mini ${accentClass} ${disabled ? "disabled" : ""}`}
      onClick={!disabled ? onClick : undefined}
    >
      <div className="dp-action-mini-icon">{icon}</div>
      <div className="dp-action-mini-title">{title}</div>
      <div className="dp-action-mini-desc">{description}</div>
    </div>
  );
}