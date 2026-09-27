import { useEffect, useState } from "react";

import { getToken } from "../services/auth";

interface Props {
  src: string;
  alt: string;
  className?: string;
  onClick?: () => void;
}

/**
 * Renders an image, transparently handling the authenticated `/uploads/…` path.
 *
 * Uploaded images are not public, so a plain `<img src>` can't load them for
 * Bearer-token sessions (only cookies would be sent). For those we fetch the
 * bytes with the session token and render an object URL; every other URL (AI
 * CDN images, data: URIs) renders as a normal <img>.
 */
export default function AuthedImage({ src, alt, className, onClick }: Props) {
  const isUpload = src.startsWith("/uploads/");
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!isUpload) {
      setBlobUrl(null);
      return;
    }
    let cancelled = false;
    let created: string | null = null;
    const token = getToken();
    fetch(src, {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(String(res.status)))))
      .then((blob) => {
        if (cancelled) return;
        created = URL.createObjectURL(blob);
        setBlobUrl(created);
      })
      .catch(() => {
        if (!cancelled) setBlobUrl(null);
      });
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [src, isUpload]);

  if (!isUpload) {
    return <img src={src} alt={alt} className={className} onClick={onClick} />;
  }
  if (!blobUrl) {
    return (
      <div
        className={className}
        aria-label="loading image"
        style={{ background: "var(--surface-2)" }}
      />
    );
  }
  return <img src={blobUrl} alt={alt} className={className} onClick={onClick} />;
}
