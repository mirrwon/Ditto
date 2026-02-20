import { useEffect, useMemo, useState } from "react";
import api from "../../services/api";
import "./DiaryList.css";
import { fetchWithSession } from "../../services/session";

const API_BASE = "/api/diary";
const BACKEND_ORIGIN = "http://localhost:8000";

/* 응답 형태 통일 */
const normalizeDiaryItems = (payload) => {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  return payload.items || payload.data || [];
};

/* 날짜 필드 통합 */
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

/* 이미지 URL 해결 (조원 수정 반영) */
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
  return date.toLocaleDateString("en-CA"); // YYYY-MM-DD
};

const DiaryList = ({ onViewDetail, onNewPost }) => {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [sortOrder, setSortOrder] = useState("desc"); // asc | desc
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

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

  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    const fromTs = dateFrom ? new Date(`${dateFrom}T00:00:00`).getTime() : null;
    const toTs = dateTo ? new Date(`${dateTo}T23:59:59`).getTime() : null;

    return items
      .filter((item) => {
        if (!keyword) return true;
        const title = (item?.title || "").toLowerCase();
        const content = (item?.content || item?.body || "").toLowerCase();
        return title.includes(keyword) || content.includes(keyword);
      })
      .filter((item) => {
        if (!fromTs && !toTs) return true;
        const ts = new Date(getItemDateValue(item) || 0).getTime();
        if (Number.isNaN(ts)) return false;
        if (fromTs && ts < fromTs) return false;
        if (toTs && ts > toTs) return false;
        return true;
      })
      .sort((a, b) => {
        const aDate = new Date(getItemDateValue(a) || 0).getTime();
        const bDate = new Date(getItemDateValue(b) || 0).getTime();
        return sortOrder === "asc" ? aDate - bDate : bDate - aDate;
      });
  }, [items, search, sortOrder, dateFrom, dateTo]);

  const handleSortToggle = () => {
    setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
  };

  const handleOpenPost = (itemId) => {
    if (!itemId) return;
    if (onViewDetail) onViewDetail(itemId);
  };

  const latestItems = filteredItems.slice(0, 2);
  const streamItems = filteredItems.slice(2);

  return (
    <div className="diary-list">
      <div className="diary-list__body">
        <div className="diary-list__controls">
          <button
            type="button"
            className="diary-list__sort"
            onClick={handleSortToggle}
          >
            {sortOrder === "asc" ? "날짜 오래된순" : "날짜 최신순"}
          </button>

          <div className="diary-list__date-filter">
            <input
              className="diary-list__date"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <span className="diary-list__date-sep">~</span>
            <input
              className="diary-list__date"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>

          <input
            className="diary-list__search"
            type="search"
            placeholder="다이어리 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {status === "loading" && (
          <div className="diary-list__state">
            다이어리를 불러오는 중입니다.
          </div>
        )}

        {status === "error" && (
          <div className="diary-list__state">
            다이어리를 불러오지 못했습니다.
          </div>
        )}

        {status === "ready" && filteredItems.length === 0 && (
          <div className="diary-list__state">
            다이어리 글이 없습니다.
          </div>
        )}

        {latestItems.length > 0 && (
          <section className="diary-featured">
            <div className="diary-section__head">
              <div className="diary-section__title">
                최신글
                <span className="diary-section__sub">최근 작성</span>
              </div>
              <button type="button" className="diary-section__more">
                더보기
              </button>
            </div>
            <div className="diary-featured__grid">
              {latestItems.map((item, index) => {
                const imageUrl = resolveImageUrl(item);
                const cacheBustedImageUrl = imageUrl
                  ? `${imageUrl}?t=${Date.now()}`
                  : "";
                const dateLabel = formatDateLabel(getItemDateValue(item));
                const title = item?.title || "제목 없음";
                const content = item?.content || item?.body || "";
                const itemId = item?.id || item?._id || "";
                const key = itemId || `${title}-${index}`;

                return (
                  <article
                    key={key}
                    className="diary-featured__card"
                    onClick={() => handleOpenPost(itemId)}
                  >
                    <div className="diary-featured__thumb">
                      {imageUrl ? (
                        <img
                          className="diary-featured__img"
                          src={cacheBustedImageUrl}
                          alt={title}
                        />
                      ) : (
                        <div className="diary-featured__empty">
                          사진 없음
                        </div>
                      )}
                    </div>
                    <div className="diary-featured__meta">
                      <h3 className="diary-featured__title">{title}</h3>
                      <p className="diary-featured__excerpt">
                        {content || "내용 없음"}
                      </p>
                      <div className="diary-featured__date">
                        {dateLabel || "날짜 없음"}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        )}

        {streamItems.length > 0 && (
          <div className="diary-stream">
            {streamItems.map((item, index) => {
              const imageUrl = resolveImageUrl(item);
              const cacheBustedImageUrl = imageUrl
                ? `${imageUrl}?t=${Date.now()}`
                : "";
              const dateLabel = formatDateLabel(getItemDateValue(item));
              const title = item?.title || "제목 없음";
              const content = item?.content || item?.body || "";
              const itemId = item?.id || item?._id || "";
              const key = itemId || `${title}-${index}-stream`;

              return (
                <article
                  key={key}
                  className="diary-stream__item"
                  onClick={() => handleOpenPost(itemId)}
                >
                  <div className="diary-stream__thumb">
                    {imageUrl ? (
                      <img
                        className="diary-stream__img"
                        src={cacheBustedImageUrl}
                        alt={title}
                      />
                    ) : (
                      <div className="diary-stream__empty">
                        사진 없음
                      </div>
                    )}
                  </div>
                  <div className="diary-stream__content">
                    <h3 className="diary-stream__title">{title}</h3>
                    <p className="diary-stream__excerpt">
                      {content || "내용 없음"}
                    </p>
                    <div className="diary-stream__meta">
                      <span className="diary-stream__date">
                        {dateLabel || "날짜 없음"}
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <div className="diary-list__actions">
        <div className="diary-list__actions-row">
          <button
            type="button"
            className="diary-new-btn"
            onClick={onNewPost}
          >
            새 글 작성
          </button>
        </div>
      </div>
    </div>
  );
};

export default DiaryList;
