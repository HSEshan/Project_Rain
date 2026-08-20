import React, { useEffect } from "react";
import { FiX } from "react-icons/fi";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Escape closes, the backdrop closes, and the page behind stops scrolling —
 * the three things the old modal did not do.
 */
export default function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  className = "",
}: ModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/80 p-0 backdrop-blur-sm animate-fade-in sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`glass w-full max-w-md rounded-t-3xl border-white/10 bg-ink-850/95 p-6 shadow-lift animate-scale-in sm:rounded-3xl ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-white">{title}</h2>
            {description && (
              <p className="mt-1 text-sm text-ink-400">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="-mr-1 -mt-1 rounded-lg p-2 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
            aria-label="Close"
          >
            <FiX size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
