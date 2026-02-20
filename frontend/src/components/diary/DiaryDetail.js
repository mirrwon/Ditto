import { useEffect, useState } from "react";
import api from "../../services/api";
import './DiaryDetail.css'

const API_BASE = "/api/diary";
const BACKEND_ORIGIN = "http://localhost:8000";

/* 상대경로 → 절대경로 */
const toAbsoluteUrl = (url) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${BACKEND_ORIGIN}${url}`;
};

const withCacheBust = (url) => {
  if (!url) return "";
  return `${url}?t=${Date.now()}`;
};

/* 응답 데이터 형태 통일 */
const normalizeDiaryItems = (payload) => {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  return payload.items || payload.data || [];
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

const formatDateLabel = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-CA"); // YYYY-MM-DD
};

const DiaryDetail = ({ id, onGoList, onEdit, onDeleteSuccess }) => {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [post, setPost] = useState(null);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fetchPost = async () => {
      setStatus("loading");
      try {
        const response = await api.get(API_BASE);
        const list = normalizeDiaryItems(response.data);

        const found = list.find((item) => String(item?.id || item?._id) === String(id));

        setPost(found || null);
        setStatus("ready");
      } catch (error) {
        setStatus("error");
      }
    };

    if (id) fetchPost();
  }, [id]);

  const handleEdit = () => {
    if (onEdit) onEdit(id);
  };

  const handleGoList = () => {
    if (onGoList) onGoList();
  };

  const handleDelete = async () => {
    if (!id) return;
    const confirmed = window.confirm("Delete this post?");
    if (!confirmed) return;

    setIsDeleting(true);
    try {
      await api.delete(`${API_BASE}/${id}`);
      if (onDeleteSuccess) onDeleteSuccess();
    } catch (error) {
      setIsDeleting(false);
      window.alert("Failed to delete post.");
    }
  };

  const handleOpenLightbox = (hasImage) => {
    if (!hasImage) return;
    setIsLightboxOpen(true);
  };

  const handleCloseLightbox = () => {
    setIsLightboxOpen(false);
  };

  if (status === "loading") return <div>Loading post...</div>;
  if (status === "error") return <div>Failed to load post.</div>;
  if (!post) return <div>Post not found.</div>;

  const rawImageUrl = resolveImageUrl(post);
  const imageUrl = toAbsoluteUrl(rawImageUrl);
  const cacheBustedImageUrl = withCacheBust(imageUrl);
  const dateLabel = formatDateLabel(getItemDateValue(post));
  const title = post?.title || "제목 없음";
  const content = post?.content || post?.body || "";

  return (
    <div className="diary-detail">
      <div className="diary-detail__body">
        <div className="diary-detail__photo-card">
          <button
            type="button"
            className="diary-detail__photoBtn"
            onClick={() => handleOpenLightbox(Boolean(imageUrl))}
          >
            {imageUrl ? (
              <img
                className="diary-detail__photo"
                src={cacheBustedImageUrl}
                alt={title}
              />
            ) : (
              <div className="diary-detail__empty">
                사진이 없습니다
              </div>
            )}
          </button>
        </div>

        <div className="diary-detail__text-card">
          <div className="diary-detail__date">
            {dateLabel || "날짜 없음"}
          </div>
          <h2 className="diary-detail__postTitle">{title}</h2>
          <p className="diary-detail__content">
            {content || "내용 없음"}
          </p>
        </div>
      </div>

      <div className="diary-detail__actions">
        <div className="diary-detail__actions-row">
          <button className="diary-detail-btn" onClick={handleGoList}>
            목록
          </button>
          <button className="diary-detail-btn" onClick={handleEdit}>
            수정
          </button>
          <button
            className="diary-detail-btn diary-detail-btn--danger"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? "삭제중..." : "삭제"}
          </button>
        </div>
      </div>

      {isLightboxOpen && (
        <div
          className="diary-lightbox"
          onClick={handleCloseLightbox}
        >
          <button
            type="button"
            className="diary-lightbox__close"
            onClick={handleCloseLightbox}
          >
            닫기
          </button>

          <div
            className="diary-lightbox__panel"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              className="diary-lightbox__img"
              src={cacheBustedImageUrl}
              alt={title}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default DiaryDetail;
