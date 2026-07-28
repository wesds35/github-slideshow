import { useEffect, useState } from "react";
import type { BadgeDefinition } from "../db";
import { onBadgeEarned } from "../lib/toastBus";

interface ActiveToast extends BadgeDefinition {
  key: string;
}

export function ToastHost() {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);

  useEffect(() => {
    return onBadgeEarned((badge) => {
      const key = `${badge.id}-${Date.now()}`;
      setToasts((prev) => [...prev, { ...badge, key }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.key !== key));
      }, 5000);
    });
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div className="toast-badge" key={t.key}>
          <div className="toast-icon">{t.name[0]}</div>
          <div>
            <div className="toast-title">Badge Earned</div>
            <div className="toast-name">{t.name}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
