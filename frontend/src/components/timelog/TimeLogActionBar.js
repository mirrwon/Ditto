import { useRef } from "react";

export default function TimeLogActionBar({
  isPlantSelected,
  onAddDiaryLog,
  onUploadPhoto,
  onTrigger,
  hideExtras = false,
}) {
  const TRIGGER_MAP = {
    water: "WATER_DONE_OK",
    fertilizer: "FERTILIZE_DONE_OK",
    move: "ROTATE_DONE_OK",
    mist: "MIST_DONE_OK",
    clean: "CLEAN_DONE_OK",
  };

  const handleAction = (type) => {
    onAddDiaryLog(type);
    if (onTrigger && TRIGGER_MAP[type]) {
      onTrigger(TRIGGER_MAP[type]);
    }
  };
  const fileInputRef = useRef(null);

  const handleActionBtnFileClick = () => {
    if (fileInputRef.current) fileInputRef.current.click();
  };

  return (
    <div className="timelog-actions">
      <div className="timelog-actions__row">
        <button
          type="button"
          className="timelog-actionBtn"
          onClick={() => handleAction("water")}
          disabled={!isPlantSelected}
        >
          <span>💧</span> 물 주기
        </button>
        <button
          type="button"
          className="timelog-actionBtn"
          onClick={() => handleAction("fertilizer")}
          disabled={!isPlantSelected}
        >
          <span>🧪</span> 비료 줌
        </button>
        <button
          type="button"
          className="timelog-actionBtn"
          onClick={() => handleAction("move")}
          disabled={!isPlantSelected}
        >
          <span>📦</span> 자리 이동
        </button>
        <button
          type="button"
          className="timelog-actionBtn"
          onClick={() => handleAction("mist")}
          disabled={!isPlantSelected}
        >
          <span>💦</span> 분무
        </button>
        <button
          type="button"
          className="timelog-actionBtn"
          onClick={() => handleAction("clean")}
          disabled={!isPlantSelected}
        >
          <span>🧼</span> 잎 닦기
        </button>
        {!hideExtras && (
          <>
            <button
              type="button"
              className="timelog-actionBtn"
              onClick={() => onAddDiaryLog("note")}
              disabled={!isPlantSelected}
            >
              <span>📝</span> 특이사항
            </button>
            <button
              type="button"
              className="timelog-actionBtn timelog-actionBtn--file"
              disabled={!isPlantSelected}
              onClick={handleActionBtnFileClick}
            >
              <span>🖼️</span> 사진추가
              <input
                ref={fileInputRef}
                className="timelog-fileInput"
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={onUploadPhoto}
              />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
