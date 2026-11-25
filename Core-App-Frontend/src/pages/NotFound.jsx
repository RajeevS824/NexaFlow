import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-25 px-4 text-center">
      <p className="font-mono text-sm text-amber-500">404</p>
      <h1 className="mt-2 font-display text-2xl font-bold text-ink-800">Page not found</h1>
      <p className="mt-2 text-sm text-ink-400">The page you're looking for doesn't exist.</p>
      <Link to="/" id="back-home-link" className="btn-primary mt-6">
        Back to home
      </Link>
    </div>
  );
}
