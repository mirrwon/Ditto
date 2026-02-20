import { useMemo } from "react";

export default function useTimeLogComputed({ logs, activePlantId, activeTab }) {
  const filteredLogs = useMemo(() => {
    let base = logs;
    if (activePlantId) base = base.filter((log) => log.plantId === activePlantId);
    if (activeTab === "all") return base;
    return base.filter((log) => log.type === activeTab);
  }, [activeTab, logs, activePlantId]);

  const counts = useMemo(() => {
    const base = { all: 0, water: 0, fertilizer: 0, move: 0, mist: 0, clean: 0, note: 0, photo: 0, new: 0 };
    const target = activePlantId ? logs.filter((l) => l.plantId === activePlantId) : logs;
    base.all = target.length;
    target.forEach((log) => {
      if (base[log.type] !== undefined) base[log.type] += 1;
    });
    return base;
  }, [logs, activePlantId]);

  const groups = useMemo(() => {
    const map = new Map();
    filteredLogs.forEach((log) => {
      const dateKey = (log.date || "").trim();
      if (!dateKey) return;
      if (!map.has(dateKey)) map.set(dateKey, []);
      map.get(dateKey).push(log);
    });
    const sortedDates = Array.from(map.keys()).sort((a, b) => (a < b ? 1 : -1));
    return sortedDates.map((date) => {
      const items = map.get(date).slice().sort((a, b) => (a.time > b.time ? 1 : -1));
      return { date, items };
    });
  }, [filteredLogs]);

  return { filteredLogs, counts, groups };
}
