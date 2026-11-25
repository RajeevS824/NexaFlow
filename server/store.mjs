import bcrypt from "bcryptjs";
import crypto from "node:crypto";

const hashSync = (pw) => bcrypt.hashSync(pw, 10);

export const PRODUCT_SLUGS = {
  BPM: "business-process-mapper",
  NXT: "nextflow",
  DOC: "document-parser",
};

const today = () => new Date().toISOString().slice(0, 10);
const daysAgoIso = (n) => {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString();
};
const formatDMY = (d) => {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${dd}-${mm}-${yyyy} ${hh}:${min}:${ss}`;
};

export const store = {
  nextIds: {
    org: 2,
    admin: 2,
    user: 3,
    communityUser: 90001,
    role: 3,
    contact: 1,
    demo: 1,
  },

  organizations: [
    {
      id: 1,
      name: "onenextgen",
      slug: "onenextgen",
      code: "ONG-001",
      email: "onenextgen@gmail.com",
      address: "Bengaluru",
      country: "India",
      state: "Karnataka",
      city: "Bengaluru",
      status: true,
    },
  ],

  products: [
    {
      id: 1,
      code: "BPM",
      name: "Business Process Mapper",
      slug: "business-process-mapper",
      description: "Turn screen recordings into SOPs",
      version: "1.0",
      isActive: true,
    },
    {
      id: 2,
      code: "NXT",
      name: "Nextflow",
      slug: "nextflow",
      description: "Visual workflow automation",
      version: "1.0",
      isActive: true,
    },
    {
      id: 3,
      code: "DOC",
      name: "Document Parser",
      slug: "document-parser",
      description: "Invoice document extraction",
      version: "1.0",
      isActive: true,
    },
  ],

  // { orgId, productId, licenseKey, purchaseDate, status }
  licenses: [
    { id: 1, orgId: 1, productId: 1, licenseKey: "ONG-BPM-1-1-2026", purchaseDate: today(), status: true },
    { id: 2, orgId: 1, productId: 2, licenseKey: "ONG-NXT-1-2-2026", purchaseDate: today(), status: true },
    { id: 3, orgId: 1, productId: 3, licenseKey: "ONG-DOC-1-3-2026", purchaseDate: today(), status: true },
  ],

  admins: [
    {
      id: 1,
      orgId: 1,
      fullName: "one-admin",
      email: "onenextgen@gmail.com",
      passwordHash: hashSync("1234567890"),
      status: true,
    },
  ],

  users: [
    {
      id: 1,
      orgId: 1,
      fullName: "Operations User",
      email: "user@onenextgen.com",
      passwordHash: hashSync("1234567890"),
      status: true,
      createdViaAdmin: true,
      roleId: 1,
    },
    {
      id: 2,
      orgId: 1,
      fullName: "Finance Analyst",
      email: "analyst@onenextgen.com",
      passwordHash: hashSync("1234567890"),
      status: true,
      createdViaAdmin: true,
      roleId: 2,
    },
  ],

  communityUsers: [],

  roles: [
    {
      id: 1,
      orgId: 1,
      name: "Automation Operator",
      description: "Full access to Business Process Mapper, Nextflow, and Document Parser.",
      status: "active",
      createdBy: 1,
    },
    {
      id: 2,
      orgId: 1,
      name: "Document Reviewer",
      description: "Access to Document Parser extraction and validation workflows.",
      status: "active",
      createdBy: 1,
    },
  ],

  // Map<roleId, Array<{ product_id, can_view, can_edit, can_execute }>>
  rolePermissions: new Map([
    [
      1,
      [
        { product_id: 1, can_view: true, can_edit: true, can_execute: true },
        { product_id: 2, can_view: true, can_edit: true, can_execute: true },
        { product_id: 3, can_view: true, can_edit: true, can_execute: true },
      ],
    ],
    [
      2,
      [
        { product_id: 1, can_view: false, can_edit: false, can_execute: false },
        { product_id: 2, can_view: false, can_edit: false, can_execute: false },
        { product_id: 3, can_view: true, can_edit: true, can_execute: true },
      ],
    ],
  ]),

  passwordResetTokens: new Map(),
  contactMessages: [],
  demoRequests: [],

  // ---------------- Document Parser state ----------------
  dpModels: [
    {
      id: "mod-invoice-standard-01",
      ownerId: null, // shared/demo model visible to org users
      name: "Standard Invoice Extractor",
      engine: "OCR",
      documentType: "Invoice",
      language: "en",
      description: "Extracts invoice numbers, vendor names, dates, totals, and line-item tables.",
      created: "2026-11-18 09:30:00",
      updated: "2026-11-24 14:15:00",
      processCount: 4,
      formFields: [
        {
          fieldName: "invoice_number",
          fieldLabel: "Invoice Number",
          datatype: "string",
          required: true,
          aiEnabled: false,
          prompt: "",
          aliases: ["Invoice #", "Inv No", "Bill No"],
        },
        {
          fieldName: "vendor_name",
          fieldLabel: "Vendor Name",
          datatype: "string",
          required: true,
          aiEnabled: false,
          prompt: "",
          aliases: ["Supplier", "Billed By"],
        },
        {
          fieldName: "invoice_date",
          fieldLabel: "Invoice Date",
          datatype: "date",
          required: true,
          aiEnabled: false,
          prompt: "",
          aliases: ["Date", "Issued Date"],
        },
        {
          fieldName: "total_amount",
          fieldLabel: "Total Amount",
          datatype: "number",
          required: true,
          aiEnabled: false,
          prompt: "",
          aliases: ["Grand Total", "Amount Due", "Total"],
        },
      ],
      tableFields: {
        line_items: {
          tableName: "line_items",
          required: false,
          startRows: ["Description", "Item"],
          endRows: ["Subtotal", "Total"],
          fields: [
            { fieldName: "description", fieldLabel: "Description", datatype: "string", required: true, aliases: ["Item", "Service"] },
            { fieldName: "qty", fieldLabel: "Qty", datatype: "number", required: true, aliases: ["Quantity"] },
            { fieldName: "unit_price", fieldLabel: "Unit Price", datatype: "number", required: false, aliases: ["Rate", "Price"] },
            { fieldName: "amount", fieldLabel: "Amount", datatype: "number", required: true, aliases: ["Line Total"] },
          ],
        },
      },
    },
    {
      id: "mod-po-extractor-02",
      ownerId: null,
      name: "Purchase Order Parser",
      engine: "LLM",
      documentType: "Purchase Order",
      language: "en",
      description: "Extracts PO numbers, buyer details, delivery terms, and ordered line items.",
      created: "2026-11-20 11:00:00",
      updated: "2026-11-23 16:40:00",
      processCount: 2,
      formFields: [
        {
          fieldName: "po_number",
          fieldLabel: "PO Number",
          datatype: "string",
          required: true,
          aiEnabled: true,
          prompt: "Extract the purchase order number",
          aliases: ["Order No", "PO #"],
        },
        {
          fieldName: "order_date",
          fieldLabel: "Order Date",
          datatype: "date",
          required: true,
          aiEnabled: false,
          prompt: "",
          aliases: ["Date"],
        },
      ],
      tableFields: {},
    },
  ],

  dpHistory: [
    {
      historyid: "dp-job-1001",
      ownerId: 1,
      modelid: "mod-invoice-standard-01",
      status: "completed",
      modelname: "Standard Invoice Extractor",
      documenttype: "Invoice",
      createddate: formatDMY(new Date(Date.now() - 86400000 * 3)),
      processdate: formatDMY(new Date(Date.now() - 86400000 * 3)),
      queuedAt: daysAgoIso(3),
      documentname: "ACME_INV_2026_089.pdf",
      stp: true,
      error_message: "",
      pages: [
        {
          page_number: 1,
          status: "Completed",
          annotated_image_path: "",
          enhanced_image_path: "",
          extracted_data: {
            fields: [
              { label_name: "invoice_number", value: "INV-2026-089", confidence: 0.98 },
              { label_name: "vendor_name", value: "Acme Industrial Supplies", confidence: 0.96 },
              { label_name: "invoice_date", value: "2026-11-20", confidence: 0.95 },
              { label_name: "total_amount", value: "4250.00", confidence: 0.99 },
            ],
            header_extraction: [],
          },
        },
      ],
    },
    {
      historyid: "dp-job-1002",
      ownerId: 1,
      modelid: "mod-invoice-standard-01",
      status: "pending",
      modelname: "Standard Invoice Extractor",
      documenttype: "Invoice",
      createddate: formatDMY(new Date(Date.now() - 86400000 * 1)),
      processdate: formatDMY(new Date(Date.now() - 86400000 * 1)),
      queuedAt: daysAgoIso(1),
      documentname: "Globex_Invoice_442.pdf",
      stp: false,
      error_message: "",
      pages: [
        {
          page_number: 1,
          status: "Pending",
          annotated_image_path: "",
          enhanced_image_path: "",
          extracted_data: {
            fields: [
              { label_name: "invoice_number", value: "GLX-442", confidence: 0.91 },
              { label_name: "vendor_name", value: "Globex Logistics Ltd", confidence: 0.89 },
              { label_name: "invoice_date", value: "2026-11-24", confidence: 0.94 },
              { label_name: "total_amount", value: "1890.50", confidence: 0.88 },
            ],
            header_extraction: [],
          },
        },
      ],
    },
    {
      historyid: "dp-job-1003",
      ownerId: 2,
      modelid: "mod-po-extractor-02",
      status: "completed",
      modelname: "Purchase Order Parser",
      documenttype: "Purchase Order",
      createddate: formatDMY(new Date()),
      processdate: formatDMY(new Date()),
      queuedAt: daysAgoIso(0),
      documentname: "PO_Northwind_718.pdf",
      stp: true,
      error_message: "",
      pages: [],
    },
  ],

  dpSettings: new Map(),

  // ---------------- Business Map state ----------------
  bmJobs: new Map([
    [
      "bm-job-5001",
      {
        job_id: "bm-job-5001",
        job_name: "Invoice_Approval_Walkthrough",
        user_id: 1,
        username: "Operations User",
        email: "user@onenextgen.com",
        video_filename: "invoice_approval_demo.mp4",
        size_bytes: 14_820_400,
        status: "SUCCESS",
        progress: 100,
        phase: "Completed",
        latency_sec: 12.4,
        error: null,
        created_at: daysAgoIso(2),
        processed_at: daysAgoIso(2),
        outputs: {
          workflow_steps_clean: "output/bm-job-5001/workflow_steps_clean.md",
          workflow_validation: "output/bm-job-5001/workflow_validation.md",
        },
      },
    ],
    [
      "bm-job-5002",
      {
        job_id: "bm-job-5002",
        job_name: "Vendor_Onboarding_SOP",
        user_id: 1,
        username: "Operations User",
        email: "user@onenextgen.com",
        video_filename: "vendor_onboarding.mp4",
        size_bytes: 22_140_000,
        status: "SUCCESS",
        progress: 100,
        phase: "Completed",
        latency_sec: 16.8,
        error: null,
        created_at: daysAgoIso(0),
        processed_at: daysAgoIso(0),
        outputs: {
          workflow_steps_clean: "output/bm-job-5002/workflow_steps_clean.md",
          workflow_validation: "output/bm-job-5002/workflow_validation.md",
        },
      },
    ],
  ]),

  bmLogSettings: new Map(),
  bmUploadSettings: new Map(),
  bmLlmSettings: new Map(),
};

export function getOrgLicensedProducts(orgId) {
  const activeLicenses = store.licenses.filter((l) => l.orgId === orgId && l.status);
  const licensedIds = new Set(activeLicenses.map((l) => l.productId));
  return store.products
    .filter((p) => p.isActive && licensedIds.has(p.id))
    .map((p) => ({
      id: p.id,
      code: p.code,
      name: p.name,
      slug: p.slug,
    }));
}

export function getUserRoleProducts(userId, orgId) {
  const user = store.users.find((u) => u.id === userId && u.orgId === orgId);
  if (!user || !user.roleId) return [];
  const role = store.roles.find((r) => r.id === user.roleId && r.orgId === orgId && r.status === "active");
  if (!role) return [];
  const perms = store.rolePermissions.get(role.id) || [];
  const licensedIds = new Set(
    store.licenses.filter((l) => l.orgId === orgId && l.status).map((l) => l.productId)
  );
  const result = [];
  for (const perm of perms) {
    if (!perm.can_view || !licensedIds.has(perm.product_id)) continue;
    const prod = store.products.find((p) => p.id === perm.product_id && p.isActive);
    if (!prod) continue;
    result.push({
      id: prod.id,
      code: prod.code,
      name: prod.name,
      slug: prod.slug,
      can_view: Boolean(perm.can_view),
      can_edit: Boolean(perm.can_edit),
      can_execute: Boolean(perm.can_execute),
    });
  }
  return result;
}

export function getOrgUserIds(orgId) {
  const ent = store.users.filter((u) => u.orgId === orgId).map((u) => u.id);
  const com = store.communityUsers.filter((u) => u.orgId === orgId).map((u) => u.id);
  return [...ent, ...com];
}

export function generateUuid() {
  return crypto.randomUUID();
}
