import { useState, useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import DiaryMainPage from "./DiaryMainPage";
import TimeLogPage from "./TimeLogPage";
import "./PlantBoard.css";
import DecorateContainer from "../../components/decorate/DecorateContainer";
import DiaryMiniPreview from "../../components/diary/DiaryMiniPreview";
import { fetchWithSession } from "../../services/session";
import iconTt from "../../assets/tamagotchi/plant_icons/튼튼이.png";
import iconStar from "../../assets/tamagotchi/plant_icons/별꽃이.png";
import iconLong from "../../assets/tamagotchi/plant_icons/쭉쭉이.png";
import iconFluffy from "../../assets/tamagotchi/plant_icons/복실이.png";
import iconVine from "../../assets/tamagotchi/plant_icons/꼬불이.png";
import emoteAnnoyed from "../../assets/tamagotchi/emotes/EMOTE_ANNOYED.png";
import emoteCalm from "../../assets/tamagotchi/emotes/EMOTE_CALM.png";
import emoteHappy from "../../assets/tamagotchi/emotes/EMOTE_HAPPY.png";
import emoteIdle from "../../assets/tamagotchi/emotes/EMOTE_IDLE.png";
import emoteMagical from "../../assets/tamagotchi/emotes/EMOTE_MAGICAL.png";
import emoteNeedy from "../../assets/tamagotchi/emotes/EMOTE_NEEDY.png";
import emoteProud from "../../assets/tamagotchi/emotes/EMOTE_PROUD.png";
import emoteSassy from "../../assets/tamagotchi/emotes/EMOTE_SASSY.png";
import emoteWorried from "../../assets/tamagotchi/emotes/EMOTE_WORRIED.png";
import tamagotchiTabImg from "../../assets/tamagotchi/tamagotchi_tab.png";

const PlantBoard = () => {
  const location = useLocation();
  const [activeView, setActiveView] = useState(
    () => localStorage.getItem("plantboard_active_view") || "timelog"
  ); // 'timelog' | 'tamagotchi' | 'diary' | 'decorate'
  const [selectedPlant, setSelectedPlant] = useState(
    () => {
      try {
        const raw = localStorage.getItem("plantboard_selected_plant");
        return raw ? JSON.parse(raw) : null;
      } catch {
        return null;
      }
    }
  );
  const [diaryKey, setDiaryKey] = useState(0);

  // Decoration state
  const [decorateItem, setDecorateItem] = useState(null);
  const [decoratedResult, setDecoratedResult] = useState(null);
  const [charPos, setCharPos] = useState({ x: 60, y: 70 });
  const [charJump, setCharJump] = useState(false);
  const [tamaState, setTamaState] = useState(null);

  // Reset decorate state when entering the plantboard route (e.g. from Header)
  useEffect(() => {
    setDecorateItem(null);
    setDecoratedResult(null);
  }, [location]);

  useEffect(() => {
    localStorage.setItem("plantboard_active_view", activeView);
  }, [activeView]);

  useEffect(() => {
    if (selectedPlant) {
      localStorage.setItem("plantboard_selected_plant", JSON.stringify(selectedPlant));
    } else {
      localStorage.removeItem("plantboard_selected_plant");
    }
  }, [selectedPlant]);

  const ensurePixelRoomImage = async (plant) => {
    if (!plant || !plant.roomImageUrl || plant.roomImagePixelUrl) return plant;
    try {
      const res = await fetchWithSession("/api/plantboard/room_pixel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageUrl: plant.roomImageUrl, plantId: plant.id }),
      });
      const data = await res.json();
      if (data.ok && data.url) {
        return data.plant ? data.plant : { ...plant, roomImagePixelUrl: data.url };
      }
    } catch (e) {
      console.error("Failed to build pixel room image:", e);
    }
    return plant;
  };

  const ensureAllPixelRooms = async () => {
    try {
      const res = await fetchWithSession("/api/plantboard/room_pixel_all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: true }),
      });
      const data = await res.json();
      if (data.ok && Array.isArray(data.items) && selectedPlant) {
        const next = data.items.find((p) => p.id === selectedPlant.id);
        if (next) setSelectedPlant(next);
      }
    } catch (e) {
      console.error("Failed to build pixel room images:", e);
    }
  };

  useEffect(() => {
    if (activeView === "tamagotchi") {
      ensureAllPixelRooms();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView]);

  useEffect(() => {
    if (activeView !== "tamagotchi" || !selectedPlant) return;

    const rand = (min, max) => Math.random() * (max - min) + min;
    let mounted = true;

    const move = () => {
      if (!mounted) return;
      setCharPos({ x: rand(10, 80), y: rand(45, 80) });
      setCharJump(true);
      window.setTimeout(() => {
        if (mounted) setCharJump(false);
      }, 450);
    };

    move();
    const timer = window.setInterval(move, 5200 + Math.random() * 1800);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [activeView, selectedPlant]);

  useEffect(() => {
    if (!selectedPlant || activeView !== "tamagotchi") {
      setTamaState(null);
      return;
    }

    let mounted = true;
    const run = async () => {
      try {
        const res = await fetchWithSession("/api/tamagotchi/state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plant_id: selectedPlant.id }),
        });
        const data = await res.json();
        if (!mounted) return;
        if (data?.ok && data?.state) {
          setTamaState(data.state);
        } else if (data?.ok && data?.output) {
          setTamaState(data.output);
        } else {
          setTamaState(null);
        }
      } catch (e) {
        if (mounted) setTamaState(null);
      }
    };
    run();

    return () => {
      mounted = false;
    };
  }, [selectedPlant, activeView]);

  const getPlantIcon = (plant) => {
    if (!plant) return null;
    if (plant.characterImageUrl) return plant.characterImageUrl;
    const raw =
      plant.characterName ||
      plant.character ||
      plant.characterId ||
      plant.character_key ||
      "";
    const key = String(raw).toLowerCase();
    const map = {
      // New asset names (Korean character names)
      "튼튼이": iconTt,
      "별꽃이": iconStar,
      "쭉쭉이": iconLong,
      "복실이": iconFluffy,
      "꼬불이": iconVine,
      // Legacy keys (keep backward compatibility)
      plant_icon_1: iconTt,
      icon1: iconTt,
      "1": iconTt,
      plant_icon_2: iconStar,
      icon2: iconStar,
      "2": iconStar,
      plant_icon_3: iconLong,
      icon3: iconLong,
      "3": iconLong,
      plant_icon_4: iconFluffy,
      icon4: iconFluffy,
      "4": iconFluffy,
      plant_icon_5: iconVine,
      icon5: iconVine,
      "5": iconVine,
    };
    return map[key] || null;
  };

  const getEmoteOverlay = (emote) => {
    const map = {
      HAPPY: emoteHappy,
      NEEDY: emoteNeedy,
      ANNOYED: emoteAnnoyed,
      WORRIED: emoteWorried,
      CALM: emoteCalm,
      PROUD: emoteProud,
      MAGICAL: emoteMagical,
      SASSY: emoteSassy,
      IDLE: emoteIdle,
    };
    return map[emote] || emoteIdle;
  };

  const bubbleStyle = useMemo(() => {
    if (!selectedPlant) return { left: "8%", top: "8%" };
    const clamp = (val, min, max) => Math.max(min, Math.min(max, val));
    const left = clamp(charPos.x - 10, 6, 78);
    const top = clamp(charPos.y - 22, 8, 75);
    return { left: `${left}%`, top: `${top}%` };
  }, [charPos, selectedPlant]);

  const viewTitle = useMemo(() => {
    if (activeView === "tamagotchi") return "TAMAGOTCHI";
    if (activeView === "diary") return "DIARY";
    return "TIME LOG";
  }, [activeView]);

  return (
    <div className="plantboard-container">
      {/* Sidebar Area */}
      <aside className="plantboard-sidebar">
        {/* Compact Log Tab at the very top */}
        <div
          className={`sidebar-compact-tab ${activeView === "timelog" ? "active" : ""}`}
          onClick={() => {
            setActiveView("timelog");
            setDecorateItem(null);
          }}
        >
          LOG
        </div>

        <div
          className={`sidebar-section sidebar-section--tamagotchi ${activeView === "tamagotchi" ? "active" : ""} ${!selectedPlant ? "is-disabled" : ""}`}
          onClick={() => {
            if (!selectedPlant) return;
            setActiveView("tamagotchi");
            setDecorateItem(null);
            ensurePixelRoomImage(selectedPlant).then((next) => {
              if (next && next !== selectedPlant) setSelectedPlant(next);
            });
          }}
        >
          <div className="sidebar-label">TAMAGOTCHI</div>
          <div className="sidebar-content tamagotchi-placeholder">
            {selectedPlant ? (
              <div className="placeholder-box">
                {selectedPlant.roomImagePixelUrl || selectedPlant.roomImageUrl ? (
                  <img
                    src={selectedPlant.roomImagePixelUrl || selectedPlant.roomImageUrl}
                    alt={`${selectedPlant.name} room`}
                    className="tamagotchi-room-img"
                  />
                ) : null}
              </div>
            ) : (
              <div className="placeholder-box">
                <img
                  src={tamagotchiTabImg}
                  alt="tamagotchi tab placeholder"
                  className="tamagotchi-room-img"
                />
                <p className="tamagotchi-placeholder-text">식물을 선택하세요</p>
              </div>
            )}
          </div>
        </div>

        <div
          className={`sidebar-section sidebar-section--diary ${activeView === "diary" ? "active" : ""}`}
          onClick={() => {
            if (activeView === "diary") {
              setDiaryKey((prev) => prev + 1);
            }
            setActiveView("diary");
            setDecorateItem(null);
          }}
        >
          <div className="sidebar-label">DIARY</div>
          <div className="sidebar-content diary-preview">
            <DiaryMiniPreview />
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="plantboard-main">
        {(activeView === "timelog" || activeView === "tamagotchi" || activeView === "diary") && (
          <div className="plantboard-view-header">
            <h2 className="plantboard-view-title">{viewTitle}</h2>
          </div>
        )}

        {activeView === "timelog" && (
          <TimeLogPage
            onEnterDecorate={(item) => {
              setDecorateItem(item);
              setActiveView("decorate");
              setDecoratedResult(null);
            }}
            decoratedData={decoratedResult}
            initialActivePlantId={selectedPlant?.id || ""}
            onSelectPlant={(plant) => {
              setSelectedPlant(plant);
            }}
            showHeader={false}
            showControls={true}
            showTimeline={true}
            showActionBar={true}
          />
        )}

        {activeView === "tamagotchi" && (
          <TimeLogPage
            onEnterDecorate={(item) => {
              setDecorateItem(item);
              setActiveView("decorate");
              setDecoratedResult(null);
            }}
            decoratedData={decoratedResult}
            initialActivePlantId={selectedPlant?.id || ""}
            onSelectPlant={(plant) => {
              setSelectedPlant(plant);
            }}
            showHeader={false}
            showControls={true}
            showTimeline={false}
            showActionBar={true}
            enableFiltering={false}
            mode="tamagotchi"
            filterTabs={[
              { key: "water", label: "물 주기" },
              { key: "fertilizer", label: "비료 주기" },
              { key: "move", label: "자리 이동" },
              { key: "mist", label: "분무" },
              { key: "clean", label: "청소" },
            ]}
          >
            <div className="tamagotchi-view-placeholder">
              {selectedPlant ? (
                <>
                  <div className="tamagotchi-room">
                    {selectedPlant.roomImagePixelUrl || selectedPlant.roomImageUrl ? (
                      <img
                        src={selectedPlant.roomImagePixelUrl || selectedPlant.roomImageUrl}
                        alt={`${selectedPlant.name} room`}
                        className="tamagotchi-room-img"
                      />
                    ) : null}
                    <div className="tamagotchi-bubble tamagotchi-bubble--room" style={bubbleStyle}>
                      {tamaState?.text || "반응 데이터를 기다리는 중이야."}
                    </div>
                    {getPlantIcon(selectedPlant) ? (
                      <div
                        className={`tamagotchi-character ${charJump ? "is-jump" : ""} anim-${tamaState?.animation || "idle"}`}
                        style={{ left: `${charPos.x}%`, top: `${charPos.y}%` }}
                      >
                        <img
                          src={getPlantIcon(selectedPlant)}
                          alt={`${selectedPlant.name} character`}
                          className="tamagotchi-character__base"
                        />
                        <img
                          src={getEmoteOverlay(tamaState?.emote || "IDLE")}
                          alt={`${selectedPlant.name} emote`}
                          className="tamagotchi-character__emote"
                        />
                      </div>
                    ) : null}
                  </div>
                  <div className="tamagotchi-panel">
                    <div className="tamagotchi-meta">
                      <span className="tama-pill">emote: {tamaState?.emote || "IDLE"}</span>
                      <span className="tama-pill">animation: {tamaState?.animation || "idle"}</span>
                    </div>
                    <div className="tamagotchi-tags">
                      {(tamaState?.tags || ["bucket:IDLE"]).map((tag) => (
                        <span key={tag} className="tama-tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p>식물을 먼저 선택해 주세요.</p>
              )}
            </div>
          </TimeLogPage>
        )}

        {activeView === "diary" && <DiaryMainPage key={diaryKey} />}
        {activeView === "decorate" && (
          <DecorateContainer
            item={decorateItem}
            onCancel={() => {
              setActiveView("timelog");
              setDecorateItem(null);
            }}
            onSave={(decoratedData) => {
              setDecoratedResult({
                ...decoratedData,
                plantId: decorateItem?.plantId,
                plantName: decorateItem?.plantName,
              });
              setActiveView("timelog");
              setDecorateItem(null);
            }}
          />
        )}
      </main>
    </div>
  );
};

export default PlantBoard;
