import { useEffect, useMemo, useState } from "react";
import TimeLogSummary from "../../components/timelog/TimeLogSummary";
import TimeLogFilterTabs from "../../components/timelog/TimeLogFilterTabs";
import TimeLogPlantSelector from "../../components/timelog/TimeLogPlantSelector";
import TimeLogActionBar from "../../components/timelog/TimeLogActionBar";
import TimeLogTimelineSection from "../../components/timelog/TimeLogTimelineSection";
import useTimeLogData from "../../hooks/useTimeLogData";
import useTimeLogComputed from "../../hooks/useTimeLogComputed";
import useTimeLogHandlers from "../../hooks/useTimeLogHandlers";

import "./TimeLog.css";

export default function TimeLogPage({
  onEnterDecorate,
  decoratedData,
  onSelectPlant,
  initialActivePlantId = "",
  showHeader = true,
  showControls = true,
  showTimeline = true,
  showActionBar = true,
  enableFiltering = true,
  mode = "timelog",
  filterTabs,
  onTrigger,
  children,
}) {
  const [activeTab, setActiveTab] = useState("all");
  const [activePlantId, setActivePlantId] = useState(initialActivePlantId || "");

  const { plants, logs, createLog, createPlant, deleteLog } = useTimeLogData();
  const activePlant = useMemo(() => plants.find((p) => p.id === activePlantId) || null, [plants, activePlantId]);

  // If a stored plant exists and user hasn't picked yet, hydrate the selection.
  useEffect(() => {
    if (!activePlantId && initialActivePlantId) {
      setActivePlantId(initialActivePlantId);
    }
  }, [activePlantId, initialActivePlantId]);

  // Keep parent selection in sync with latest plant data.
  useEffect(() => {
    if (onSelectPlant) {
      onSelectPlant(activePlant);
    }
  }, [activePlant, onSelectPlant]);

  useEffect(() => {
    if (!enableFiltering && activeTab !== "all") {
      setActiveTab("all");
    }
  }, [enableFiltering, activeTab]);
  const isPlantSelected = Boolean(activePlantId);
  const { counts, groups } = useTimeLogComputed({ logs, activePlantId, activeTab });
  const { addDiaryLog, handleUploadPhoto, deleteDiaryLog } = useTimeLogHandlers({
    plants,
    activePlant,
    activePlantId,
    setActivePlantId,
    createLog,
    createPlant,
    deleteLog,
    decoratedData,
  });

  return (
    <div className={`timelog timelog--${mode}`}>
      {showHeader && (
        <div className="timelog__header">
          <div className="timelog__title">TIME LOG</div>
        </div>
      )}

      <div className="timelog-inner">
        {showControls && (
          <>
            <TimeLogPlantSelector
              plants={plants}
              activePlantId={activePlantId}
              onChange={(e) => {
                const nextId = e.target.value;
                setActivePlantId(nextId);
                if (onSelectPlant) {
                  const selected = plants.find((p) => p.id === nextId) || null;
                  onSelectPlant(selected);
                }
              }}
            />

            <div className="timelog-summaryRow timelog-summaryRow--hidden" />

            <TimeLogFilterTabs
              activeTab={activeTab}
              counts={counts}
              onChangeTab={setActiveTab}
              disabled={!enableFiltering}
              tabs={filterTabs}
            />
          </>
        )}

        {showTimeline && (
          <TimeLogTimelineSection
            groups={groups}
            onDelete={deleteDiaryLog}
            showPlantTag={!activePlantId}
            onEnterDecorate={onEnterDecorate}
          />
        )}

        {children}
      </div>

      {showActionBar && (
        <TimeLogActionBar
          isPlantSelected={isPlantSelected}
          onAddDiaryLog={addDiaryLog}
          onUploadPhoto={handleUploadPhoto}
          onTrigger={onTrigger}
          hideExtras={!showTimeline}
        />
      )}
    </div>
  );
}
