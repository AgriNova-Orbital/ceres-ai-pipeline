"use client";

import { useState } from "react";

export default function BrandLogo({
  src,
  alt,
  className,
  fallback = "Ceres AI",
}: {
  src: string;
  alt: string;
  className?: string;
  fallback?: string;
}) {
  const [broken, setBroken] = useState(false);

  if (broken) {
    return (
      <div className={`inline-flex items-center justify-center rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs font-semibold ${className ?? ""}`}>
        {fallback}
      </div>
    );
  }

  return <img src={src} alt={alt} className={className} onError={() => setBroken(true)} />;
}
