/**
 * data/products.js
 * ------------------------------------------------------------
 * Single source of truth for product copy, used by both the
 * Home page's product cards and each product's detail page.
 * Add a new product here and it'll show up in the header
 * dropdown (see components/Header.jsx), the Home page cards,
 * and can get its own route in App.jsx.
 * ------------------------------------------------------------
 */

export const PRODUCTS = [
  {
    id: 1,
    slug: "nextflow",
    path: "/products/nextflow",
    name: "Nextflow",
    icon: "⚙️",
    tagline: "Visual workflow automation",
    purchased: true,
    // Placeholder image for the Home page's product section — swap this
    // URL for a real product screenshot whenever it's ready.
    image: "https://picsum.photos/seed/nexaflow-nextflow/900/700",
    summary:
      "Design multi-step workflows on a visual canvas — triggers, conditions, approvals, and integrations — the same way you'd sketch a process on a whiteboard.",
    heroDescription:
      "Nextflow is a drag-and-drop workflow builder. Add a trigger, chain together steps and conditions, and publish — no code required to get your first automation running.",
    features: [
      {
        title: "Drag-and-drop canvas",
        description: "Build workflows by connecting steps visually, in the same spirit as leading RPA workflow designers.",
      },
      {
        title: "Conditional branching",
        description: "Route a process down different paths based on data, approvals, or business rules.",
      },
      {
        title: "Built-in integrations",
        description: "Connect the apps your team already uses — email, spreadsheets, CRMs, and ticketing systems.",
      },
      {
        title: "Run history & retries",
        description: "See every run in one place, and automatically retry steps that fail transiently.",
      },
    ],
  },
  {
    id: 2,
    slug: "business-process-mapper",
    path: "/products/business-process-mapper",
    name: "Business Process Mapper",
    icon: "🎥",
    tagline: "Turn screen recordings into SOPs",
    purchased: true,
    image: "https://picsum.photos/seed/nexaflow-bpm/900/700",
    summary:
      "Upload a screen recording of someone doing their job. Business Process Mapper watches and listens, then hands you back a written, step-by-step document.",
    heroDescription:
      "Business Process Mapper takes a video walkthrough as input, analyzes both the visuals and the narration inside it, and produces a clean, structured document describing every step — perfect for capturing knowledge before it walks out the door.",
    features: [
      {
        title: "Video + audio understanding",
        description: "Processes both what's shown on screen and what's said out loud during the recording.",
      },
      {
        title: "Step-by-step documents",
        description: "Outputs a structured, readable document instead of a raw transcript.",
      },
      {
        title: "Faster SOP creation",
        description: "Turn a 10-minute walkthrough into a shareable process document in minutes, not hours.",
      },
      {
        title: "Editable output",
        description: "Review and refine the generated document before publishing it to your team.",
      },
    ],
  },
  {
    id: 3,
    slug: "document-parser",
    path: "/products/document-parser",
    name: "Document Parser",
    icon: "🧾",
    tagline: "Invoice data, extracted to CSV",
    purchased: true,
    image: "https://picsum.photos/seed/nexaflow-docparser/900/700",
    summary:
      "Feed in invoice PDFs and get back clean, structured data — vendor, line items, totals, dates — ready to drop into your accounting workflow.",
    heroDescription:
      "Document Parser reads invoice PDFs, identifies the fields that matter (vendor details, line items, taxes, totals) and exports everything into a tidy CSV file your finance team can import anywhere.",
    features: [
      {
        title: "Invoice-aware extraction",
        description: "Recognizes common invoice layouts and pulls out vendor, date, line items, and totals.",
      },
      {
        title: "CSV export",
        description: "Get a ready-to-import CSV file, formatted for spreadsheets and accounting software.",
      },
      {
        title: "Batch processing",
        description: "Drop in a folder of invoices and process them all in one pass.",
      },
      {
        title: "Accuracy checks",
        description: "Flags low-confidence fields for a quick human review before export.",
      },
    ],
  },
];

export function getProductBySlug(slug) {
  return PRODUCTS.find((p) => p.slug === slug);
}
