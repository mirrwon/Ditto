import TimeLogLine from "./TimeLogLine";

export default function TimeLogTimelineSection({
  groups,
  onDelete,
  showPlantTag,
  onEnterDecorate,
}) {
  return (
    <div className="timelog-timeline-section">
      <div className="timelog__sectionTitle">오늘의 타임라인</div>
      <div className="timelog__dateLabel">Test</div>
      <TimeLogLine
        groups={groups}
        onDelete={onDelete}
        showPlantTag={showPlantTag}
        onEnterDecorate={onEnterDecorate}
      />
    </div>
  );
}
