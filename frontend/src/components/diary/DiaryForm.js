import "./DiaryForm.css";

const DiaryForm = ({
  mode, // "create" | "edit"
  title,
  content,
  date,
  showDate,
  disableDate,
  imagePreview,
  isSaving,
  errorMessage,
  onTitleChange,
  onContentChange,
  onDateChange,
  onImageChange,
  onSubmit,
  onCancel,
}) => {
  return (
    <div className="diary-form">
      <form className="diary-form__body" onSubmit={onSubmit}>
        {showDate && (
          <div className="diary-form__date">
            <input
              className="diary-form__date-input"
              type="date"
              value={date}
              onChange={onDateChange}
              disabled={disableDate}
            />
          </div>
        )}

        <div className="diary-form__content">
          <div className="diary-form__image">
            {imagePreview ? (
              <img
                className="diary-form__image-img"
                src={imagePreview}
                alt="preview"
              />
            ) : (
              <div className="diary-form__image-empty">
                사진이 없습니다<br />사진을 선택해주세요
              </div>
            )}

            <label className="diary-form__file-btn">
              이미지 업로드
              <input
                className="diary-form__file-input"
                type="file"
                accept="image/*"
                onChange={onImageChange}
              />
            </label>
          </div>

          <input
            className="diary-form__input"
            value={title}
            onChange={onTitleChange}
            placeholder="제목을 입력해주세요..."
          />

          <textarea
            className="diary-form__textarea"
            value={content}
            onChange={onContentChange}
            placeholder="오늘의 식물 이야기를 들려주세요.."
            rows={8}
          />

          {errorMessage && (
            <div className="diary-form__error">
              오류: {errorMessage}
            </div>
          )}
        </div>
      </form>

      <div className="diary-form__actions">
        <div className="diary-form__actions-row">
          <button type="submit" className="diary-form-btn diary-form-btn--primary" onClick={onSubmit}>
            {isSaving ? "저장중..." : "저장"}
          </button>
          <button type="button" className="diary-form-btn" onClick={onCancel}>
            취소
          </button>
        </div>
      </div>
    </div>
  );
};

export default DiaryForm;
