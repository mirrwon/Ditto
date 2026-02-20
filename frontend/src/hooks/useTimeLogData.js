import { useCallback, useEffect, useState } from "react";
import { fetchWithSession } from "../services/session";

export default function useTimeLogData() {
  const [plants, setPlants] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchPlants = useCallback(async () => {
    try {
      const res = await fetchWithSession("/api/plantboard/plants");
      const data = await res.json();
      if (data.ok) {
        setPlants(data.items || []);
      }
    } catch (err) {
      console.error("Failed to fetch plants:", err);
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetchWithSession("/api/plantboard/logs");
      const data = await res.json();
      if (data.ok) {
        setLogs(data.items || []);
      }
    } catch (err) {
      console.error("Failed to fetch logs:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const createLog = useCallback(
    async (logData) => {
      try {
        const res = await fetchWithSession("/api/plantboard/logs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ log: logData }),
        });
        const data = await res.json();
        if (data.ok) {
          fetchLogs();
        }
      } catch (err) {
        console.error("Failed to create log:", err);
      }
    },
    [fetchLogs]
  );

  const createPlant = useCallback(
    async (plantData) => {
      try {
        const res = await fetchWithSession("/api/plantboard/plants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plant: plantData }),
        });
        const data = await res.json();
        if (data.ok) {
          await fetchPlants();
          return data.item;
        }
      } catch (err) {
        console.error("Failed to create plant:", err);
      }
      return null;
    },
    [fetchPlants]
  );

  const deleteLog = useCallback(
    async (logId) => {
      try {
        const res = await fetchWithSession(`/api/plantboard/logs/${logId}`, {
          method: "DELETE",
        });
        const data = await res.json();
        if (data.ok) {
          fetchLogs();
        }
      } catch (err) {
        console.error("Failed to delete log:", err);
      }
    },
    [fetchLogs]
  );

  useEffect(() => {
    fetchPlants();
    fetchLogs();
  }, [fetchPlants, fetchLogs]);

  return {
    plants,
    logs,
    loading,
    fetchPlants,
    fetchLogs,
    createLog,
    createPlant,
    deleteLog,
  };
}
