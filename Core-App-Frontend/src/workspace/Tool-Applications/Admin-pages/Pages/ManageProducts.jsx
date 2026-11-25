/**
 * workspace/pages/ManageProducts.jsx
 * ------------------------------------------------------------
 * Admin-only "Products" page (Manage > Products).
 *
 * Lists this organization's *purchased* products (read-only as
 * far as the marketing catalog goes - an admin here can't add,
 * remove, rename, or otherwise touch a product's marketing-facing
 * data). What the admin CAN do is flip a purchased product's
 * Active/Deactivated switch, which controls whether their own
 * users/employees currently see and can open that product in the
 * workspace sidebar and dashboard quick links.
 *
 * Now backed by the real FastAPI + MS SQL backend via apiFetch.
 * ------------------------------------------------------------
 */

import React, { useState, useEffect } from "react";
import { FaCheckCircle } from "react-icons/fa";
import Header from "../../../components/WorkspaceHeader";
import { apiFetch } from "../../../../services/api";
import "../../../styles/manage.css";

export default function ManageProducts() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadProducts();
  }, []);

  async function loadProducts() {
    try {
      const data = await apiFetch("/api/admin/products");
      setProducts(data || []);
    } catch (err) {
      console.error("Failed to load products:", err);
      setError("Failed to load products. Please refresh the page.");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(product, checked) {
    setError(null);
    // Optimistic update so the switch feels instant...
    setProducts((prev) => prev.map((p) => (p.id === product.id ? { ...p, enabled: checked } : p)));
    try {
      await apiFetch(`/api/admin/products/${product.id}/toggle`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: checked }),
      });
    } catch (err) {
      // ...but roll it back and surface the error if the save actually failed.
      setProducts((prev) => prev.map((p) => (p.id === product.id ? { ...p, enabled: !checked } : p)));
      setError(err.message || `Failed to ${checked ? "activate" : "deactivate"} ${product.name}.`);
    }
  }

  return (
    <>
      <Header title="Products" description="Products your organization has purchased." />
      <main className="main-content">
        <div className="manage-page">
          <div className="manage-card">
            <h2 className="manage-card-heading">Your purchased products</h2>
            <p className="manage-card-subheading">
              Turn a product on or off for your users below. To add another product to your
              organization, contact your OneNextGen Automation account team.
            </p>

            {error && (
              <p className="manage-error" style={{ marginBottom: 16 }}>
                {error}
              </p>
            )}

            {loading ? (
              <p className="manage-hint">Loading products…</p>
            ) : products.length === 0 ? (
              <p className="manage-hint">No products purchased yet.</p>
            ) : (
              <div className="manage-table-wrap">
                <table className="manage-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Description</th>
                      <th className="center">Purchased</th>
                      <th className="center" style={{ width: 160 }}>
                        User Access
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((product) => {
                      const enabled = product.enabled;
                      return (
                        <tr key={product.id} id={`product-row-${product.id}`}>
                          <td style={{ fontWeight: 600 }}>{product.name}</td>
                          <td>{product.description || "—"}</td>
                          <td className="center">
                            <span className="status-pill active">
                              <FaCheckCircle size={11} style={{ marginRight: 5, verticalAlign: -1 }} />
                              Purchased
                            </span>
                          </td>
                          <td className="center">
                            <label className="pa-toggle" title={enabled ? "Deactivate for users" : "Activate for users"}>
                              <input
                                type="checkbox"
                                checked={enabled}
                                onChange={(e) => handleToggle(product, e.target.checked)}
                              />
                              <span className="pa-toggle-track">
                                <span className="pa-toggle-thumb" />
                              </span>
                              <span className={`pa-toggle-label ${enabled ? "on" : "off"}`}>
                                {enabled ? "Active" : "Deactivated"}
                              </span>
                            </label>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}