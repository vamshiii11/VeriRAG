import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f7fb] px-6 text-center">
      <div>
        <p className="font-display text-6xl font-semibold tracking-[-0.08em] text-[#172333]">404</p>
        <p className="mt-3 text-sm text-[#718096]">This evidence trail doesn’t exist.</p>
        <Link to="/" className="mt-6 inline-flex rounded-xl bg-[#101827] px-4 py-2.5 text-xs font-semibold text-white">Return to overview</Link>
      </div>
    </div>
  );
};

export default NotFound;
