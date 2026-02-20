import { useEffect, useState } from "react";

export function useTimeLogStorage({
  plantsKey = "plants_timelog",
  logsKey = "logs_timelog",
  initialPlants = [],
  initialLogs = [],
}) {
  const [plants, setPlants] = useState(() => {
    try {
      const saved = localStorage.getItem(plantsKey);
      return saved ? JSON.parse(saved) : initialPlants;
    } catch {
      return initialPlants;
    }
  });

  const [logs, setLogs] = useState(() => {
    try {
      const saved = localStorage.getItem(logsKey);
      return saved ? JSON.parse(saved) : initialLogs;
    } catch {
      return initialLogs;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(plantsKey, JSON.stringify(plants));
    } catch {}
  }, [plantsKey, plants]);

  useEffect(() => {
    try {
      localStorage.setItem(logsKey, JSON.stringify(logs));
    } catch {}
  }, [logsKey, logs]);

  const resetTimeLogStorage = () => {
    try {
      localStorage.removeItem(plantsKey);
      localStorage.removeItem(logsKey);
    } catch {}
    setPlants(initialPlants);
    setLogs(initialLogs);
  };

  return { plants, setPlants, logs, setLogs, resetTimeLogStorage };
}
