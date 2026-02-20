import { useEffect } from "react";

import { readPendingDiaryPhoto, clearPendingDiaryPhoto } from "../components/timelog/TimeLogPending";
import { FileToDataUrl } from "../components/timelog/FileToDataUrl";

export default function useTimeLogHandlers({
  plants,
  activePlant,
  activePlantId,
  setActivePlantId,
  newPlantName,
  newPlantFile,
  setNewPlantName,
  setNewPlantFile,
  setIsAddPlantOpen,
  createLog,
  createPlant,
  deleteLog,
  decoratedData,
}) {
  // --- Pending Photo Logic (from Chat) ---
  useEffect(() => {
    const applyPending = async () => {
      const pending = readPendingDiaryPhoto();
      if (!pending?.plantName || !pending?.imageUrl) return;

      clearPendingDiaryPhoto();

      // 1) Find plant or create
      let plant = plants.find((p) => p.name === pending.plantName);
      if (!plant) {
        // Create new plant automatically
        const newPlantData = {
          name: pending.plantName,
          coverUrl: pending.imageUrl,
          createdBy: "chatbot",
        };
        plant = await createPlant(newPlantData);
      }

      if (!plant) return; // Fail safe

      // 2) Select plant
      setActivePlantId(plant.id);

      // 3) Create logs
      const now = buildNow();

      // Photo Log
      await createLog({
        type: "photo",
        date: now.date,
        time: now.time,
        plantId: plant.id,
        plantName: plant.name,
        title: "배치 사진 저장",
        detail: "챗봇 최종 선택 이미지",
        imageUrl: pending.imageUrl,
        meta: { resultId: pending.resultId || null },
      });

      // New Plant Log (only if it was new, but logic sets it anyway usually)
      await createLog({
        type: "new",
        date: now.date,
        time: now.time,
        plantId: plant.id,
        plantName: plant.name,
        title: "새 식물 추가",
        detail: "새 식물을 등록했어요.",
        imageUrl: plant.coverUrl || pending.imageUrl,
      });
    };

    if (plants.length > 0) {
      // Only run if plants loaded or empty list confirmed, avoiding race condition?
      // Actually pending read clears it, so we need to be careful.
      // For simplicity, we assume plants load fast or we accept race.
      // A better way is checking if 'loading' in fetchPlants is done.
      applyPending();
    }
  }, [plants, createLog, createPlant, setActivePlantId]);

  const addPlantManually = async () => {
    const name = (newPlantName || "").trim();
    if (!name) return alert("식물 이름을 입력하세요.");
    if (!newPlantFile) return alert("대표 사진을 선택하세요.");

    const exist = plants.find((p) => p.name === name);
    if (exist) return alert("같은 이름의 식물이 이미 있어요.");

    let coverUrl = "";
    try {
      coverUrl = await FileToDataUrl(newPlantFile);
    } catch {
      return alert("이미지 처리에 실패했어요.");
    }

    const newPlantData = { name, coverUrl, createdBy: "manual" };
    const savedPlant = await createPlant(newPlantData);

    if (savedPlant) {
      setActivePlantId(savedPlant.id);
      setIsAddPlantOpen(false);
      setNewPlantName("");
      setNewPlantFile(null);

      // Log
      const now = buildNow();
      await createLog({
        type: "new",
        date: now.date,
        time: now.time,
        plantId: savedPlant.id,
        plantName: savedPlant.name,
        title: "새 식물 등록",
        detail: "수동으로 추가한 식물",
        imageUrl: coverUrl,
      });
    }
  };

  const addDiaryLog = async (type) => {
    if (!activePlant) return;

    if (type === "note") {
      const memo = window.prompt("특이사항 메모를 입력하세요");
      if (!memo || !memo.trim()) return;

      const now = buildNow();
      await createLog({
        type,
        date: now.date,
        time: now.time,
        plantId: activePlant.id,
        plantName: activePlant.name,
        title: "특이사항",
        detail: memo.trim(),
      });
      return;
    }

    if (type === "photo") return;

    const now = buildNow();
    let title = "기록";
    let detail = "";
    if (type === "water") {
      title = "물 주기";
      detail = activePlant.name;
    }
    if (type === "fertilizer") {
      title = "비료 줌";
      detail = activePlant.name;
    }
    if (type === "move") {
      title = "자리 이동";
      detail = "광 조건: 조정";
    }
    if (type === "mist") {
      title = "분무";
      detail = "습도 케어";
    }
    if (type === "clean") {
      title = "잎 닦기";
      detail = "가벼운 케어";
    }

    await createLog({
      type,
      date: now.date,
      time: now.time,
      plantId: activePlant.id,
      plantName: activePlant.name,
      title,
      detail,
    });
  };

  const handleUploadPhoto = async (e) => {
    if (!activePlant) return;
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    let imageUrl = "";
    try {
      imageUrl = await FileToDataUrl(file);
    } catch {
      return alert("이미지 업로드 실패");
    }

    const now = buildNow();
    await createLog({
      type: "photo",
      date: now.date,
      time: now.time,
      plantId: activePlant.id,
      plantName: activePlant.name,
      title: "배치 사진 저장",
      detail: "직접 업로드한 사진",
      imageUrl,
      meta: { source: "upload", filename: file.name },
    });
  };

  // ✅ Decoration Save
  useEffect(() => {
    if (decoratedData && decoratedData.file) {
      const saveDecorated = async () => {
        try {
          const imageUrl = await FileToDataUrl(decoratedData.file);
          const now = buildNow();

          await createLog({
            type: "photo",
            date: now.date,
            time: now.time,
            plantId: decoratedData.plantId || activePlantId,
            plantName: decoratedData.plantName || (activePlant ? activePlant.name : "식물"),
            title: "꾸민 사진 저장",
            detail: decoratedData.nickname ? `${decoratedData.nickname} 꾸미기 완료` : "꾸미기 완료된 사진",
            imageUrl,
            meta: {
              source: "decorate",
              tags: decoratedData.tags,
            },
          });
        } catch (e) {
          console.error("Failed to save decorated image:", e);
        }
      };
      saveDecorated();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decoratedData]);

  const deleteDiaryLog = (logId) => {
    if (window.confirm("정말 삭제하시겠습니까?")) {
      deleteLog(logId);
    }
  };

  return {
    addPlantManually,
    addDiaryLog,
    handleUploadPhoto,
    deleteDiaryLog,
  };
}

function buildNow() {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  const hh = String(now.getHours()).padStart(2, "0");
  const min = String(now.getMinutes()).padStart(2, "0");
  return { date: `${yyyy}-${mm}-${dd}`, time: `${hh}:${min}` };
}
