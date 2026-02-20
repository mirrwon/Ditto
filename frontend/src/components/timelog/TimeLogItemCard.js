export default function TimeLogItemCard({ item, onDelete, showPlantTag = false, onDecorate }) {
  const icon = getTypeIcon(item?.type);
  const plantLabel = item?.plantName || item?.plant?.name || "";

  const handleDelete = () => {
    if (!item?.id) return;
    const ok = window.confirm("이 기록을 삭제할까요?");
    if (!ok) return;
    if (typeof onDelete === "function") onDelete(item.id);
  };

  const hasImage = Boolean(item?.imageUrl);
  const showImageBlock = hasImage && (item?.type === "photo" || item?.type === "new");

  return (
    <div className="timelog-item">
      <div className="timelog-item__time">{item?.time}</div>

      <div className="timelog-item__card">
        <div className="timelog-item__top">
          <div className="timelog-item__topLeft">
            <span className="timelog-item__icon" aria-hidden>
              {icon}
            </span>

            <span className="timelog-item__title">{item?.title}</span>

            {showPlantTag && plantLabel ? (
              <span className="timelog-item__plantTag">{plantLabel}</span>
            ) : null}
          </div>

          <div className="timelog-item__topRight">
            {(item?.type === "photo" || item?.type === "new") && hasImage && (
              <button
                type="button"
                className="timelog-item__decorBtn ui-btn ui-btn-primary ui-btn--compact"
                onClick={() => typeof onDecorate === 'function' && onDecorate(item)}
              >
                사진 꾸미기
              </button>
            )}
            <button
              type="button"
              className="timelog-item__deleteBtn"
              onClick={handleDelete}
              aria-label="기록 삭제"
              title="삭제"
            >
              🗑️
            </button>
          </div>
        </div>

        {item?.detail ? (
          <div className="timelog-item__detail">{item.detail}</div>
        ) : null}

        {showImageBlock ? (
          <div className="timelog-item__image">
            <img
              className="timelog-item__img"
              src={item.imageUrl}
              alt={plantLabel || item?.title || "image"}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function getTypeIcon(type) {
  switch (type) {
    case "water":
      return "💧";
    case "fertilizer":
      return "🧪";
    case "move":
      return "📦";
    case "mist":
      return "💦";
    case "clean":
      return "🧽";
    case "repot":
      return "🪴";
    case "note":
      return "📝";
    case "photo":
      return "🖼️";
    case "new":
      return "🌱";
    default:
      return "•";
  }
}
