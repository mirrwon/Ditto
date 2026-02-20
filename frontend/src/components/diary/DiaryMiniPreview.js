import { useEffect, useMemo, useState } from "react";
import api from "../../services/api";
import { fetchWithSession } from "../../services/session";
import "./DiaryMiniPreview.css";

const API_BASE = "/api/diary";
const BACKEND_ORIGIN = "http://localhost:8000";

const normalizeDiaryItems = (payload) => {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  return payload.items || payload.data || [];
};

const getItemDateValue = (item) => {
  return (
    item?.date ||
    item?.created_at ||
    item?.createdAt ||
    item?.createdDate ||
    item?.created_date ||
    null
  );
};

const resolveImageUrl = (item) => {
  const filename = item?.image_filename || item?.imageFilename;
  if (filename) return `${BACKEND_ORIGIN}/auth-uploads/${filename}`;

  return (
    item?.imageUrl ||
    item?.image_url ||
    item?.photoUrl ||
    item?.photo_url ||
    item?.photo ||
    item?.image ||
    ""
  );
};

const formatDateLabel = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-CA");
};

const getExcerpt = (text) => {
  if (!text) return "";
  const plain = String(text).replace(/\s+/g, " ").trim();
  if (plain.length <= 100) return plain;
  return `${plain.slice(0, 100)}...`;
};

export default function DiaryMiniPreview() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    const fetchDiary = async () => {
      setStatus("loading");
      try {
        const response = await api.get(API_BASE);
        const list = normalizeDiaryItems(response.data);
        setItems(list);
        setStatus("ready");
        return;
      } catch (error) {
        try {
          const res = await fetchWithSession(API_BASE);
          if (!res.ok) throw new Error("failed");
          const data = await res.json();
          const list = normalizeDiaryItems(data);
          setItems(list);
          setStatus("ready");
          return;
        } catch (e) {
          setStatus("error");
        }
      }
    };

    fetchDiary();
  }, []);

  const latest = useMemo(() => {
    if (!items.length) return null;
    const sorted = [...items].sort((a, b) => {
      const aDate = new Date(getItemDateValue(a) || 0).getTime();
      const bDate = new Date(getItemDateValue(b) || 0).getTime();
      return bDate - aDate;
    });
    return sorted[0] || null;
  }, [items]);

  if (status === "loading") {
    return <div className="diary-mini__state">???? ?...</div>;
  }

  if (status === "error" || !latest) {
    return <div className="diary-mini__state">?? ????? ????</div>;
  }

  const imageUrl = resolveImageUrl(latest);
  const cacheBustedImageUrl = imageUrl ? `${imageUrl}?t=${Date.now()}` : "";
  const dateLabel = formatDateLabel(getItemDateValue(latest));
  const title = latest?.title || "?? ??";
  const content = latest?.content || latest?.body || "";

  return (
    <div className="diary-mini">
      <div className="diary-mini__head">
        <span className="diary-mini__label">LATEST</span>
      </div>
      <div className="diary-mini__thumb">
        {imageUrl ? (
          <img className="diary-mini__img" src={cacheBustedImageUrl} alt={title} />
        ) : (
          <div className="diary-mini__empty">?? ??</div>
        )}
      </div>
      <div className="diary-mini__meta">
        <div className="diary-mini__date">{dateLabel || "?? ??"}</div>
        <div className="diary-mini__title">{title}</div>
        <div className="diary-mini__excerpt">{getExcerpt(content) || "?? ??"}</div>
      </div>
    </div>
  );
}
