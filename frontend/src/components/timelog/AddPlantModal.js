export default function AddPlantModal({
  open,
  onClose,
  newPlantName,
  onChangeName,
  onChangeFile,
  onSubmit,
}) {
  if (!open) return null;

  return (
    <div className="timelog-modal" onClick={onClose}>
      <div className="timelog-modal__panel" onClick={(e) => e.stopPropagation()}>
        <div className="timelog-modal__title">새 식물 추가</div>
        <label className="timelog-modal__label">식물 이름</label>
        <input
          className="timelog-modal__input"
          value={newPlantName}
          onChange={onChangeName}
          placeholder="예) 몬스테라"
        />
        <label className="timelog-modal__label">대표 사진</label>
        <input
          className="timelog-modal__file"
          type="file"
          accept="image/*"
          onChange={onChangeFile}
        />
        <div className="timelog-modal__actions">
          <button type="button" className="timelog-modal__btn" onClick={onClose}>
            취소
          </button>
          <button
            type="button"
            className="timelog-modal__btn timelog-modal__btn--primary"
            onClick={onSubmit}
          >
            등록
          </button>
        </div>
      </div>
    </div>
  );
}
