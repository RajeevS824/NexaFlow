/**
 * workspace/pages/ProductSettings.jsx
 * ------------------------------------------------------------
 * Reached from the sidebar's Settings dropdown (any product name
 * -> opens THIS in a new tab, not the public marketing product
 * page). Visible to every signed-in user, admin or not — this is
 * per-product workspace configuration, not org-wide user/role
 * management (that stays under Manage, admin-only).
 *
 * The Settings dropdown lists every product, purchased or not.
 * Anyone can open this page for any product, but changing a
 * setting on a product this organization hasn't purchased pops an
 * "Access Restricted" message instead of applying the change -
 * only purchased products can actually be configured here.
 *
 * Frontend-only demo: preferences are kept in local component
 * state, no backend to persist them to yet.
 * ------------------------------------------------------------
 */

import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { FaCog, FaBell, FaPlug, FaKey, FaLock, FaTimes } from "react-icons/fa";
import Header from "../components/WorkspaceHeader";
import { PRODUCTS } from "../../data/products.js";
import "../styles/manage.css";

export default function ProductSettings() {
  const { slug } = useParams();
  const product = PRODUCTS.find((p) => p.slug === slug);

  const [emailAlerts, setEmailAlerts] = useState(true);
  const [runFailureAlerts, setRunFailureAlerts] = useState(true);
  const [weeklyDigest, setWeeklyDigest] = useState(false);
  const [apiKey, setApiKey] = useState("•••• •••• •••• 8f2c");
  const [saved, setSaved] = useState(false);
  const [showRestricted, setShowRestricted] = useState(false);

  if (!product) {
    return (
      <>
        <Header title="Settings" description="Product not found." />
        <main className="main-content">
          <div className="manage-page">
            <div className="manage-card">
              <p className="manage-hint">We couldn't find settings for "{slug}".</p>
            </div>
          </div>
        </main>
      </>
    );
  }

  const canEdit = product.purchased;

  // Every control funnels through this before actually changing anything:
  // purchased -> apply the change normally; not purchased -> block it and
  // show the "Access Restricted" popup instead.
  function guarded(applyChange) {
    if (!canEdit) {
      setShowRestricted(true);
      return;
    }
    applyChange();
  }

  function handleSave(e) {
    e.preventDefault();
    guarded(() => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    });
  }

  return (
    <>
      <Header title={`${product.name} Settings`} description={product.tagline} />
      <main className="main-content">
        <div className="manage-page" style={{ maxWidth: 760 }}>
          <div className="manage-card">
            <h2 className="manage-card-heading">
              <span className="rg-icon-chip">
                <FaCog size={16} />
              </span>
              {product.name}
              {!canEdit && (
                <span className="status-pill inactive" style={{ marginLeft: 10 }}>
                  <FaLock size={10} style={{ marginRight: 5, verticalAlign: -1 }} />
                  Not purchased
                </span>
              )}
            </h2>
            <p className="manage-card-subheading">
              {canEdit
                ? `Configure how ${product.name} behaves for you.`
                : `Your organization hasn't purchased ${product.name} yet. You can look around, but changes are disabled.`}
            </p>

            {saved && <div className="manage-success-banner">Settings saved.</div>}

            <form onSubmit={handleSave}>
              <div className="manage-field">
                <label>
                  <FaBell size={12} style={{ marginRight: 6, verticalAlign: -1 }} />
                  Notifications
                </label>
                <div className="rg-radio-group" style={{ flexDirection: "column", alignItems: "flex-start", gap: 10 }}>
                  <label className="rg-radio">
                    <input
                      type="checkbox"
                      checked={emailAlerts}
                      onChange={(e) => guarded(() => setEmailAlerts(e.target.checked))}
                    />
                    Email me when a run completes
                  </label>
                  <label className="rg-radio">
                    <input
                      type="checkbox"
                      checked={runFailureAlerts}
                      onChange={(e) => guarded(() => setRunFailureAlerts(e.target.checked))}
                    />
                    Alert me immediately on failures
                  </label>
                  <label className="rg-radio">
                    <input
                      type="checkbox"
                      checked={weeklyDigest}
                      onChange={(e) => guarded(() => setWeeklyDigest(e.target.checked))}
                    />
                    Send a weekly summary digest
                  </label>
                </div>
              </div>

              <div className="manage-field">
                <label>
                  <FaPlug size={12} style={{ marginRight: 6, verticalAlign: -1 }} />
                  Connected accounts
                </label>
                <p className="manage-hint" style={{ marginTop: 0 }}>
                  No accounts connected yet.
                </p>
              </div>

              <div className="manage-field">
                <label htmlFor="ps-api-key">
                  <FaKey size={12} style={{ marginRight: 6, verticalAlign: -1 }} />
                  API Key
                </label>
                <input
                  id="ps-api-key"
                  className="manage-input"
                  type="text"
                  value={apiKey}
                  onFocus={(e) => {
                    if (!canEdit) {
                      e.target.blur();
                      setShowRestricted(true);
                    }
                  }}
                  onChange={(e) => guarded(() => setApiKey(e.target.value))}
                />
              </div>

              <div className="rg-modal-actions" style={{ justifyContent: "flex-start" }}>
                <button type="submit" className="btn-primary-dp">
                  Save Settings
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>

      {/* Access Restricted popup - shown whenever someone tries to change a
          setting on a product this organization hasn't purchased. */}
      {showRestricted && (
        <div className="rg-modal-overlay" onClick={() => setShowRestricted(false)}>
          <div className="rg-modal rg-modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="rg-modal-header">
              <span className="rg-icon-chip">
                <FaLock size={16} />
              </span>
              <h2>Access Restricted</h2>
              <button type="button" className="rg-modal-close" onClick={() => setShowRestricted(false)} aria-label="Close">
                <FaTimes size={14} />
              </button>
            </div>
            <p className="manage-card-subheading" style={{ marginBottom: 20 }}>
              You don't have access to change settings for {product.name}. Only purchased products can have
              their settings changed.
            </p>
            <div className="rg-modal-actions">
              <button type="button" className="btn-primary-dp" onClick={() => setShowRestricted(false)}>
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
