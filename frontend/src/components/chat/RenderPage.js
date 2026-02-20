import { useEffect, useState } from "react";
import { fetchWithSession } from "../../services/session";

const API_BASE = "http://localhost:8000/api/chat";
const RENDER_API = `${API_BASE}/render`;
const RESULT_BASE = "http://localhost:8000";

export default function RenderPage() {
  const [loading, setLoading] = useState(true);
  const [spotImages, setSpotImages] = useState([]); // [{spot_index, url}]
  const [error, setError] = useState(null);
  const [savingSpot, setSavingSpot] = useState(null);
  const [saveMessage, setSaveMessage] = useState("");

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        setLoading(true);
        setError(null);

        // =========================================================
        // 1) 최신 분석 결과에서 spots 3개 가져오기
        // =========================================================
        const latestRes = await fetchWithSession(
          `${RESULT_BASE}/results/result_latest.json?t=${Date.now()}`,
          { method: "GET" }
        );
        if (!latestRes.ok) throw new Error("failed_to_load_result_latest");

        const latest = await latestRes.json();
        const spots = Array.isArray(latest?.spots) ? latest.spots : [];
        if (spots.length < 3) throw new Error("spots<3");

        // spots: result_latest.json의 latest.spots
        // render_plan: 백엔드(analyze)에서 넣어준 정책 { count, spot_indexes }
        const plan = latest?.render_plan;

        // 1) 기본은 기존처럼 3개
        let spotIndexes = spots.slice(0, 3).map((s, i) => {
          const v = s?.spot_index ?? s?.index ?? i;
          const n = Number(v);
          return Number.isFinite(n) ? n : i;
        });

        // 2) 테이블/바닥 정책이 있으면 plan 우선 적용
        if (plan?.count === 1 && Array.isArray(plan?.spot_indexes) && plan.spot_indexes.length >= 1) {
          const n = Number(plan.spot_indexes[0]);
          spotIndexes = [Number.isFinite(n) ? n : 0];
        }

        if (plan?.count === 3 && Array.isArray(plan?.spot_indexes) && plan.spot_indexes.length >= 3) {
          spotIndexes = plan.spot_indexes.slice(0, 3).map((v, i) => {
            const n = Number(v);
            return Number.isFinite(n) ? n : i;
          });
        }


        // =========================================================
        // 2) 선택한 식물 고정 (sessionStorage.selected_plant)
        //    너 스샷 기준: { id:"136", name:"...", image:"https://..." }
        // =========================================================
        const plantRaw = sessionStorage.getItem("selected_plant");
        if (!plantRaw) throw new Error("missing selected_plant");

        const plant = JSON.parse(plantRaw);
        const plant_name = plant?.name;
        if (!plant_name) throw new Error("missing plant_name");


        // sid는 있으면 같이 보내고, 없으면 생략
        const sid = localStorage.getItem("sid");

        console.log("render payload", { plant_name });


        // =========================================================
        // 3) render 1번 호출 (서버가 3개 스팟을 한 번에 내려줌)
        // =========================================================
        const r = await fetchWithSession(RENDER_API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...(sid ? { sid } : {}),
            // 백엔드가 spot_index 필수일 가능성 대응
            spot_index: spotIndexes[0],          // 예: 0
            // 3개 스팟을 명시적으로 전달 (백엔드가 받으면 이걸 우선 사용하게 됨)
            render_idxs: spotIndexes,            // 예: [0,5,4]

            plant_name,
            regen: true,
            mode: "ai_edit",
          }),
        });


        const j = await r.json().catch(() => null);
        if (!r.ok) {
          const msg = j?.detail || j?.message || "render_failed";
          throw new Error(msg);
        }

        console.log("[RENDER][response]", j);
        console.log("[RENDER][images_type]", Array.isArray(j?.images) ? typeof j.images[0] : "no_images");

        // ✅ 서버가 images 또는 spot_images 둘 중 어디로 보내든 받는다
        const arr =
          (Array.isArray(j?.images) && j.images) ||
          (Array.isArray(j?.spot_images) && j.spot_images) ||
          [];

        // ✅ 문자열 URL / 객체 둘 다 처리
        const imgs = arr.map((it, i) => {
          let rawUrl = null;
          let spotIndex = i;

          if (typeof it === "string") {
            rawUrl = it;
            spotIndex = i;
          } else if (it && typeof it === "object") {
            rawUrl = it.image_url || it.url || it.imageUrl || it.src || null;
            const n = Number(it.spot_index ?? it.spotIndex ?? i);
            spotIndex = Number.isFinite(n) ? n : i;
          }

          if (!rawUrl) {
            // 디버그용으로 응답을 같이 찍어라 (원인 확정)
            console.log("[RENDER][bad_item]", it);
            throw new Error(`missing image_url for spot ${spotIndex}`);
          }

          const url = rawUrl.startsWith("http") ? rawUrl : `${RESULT_BASE}${rawUrl}`;
          return { spot_index: spotIndex, url };
        });

        if (imgs.length < 1) {
          console.log("render response json =", j);
          throw new Error("missing images in render response");
        }

        setSpotImages(imgs);



      } catch (e) {
        if (!mounted) return;
        setError(String(e?.message || e));
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  const buildNow = () => {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const dd = String(now.getDate()).padStart(2, "0");
    const hh = String(now.getHours()).padStart(2, "0");
    const min = String(now.getMinutes()).padStart(2, "0");
    return { date: `${yyyy}-${mm}-${dd}`, time: `${hh}:${min}` };
  };

  const readSelectedPlant = () => {
    const plantRaw = sessionStorage.getItem("selected_plant");
    if (!plantRaw) return null;
    try {
      return JSON.parse(plantRaw);
    } catch {
      return null;
    }
  };

  const ensurePlant = async (payload, roomImageUrl) => {
    const listRes = await fetchWithSession("/api/plantboard/plants");
    const listData = await listRes.json();
    const list = Array.isArray(listData?.items) ? listData.items : [];

    const existing =
      list.find((p) => p.sourcePlantId === payload.id) ||
      list.find((p) => p.name === payload.name) ||
      null;
    if (existing) return existing;

    const plantData = {
      name: payload.name,
      sourcePlantId: payload.id,
      sourcePlantName: payload.name,
      image: payload.image,
      roomImageUrl: roomImageUrl || null,
      characterName: payload.characterName || null,
      personality: payload.personality || null,
    };

    const res = await fetchWithSession("/api/plantboard/plants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plant: plantData }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error("plant_create_failed");
    return data.item;
  };

  const ensureRoomPixel = async (roomImageUrl, plantId) => {
    if (!roomImageUrl || !plantId) return null;
    try {
      const res = await fetchWithSession("/api/plantboard/room_pixel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageUrl: roomImageUrl, plantId }),
      });
      const data = await res.json();
      if (data.ok && data.plant) return data.plant;
      if (data.ok && data.url) return { id: plantId, roomImagePixelUrl: data.url };
    } catch (e) {
      console.error("Failed to build room pixel:", e);
    }
    return null;
  };

  const handleSave = async (spot) => {
    if (!spot?.url) return;
    setSavingSpot(spot.url);
    setSaveMessage("");
    try {
      const selectedPlant = readSelectedPlant();
      if (!selectedPlant) throw new Error("missing selected_plant");

      const roomImageUrl = sessionStorage.getItem("room_image_url") || "";
      const plant = await ensurePlant(selectedPlant, roomImageUrl);
      const pixelResult = await ensureRoomPixel(roomImageUrl, plant?.id);
      const mergedPlant = pixelResult?.id ? { ...plant, ...pixelResult } : plant;

      const now = buildNow();
      const log = {
        type: "photo",
        date: now.date,
        time: now.time,
        title: "챗봇 결과 저장",
        detail: "AI 렌더 결과",
        imageUrl: spot.url,
        plantId: mergedPlant?.id || plant?.id,
        plantName: mergedPlant?.name || plant?.name || selectedPlant.name,
        plantImageUrl: mergedPlant?.image || selectedPlant.image || null,
        plantCharacterName: mergedPlant?.characterName || selectedPlant.characterName || null,
        plantPersonality: mergedPlant?.personality || selectedPlant.personality || null,
        roomImageUrl: roomImageUrl || null,
        roomImagePixelUrl: mergedPlant?.roomImagePixelUrl || null,
        sourcePlantId: selectedPlant.id || null,
      };

      const res = await fetchWithSession("/api/plantboard/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ log }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error("log_create_failed");

      if (mergedPlant?.id) {
        localStorage.setItem("plantboard_selected_plant", JSON.stringify(mergedPlant));
        localStorage.setItem("plantboard_active_view", "tamagotchi");
      }

      setSaveMessage("저장 완료. 타임로그에 추가했어요.");
    } catch (e) {
      setSaveMessage("저장 실패. 다시 시도해주세요.");
    } finally {
      setSavingSpot(null);
    }
  };

  return (
    <div className="render-page">
      <h2>AI 추천 스팟</h2>

      {loading && <div>이미지 생성 중...</div>}
      {error && <div style={{ color: "red" }}>{error}</div>}

      {!loading && !error && (
        <div className="spot-grid">
          {spotImages.map((it) => (
            <div className="spot-card" key={it.spot_index}>
              <img
                src={it.url}
                alt={`spot-${it.spot_index}`}
                style={{ width: "100%", borderRadius: 12 }}
              />
              <button
                type="button"
                className="ui-btn ui-btn-primary ui-btn--compact"
                style={{ marginTop: 12 }}
                disabled={savingSpot === it.url}
                onClick={() => handleSave(it)}
              >
                {savingSpot === it.url ? "저장 중..." : "타임로그에 저장"}
              </button>
            </div>
          ))}
        </div>
      )}
      {saveMessage && <div style={{ marginTop: 12 }}>{saveMessage}</div>}
    </div>
  );
}
