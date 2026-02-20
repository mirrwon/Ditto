export default function TimeLogSummary({ counts }) {
  return (
    <div className="timelog-summary">
      <div className="timelog-summary__item">
        <div className="timelog-summary__label">물 준 횟수</div>
        <div className="timelog-summary__value">
          💧 {counts?.water ?? 0}
        </div>
      </div>

      <div className="timelog-summary__item">
        <div className="timelog-summary__label">비료 준 횟수</div>
        <div className="timelog-summary__value">
          🧪 {counts?.fertilizer ?? 0}
        </div>
      </div>

      <div className="timelog-summary__item">
        <div className="timelog-summary__label">특이사항</div>
        <div className="timelog-summary__value">
          📝 {counts?.note ?? 0}
        </div>
      </div>
    </div>
  );
}
