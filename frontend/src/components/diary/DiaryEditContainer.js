import { useEffect, useState } from "react";
import DiaryForm from "./DiaryForm";
import { diaryApi } from "../../services/diaryApi";


const BACKEND_ORIGIN = "http://localhost:8000";

const toAbsoluteUrl = (url) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("/")) return `${BACKEND_ORIGIN}${url}`;
  return `${BACKEND_ORIGIN}/${url}`;
};


const normalizeDiaryItems = (payload) => {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  return payload.items || payload.data || [];
};

const resolveImageUrl = (item) => {
  const filename = item?.image_filename || item?.imageFilename;
  if (filename) return `/auth-uploads/${filename}`; // 상대경로로 반환

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

const toDateInputValue = (value) => {
  if (!value) return "";
  return String(value).slice(0, 10);
};

const DiaryEditContainer = ({ id, onSuccess, onCancel }) => {
  const [loadStatus, setLoadStatus] = useState("loading"); // loading | ready | error | notfound
  const [saveStatus, setSaveStatus] = useState("idle"); // idle | saving | error

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [date, setDate] = useState("");

  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");

  useEffect(() => {
    const loadPost = async () => {
      setLoadStatus("loading");
      try {
        const res = await diaryApi.getList();
        const list = normalizeDiaryItems(res?.data);

        const found = list.find((item) => String(item?.id || item?._id) === String(id));

        if (!found) {
          setLoadStatus("notfound");
          return;
        }
        setTitle(found?.title || "");
        setContent(found?.content || found?.body || "");
        setDate(toDateInputValue(getItemDateValue(found)));
        const raw = resolveImageUrl(found);
        setImagePreview(toAbsoluteUrl(raw));
        setLoadStatus("ready");
      } catch (error) {
        setLoadStatus("error");
      }
    };

    if (id) loadPost();
  }, [id]);

  useEffect(() => {
    return () => {
      if (imagePreview && String(imagePreview).startsWith("blob:")) {
        URL.revokeObjectURL(imagePreview);
      }
    };
  }, [imagePreview]);

  const handleImageChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setImageFile(file);
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);
  };

  const handleSubmit = async (event) => {
    if (event?.preventDefault) event.preventDefault();
    if (!title.trim() || !content.trim()) return;

    setSaveStatus("saving");
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("content", content);
      if (imageFile) formData.append("image", imageFile);
      if (date) formData.append("date", date);

      await diaryApi.update(id, formData);
      if (onSuccess) onSuccess(id);
    } catch (error) {
      setSaveStatus("error");
    }
  };

  const goDiaryDetail = () => {
    if (onCancel) onCancel();
  };

  if (loadStatus === "loading") return <div>Loading post...</div>;
  if (loadStatus === "error") return <div>Failed to load post.</div>;
  if (loadStatus === "notfound") return <div>Post not found.</div>;

  return (
    <DiaryForm
      mode="edit"
      title={title}
      content={content}
      date={date}
      showDate={true}
      disableDate={true}
      imagePreview={imagePreview}
      isSaving={saveStatus === "saving"}
      errorMessage={saveStatus === "error" ? "저장에 실패했습니다." : ""}
      onTitleChange={(e) => setTitle(e.target.value)}
      onContentChange={(e) => setContent(e.target.value)}
      onDateChange={(e) => setDate(e.target.value)}
      onImageChange={handleImageChange}
      onSubmit={handleSubmit}
      onCancel={goDiaryDetail}
    />
  );
};

export default DiaryEditContainer;
