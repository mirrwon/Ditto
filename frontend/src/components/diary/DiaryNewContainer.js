import { useEffect, useState } from "react";
import DiaryForm from "./DiaryForm";
import { diaryApi } from "../../services/diaryApi";

const toDateInputValue = (value) => {
  if (!value) return "";
  return String(value).slice(0, 10);
};

const DiaryNewContainer = ({ onSuccess, onCancel }) => {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  // 날짜 state 추가 (기본값: 오늘)
  const [date, setDate] = useState(() => toDateInputValue(new Date().toISOString()));

  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");

  const [status, setStatus] = useState("idle"); // idle | saving | error

  const handleImageChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setImageFile(file);
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);
  };

  useEffect(() => {
    return () => {
      if (imagePreview && String(imagePreview).startsWith("blob:")) {
        URL.revokeObjectURL(imagePreview);
      }
    };
  }, [imagePreview]);

  const handleSubmit = async (event) => {
    if (event?.preventDefault) event.preventDefault();
    if (!title.trim() || !content.trim()) return;

    setStatus("saving");
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("content", content);

      // 날짜 전송 (백엔드가 date 받는 경우)
      if (date) formData.append("date", date);

      if (imageFile) formData.append("image", imageFile);

      const res = await diaryApi.create(formData);
      const newId = res?.data?.id;

      if (onSuccess) onSuccess(newId);
    } catch (error) {
      setStatus("error");
    }
  };

  const goDiaryList = () => {
    if (onCancel) onCancel();
  };

  return (
    <DiaryForm
      mode="create"
      title={title}
      content={content}
      date={date}
      showDate={true}
      disableDate={false}
      imagePreview={imagePreview}
      isSaving={status === "saving"}
      errorMessage={status === "error" ? "등록에 실패했습니다." : ""}
      onTitleChange={(e) => setTitle(e.target.value)}
      onContentChange={(e) => setContent(e.target.value)}
      onDateChange={(e) => setDate(e.target.value)}
      onImageChange={handleImageChange}
      onSubmit={handleSubmit}
      onCancel={goDiaryList}
    />
  );
};

export default DiaryNewContainer;
