import TimeLogItemCard from "./TimeLogItemCard";

export default function TimeLogLine({ groups, onDelete, showPlantTag, onEnterDecorate }) {

  if (!groups || groups.length === 0) {
    return <div className="timelog-empty">해당 기록이 없어요.</div>;
  }

  return (
    <div className="timelog-timeline">
      {groups.map((group) => (
        <section key={group.date} className="timelog-day">
          <div className="timelog-day__title">
            {formatKoreanDate(group.date)}
          </div>

          <div className="timelog-day__list">
            {group.items.map((item) => (
              <TimeLogItemCard
                key={item.id}
                item={item}
                onDelete={onDelete}
                showPlantTag={showPlantTag}
                onDecorate={onEnterDecorate}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function formatKoreanDate(isoDate) {
  if (!isoDate) return "";
  const [y, m, d] = isoDate.split("-");
  return `${y}년 ${m}월 ${d}일`;
}
