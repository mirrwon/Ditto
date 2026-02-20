const TABS = [
  { key: "all", label: "전체" },
  { key: "water", label: "물 주기" },
  { key: "fertilizer", label: "비료 주기" },
  { key: "move", label: "자리 이동" },
  { key: "mist", label: "분무" },
  { key: "clean", label: "청소" },
  { key: "note", label: "특이사항" },
  { key: "photo", label: "사진" },
];

export default function TimeLogFilterTabs({
  activeTab,
  onChangeTab,
  counts,
  disabled = false,
  tabs = TABS,
}) {
  const handleClickTab = (key) => {
    if (disabled) return;
    onChangeTab(key);
  };

  return (
    <div className="timelog-tabs" role="tablist" aria-label="다이어리 필터">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.key;

        return (
          <button
            key={tab.key}
            type="button"
            className={`timelog-tab ${isActive ? "is-active" : ""}`}
            onClick={() => handleClickTab(tab.key)}
            role="tab"
            aria-selected={isActive}
            aria-disabled={disabled}
            disabled={disabled}
          >
            <span className="timelog-tab__label">{tab.label}</span>

            <span className="timelog-tab__badge">
              {counts?.[tab.key] ?? 0}
            </span>
          </button>
        );
      })}
    </div>
  );
}
