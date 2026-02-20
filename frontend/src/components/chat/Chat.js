import { useEffect, useMemo, useRef, useState } from "react";
import Button from "../common/Button";
import { fetchWithSession } from "../../services/session";
import "./Chat.css";

const API_BASE = "http://localhost:8000/api/chat";
const API_ROOT = API_BASE.replace(/\/api\/chat$/, "");
const IMAGE_API = `${API_BASE}/image`;
const RESULTS_API = `${API_BASE}/results`;
const SCENES_API = `${API_BASE.replace(/\/api\/chat$/, "")}/api/chat/scenes`;
const SCENES_API_ALL = `${API_BASE.replace(/\/api\/chat$/, "")}/api/chat/scenes/all`;
// const SPOT_API = `${API_BASE}/spot`;
const ANALYZE_API = `${API_BASE}/analyze`;
const RENDER_API = `${API_BASE}/render`;
const RECOMMEND_API = `${API_BASE}/recommend`;

function normalizeCvResult(raw) {
  const out = raw && typeof raw === "object" ? raw : {};
  const spots = Array.isArray(out.spots) ? out.spots : [];
  const best = out.best_spot ?? spots[0] ?? null;

  return {
    ...out,
    spots,
    best_spot: best,
    window: out.window ?? null,
    pnp: out.pnp ?? null,
    scene: out.scene ?? null,
  };
}

const normalizeMessages = (payload) => {
  if (!payload) return [];
  const raw = Array.isArray(payload) ? payload : payload.messages || payload.data || [];

  return raw
    .filter((item) => {
      if (!item) return false;
      // ✅ text가 없어도 images가 있으면 살린다
      if (item.text) return true;
      if (Array.isArray(item.images) && item.images.length > 0) return true;
      // ✅ scene_required 같은 payload-only도 살린다
      if (item.payload) return true;
      return false;
    })
    .map((item, index) => ({
      id: item.id || `${Date.now()}-${index}`,
      role: item.role || "bot",
      text: item.text,
      timestamp: item.timestamp || null,
      type: item.type,
      images: item.images,
      payload: item.payload,
    }));
};



const normalizePayload = (data) => {
  if (!data) return null;

  const messagePayload =
    Array.isArray(data.messages) ? data.messages.find((m) => m && m.payload)?.payload : null;

  const raw =
    data.payload ||
    data.data?.payload ||
    messagePayload ||
    (data.photos ? data : null);

  if (!raw) return null;

  const resolvedInput =
    raw.input ||
    (raw.input_type
      ? {
        type: raw.input_type,
        placeholder: raw.input?.placeholder,
      }
      : null);

  const photos = Array.isArray(raw.photos) ? raw.photos : [];
  const attributeSchema = Array.isArray(raw.attributeSchema)
    ? raw.attributeSchema
    : photos[0]?.attributes
      ? Object.keys(photos[0].attributes).map((key) => ({
        key,
        label: key,
      }))
      : [];

  return {
    photos,
    attributeSchema,
    type: raw.type || "",
    groups: Array.isArray(raw.groups) ? raw.groups : [],
    question: raw.question || "",
    options: Array.isArray(raw.options) ? raw.options : [],
    input: resolvedInput,
  };
};

const formatTime = (timestamp) => {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
};

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [payload, setPayload] = useState(null);
  const [status, setStatus] = useState("idle");


  const [input, setInput] = useState("");
  const [imageFiles, setImageFiles] = useState([]);
  const [startHour, setStartHour] = useState("");
  const [endHour, setEndHour] = useState("");

  const [detailMode, setDetailMode] = useState(false);
  const [filterGroups, setFilterGroups] = useState([]);
  const [selectedFilters, setSelectedFilters] = useState({});
  const [filtersSent, setFiltersSent] = useState(false);

  const listRef = useRef(null);
  const endRef = useRef(null);

  const [lightboxImages, setLightboxImages] = useState([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const hasMessages = messages.length > 0;

  const [regenSpotImage, setRegenSpotImage] = useState(false);


  // =========================================================
  // ✅ Scene Select 상태 (합침)
  // =========================================================
  const [needSceneSelect, setNeedSceneSelect] = useState(false);
  const [sceneOptions, setSceneOptions] = useState([]);
  const [selectedScene, setSelectedScene] = useState("");
  const [pendingImageFile, setPendingImageFile] = useState(null); // 재전송용

  const [sceneErrorText, setSceneErrorText] = useState("");
  const [sceneSelectMode, setSceneSelectMode] = useState(null); // "scene" | "space" | null
  const [selectedSpace, setSelectedSpace] = useState("");
  const [spaceOptions, setSpaceOptions] = useState([]);

  const [showAltSpots, setShowAltSpots] = useState(false);
  const [altSpotCount, setAltSpotCount] = useState(0);
  const [selectedSpotIndex, setSelectedSpotIndex] = useState(0);
  const [cvResult, setCvResult] = useState(null);

  const statusText = useMemo(() => {
    if (status === "loading") return "서버 응답 대기중";
    if (status === "connected") return "실시간 연결됨";
    if (status === "error") return "연결 실패";
    return "대기중";
  }, [status]);

  const attributeGridTemplate = useMemo(() => {
    const count = payload?.attributeSchema?.length || 0;
    if (!count) return null;
    return {
      gridTemplateColumns: `minmax(0, 1.2fr) repeat(${count}, minmax(0, 1fr))`,
    };
  }, [payload]);

  const shouldRenderInlineDetailInput = false;

  const textInputPlaceholder =
    payload?.input?.placeholder || (detailMode ? "상세 내용을 입력해주세요" : "");

  const activeFilterGroups =
    payload?.type === "filters" && Array.isArray(payload?.groups) ? payload.groups : filterGroups;

  const isPlantSelect =
    payload?.type === "filters" &&
    Array.isArray(payload?.groups) &&
    payload.groups.some((group) => group.key === "plants");

  const handlePickAltSpot = async (spotIndex) => {
    setSelectedSpotIndex(spotIndex);
    setStatus("loading");

    // UX: 사용자가 뭘 눌렀는지 메시지로 남김(선택)
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-spot`,
        role: "user",
        text: `다른 후보 보기: ${spotIndex + 1}`,
        timestamp: Date.now(),
      },
    ]);

    try {
      // const res = await fetchWithSession(SPOT_API, {
      const res = await fetchWithSession(RENDER_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spot_index: spotIndex,
          regen: regenSpotImage, // ✅ 체크박스 값
        }),
      });

      if (!res.ok) throw new Error("failed");

      const data = await res.json();

      // ✅ 메시지/이미지 반영
      const incoming = normalizeMessages(data);
      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);

      // ✅ cv_result도 갱신(있으면)
      const cvRaw =
        data?.cv_result ??
        data?.data?.cv_result ??
        data?.payload?.cv_result ??
        data?.result ??
        data?.data?.result ??
        null;

      // if (cvRaw) setCvResult(normalizeCvResult(cvRaw));

      setStatus("connected");
    } catch (e) {
      setStatus("error");
    }
  };

  
  // -----------------------------
  // ✅ 필터 요약 + 전송
  // -----------------------------
  const buildFilterSummary = () => {
    const groups = activeFilterGroups.length > 0 ? activeFilterGroups : filterGroups;
    const parts = groups
      .map((group) => {
        const values = selectedFilters[group.key] || [];
        if (values.length === 0) return null;
        return `${group.label}: ${values.join(", ")}`;
      })
      .filter(Boolean);

    if (parts.length === 0) return "선택한 속성 없음";
    return parts.join(" / ");
  };

  // =========================================================
  // ✅ scene list fetch (필요할 때만)
  // =========================================================
  const fetchScenesIfNeeded = async () => {
    if (sceneOptions.length > 0) return;
    try {
      const res = await fetchWithSession(SCENES_API, { method: "GET" });
      if (!res.ok) throw new Error("failed");
      const data = await res.json();

      // ✅ 백엔드 /api/chat/scenes 는 scenes가 아니라 options를 준다
      if (data?.ok && Array.isArray(data?.options)) {
        // room group options({key,label})를 spaceOptions로 넣는 게 맞다
        setSpaceOptions(data.options.map((x) => ({ id: String(x.key), label: String(x.label) })));
      }
    } catch (e) {
      setSceneErrorText(
        "scene 목록을 불러오지 못했습니다. 백엔드의 /api/chat/scenes 라우트를 확인해주세요."
      );
    }
  };

  const normalizeSceneOptions = (arr) => {
    if (!Array.isArray(arr)) return [];
    return arr
      .map((s) => {
        if (!s) return null;
        // ✅ 백엔드가 string 주는 경우도 커버
        if (typeof s === "string") return { id: s, label: s };
        // ✅ 백엔드가 {id,label} 주는 경우
        if (typeof s === "object") {
          const id = String(s.id ?? s.scene_id ?? s.value ?? "").trim();
          const label = String(s.label ?? s.name ?? id).trim();
          if (!id) return null;
          return { id, label };
        }
        return null;
      })
      .filter(Boolean);
  };

  // =========================================================
  // ✅ 서버 메시지에서 scene_required 감지
  // =========================================================
  const detectSceneRequired = (incomingMessages = []) => {
    for (const m of incomingMessages) {
      const p = m?.payload;
      if (!p) continue;

      // ✅ 1) space_required (거실/침실/욕실/주방)
      if (p.type === "space_required") {
        const opts = Array.isArray(p.options) ? p.options : [];
        setSpaceOptions(opts.map((x) => ({ id: String(x), label: String(x) })));
        setSelectedSpace("");
        setSceneSelectMode("space");

        setNeedSceneSelect(true);
        setSceneErrorText(p.message || "이 사진이 어떤 공간인지 선택해주세요.");
        return true;
      }

      // ✅ 2) scene_required (residence_house_... 같은 씬)
      if (p.type === "scene_required") {
        if (Array.isArray(p.scenes) && p.scenes.length > 0) {
          setSceneOptions(normalizeSceneOptions(p.scenes));
        } else {
          fetchScenesIfNeeded();
        }
        setSelectedScene("");
        setSceneSelectMode("scene");

        setNeedSceneSelect(true);
        setSceneErrorText(p.message || "이 사진은 공간(scene) 선택이 필요합니다.");
        return true;
      }

      // ✅ 3) room_type_required (거실/침실/주방/욕실)
      if (p.type === "room_type_required") {
        const opts = Array.isArray(p.options) ? p.options : [];
        setSpaceOptions(opts.map((x) => ({ id: String(x), label: String(x) }))); 
        setSelectedSpace("");
        setSceneSelectMode("room_type"); 
        setNeedSceneSelect(true);
        setSceneErrorText(
          p.message ||
            "이 사진의 공간 유형을 선택해주세요. (선택하면 그 공간에 맞춰 다시 분석합니다)"
        );
        return true;
      }


    }
    return false;
  };


  const detectAiEditArrived = (incomingMessages = []) => {
    return incomingMessages.some((m) => {
      if (!Array.isArray(m?.images)) return false;
      return m.images.some((img) => {
        const name = String(img?.name || "");
        const url = String(img?.url || "");
        return name === "ai_edit" || name.includes("ai_edit") || url.includes("ai_edit");
      });
    });
  };


  const sendWithFilters = async () => {
    setFiltersSent(false);

    const summaryText = buildFilterSummary();

    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-filter`,
        role: "user",
        text: summaryText,
        timestamp: Date.now(),
      },
    ]);

    setStatus("loading");
    try {
      // const response = await fetchWithSession(API_BASE, {
      const response = await fetchWithSession(RECOMMEND_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filters: { ...selectedFilters },
          meta: { lat: 37.5665, lot: 126.9780, hhmm: "1200" }, // 임시 고정값
        }),
      });
      if (!response.ok) throw new Error("failed");

      const data = await response.json();

      const savedImage =
        data?.saved_image ||
        data?.data?.saved_image ||
        data?.payload?.saved_image ||
        null;
      if (savedImage) {
        sessionStorage.setItem("room_image_url", `${API_ROOT}/uploads/${savedImage}`);
        sessionStorage.setItem("room_image_filename", savedImage);
      }

      // ✅ (합침) cv_result 파싱/정규화
      const cvRaw =
        data?.cv_result ??
        data?.data?.cv_result ??
        data?.payload?.cv_result ??
        data?.result ??
        data?.data?.result ??
        null;

      const cv = normalizeCvResult(cvRaw);
      setCvResult(cvRaw ? cv : null);

      if (cv?.best_spot?.pt) {
        const [px, py] = cv.best_spot.pt;
        const spotsCount = Array.isArray(cv.spots) ? cv.spots.length : 0;

        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-cv-summary`,
            role: "bot",
            text: `✅ 추천 위치가 계산됐어요!\n- Best: (${px}, ${py})\n- 후보 개수: ${spotsCount}개`,
            timestamp: Date.now(),
          },
        ]);
      } else if (cvRaw) {
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-cv-summary-warn`,
            role: "bot",
            text: `⚠️ CV 결과는 받았지만(best_spot 없음) 표시할 추천 좌표를 찾지 못했어요. (응답 스키마 확인 필요)`,
            timestamp: Date.now(),
          },
        ]);
      }

      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setStatus("connected");
      setFiltersSent(true);
    } catch (e) {
      setStatus("error");
      setFiltersSent(false);
    }
  };

  const handleOptionSelect = async (option) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user`,
        role: "user",
        text: option,
        timestamp: Date.now(),
      },
    ]);

    setStatus("loading");
    try {
      const response = await fetchWithSession(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: option,
          filters: { ...selectedFilters },
        }),
      });

      if (!response.ok) throw new Error("failed");

      const data = await response.json();
      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setStatus("connected");
    } catch (e) {
      setStatus("error");
    }
  };

  // -----------------------------
  // 기본 초기 로딩: /api/chat (step1)
  // -----------------------------
  useEffect(() => {
    const fetchMessages = async () => {
      setStatus("loading");
      try {
        const response = await fetchWithSession(API_BASE, { method: "GET" });
        if (!response.ok) throw new Error("failed");

        const data = await response.json();
        const nextMessages = normalizeMessages(data);
        const nextPayload = normalizePayload(data);

        setMessages(nextMessages);
        if (nextPayload) setPayload(nextPayload);

        setStatus("connected");
      } catch (error) {
        setStatus("error");
      }
    };

    fetchMessages();
  }, []);

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const response = await fetchWithSession(RESULTS_API, { method: "GET" });
        if (!response.ok) return;
        const data = await response.json();
        if (!data?.images?.length) return;
        setMessages((prev) => {
          if (prev.some((msg) => msg.id === "latest-results")) return prev;
          return [
            ...prev,
            {
              id: "latest-results",
              role: "bot",
              type: "images",
              images: data.images,
              text: "latest-results",
              timestamp: Date.now(),
            },
          ];
        });
      } catch (error) {
        // ignore
      }
    };

    fetchResults();
  }, []);

  // 필터 그룹 로딩
  useEffect(() => {
    const fetchFilters = async () => {
      try {
        const response = await fetchWithSession(`${API_BASE}/filters`);
        if (!response.ok) throw new Error("failed");
        const data = await response.json();

        if (Array.isArray(data?.groups)) {
          setFilterGroups(data.groups);
          setSelectedFilters(
            data.groups.reduce((acc, group) => {
              acc[group.key] = [];
              return acc;
            }, {})
          );
        }
      } catch (error) {
        // keep defaults
      }
    };

    fetchFilters();
  }, []);

  // payload photos 들어오면 payload-block 추가
  useEffect(() => {
    if (!payload?.photos?.length) return;
    setMessages((prev) => {
      if (prev.some((message) => message.id === "payload-block")) return prev;
      return [...prev, { id: "payload-block", role: "bot", type: "payload" }];
    });
  }, [payload]);

  // payload의 filters 그룹이 바뀌면 선택 상태 초기화(키 유지)
  useEffect(() => {
    if (payload?.type !== "filters" || !Array.isArray(payload?.groups)) return;
    const groupKeys = payload.groups.map((group) => group.key);
    setSelectedFilters((prev) => {
      const next = {};
      groupKeys.forEach((key) => {
        next[key] = prev[key] || [];
      });
      return next;
    });
    setFiltersSent(false);
  }, [payload?.type, payload?.groups]);

  useEffect(() => {
    if (payload?.type === "filters") setFiltersSent(false);
  }, [payload?.type, payload?.groups, isPlantSelect]);

  // 스크롤
  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!endRef.current) return;
    endRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, payload, detailMode]);

  // 라이트박스
  const openLightbox = (images, index) => {
    if (!images.length) return;
    setLightboxImages(images);
    setLightboxIndex(index);
  };

  const closeLightbox = () => {
    setLightboxImages([]);
    setLightboxIndex(0);
  };

  const showPrev = (event) => {
    event.stopPropagation();
    setLightboxIndex((prev) => (prev === 0 ? lightboxImages.length - 1 : prev - 1));
  };

  const showNext = (event) => {
    event.stopPropagation();
    setLightboxIndex((prev) => (prev === lightboxImages.length - 1 ? 0 : prev + 1));
  };

  const handleDownload = () => {
    const item = lightboxImages[lightboxIndex];
    if (!item?.url) return;
    const link = document.createElement("a");
    link.href = item.url;
    link.download = item.name || "image";
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  // SSE
  useEffect(() => {
    const source = new EventSource(`${API_BASE}/stream`);

    const onHeartbeat = () => {
      setStatus("connected");
    };

    source.addEventListener("heartbeat", onHeartbeat);

    source.onmessage = (event) => {
      if (!event?.data) return;

      let data;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        return;
      }

      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setStatus("connected");
    };

    source.onerror = () => {
      setStatus("error");
      source.close();
    };

    return () => {
      source.removeEventListener("heartbeat", onHeartbeat);
      source.close();
    };
  }, []);

  // 텍스트 전송
  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;

    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-input`,
        role: "user",
        text: trimmed,
        timestamp: Date.now(),
      },
    ]);

    setStatus("loading");
    try {
      const response = await fetchWithSession(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: trimmed,
          filters: { ...selectedFilters },
        }),
      });
      if (!response.ok) throw new Error("failed");

      const data = await response.json();
      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setInput("");
      setStatus("connected");
    } catch (error) {
      setStatus("error");
    }
  };

  // 이미지 선택
  const handleImageChange = (event) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    setImageFiles(files);

    // ✅ scene 재전송 대비: 첫 파일 기억
    if (files.length > 0) {
      setPendingImageFile(files[0]);
      setNeedSceneSelect(false);
      setSelectedScene("");
      setSceneErrorText("");
    }
  };

  const sendRoomTypeReanalyze = async (roomType) => {
    const rt = String(roomType || "").trim();
    if (!rt) return;

    const fileToSend = imageFiles.length > 0 ? imageFiles[0] : pendingImageFile;
    if (!fileToSend) {
      alert("재분석할 이미지가 없습니다. 다시 업로드해주세요.");
      return;
    }

    // UX: 사용자가 뭘 눌렀는지 남김
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-roomtype`,
        role: "user",
        text: `공간 선택: ${rt}`,
        timestamp: Date.now(),
      },
    ]);

    const formData = new FormData();
    formData.append("image", fileToSend);

    // 기존과 동일 meta
    formData.append(
      "meta",
      JSON.stringify({
        lat: 37.5665,
        lot: 126.978,
        label: `room_type=${rt} 재분석`,
      })
    );

    // ✅ 핵심: room_type 반드시 포함
    formData.append("room_type", rt);

    setStatus("loading");
    try {
      const response = await fetchWithSession(IMAGE_API, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error("failed");

      const data = await response.json();

      // scene_required 다시 뜨는지 먼저 감지
      const incoming = normalizeMessages(data);

      const needScene = detectSceneRequired(incoming);
      if (needScene) {
        setStatus("connected");
        return;
      }

      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setNeedSceneSelect(false);
      setSceneSelectMode(null);
      setSelectedSpace("");
      setSceneErrorText("");

      setStatus("connected");
    } catch (e) {
      setStatus("error");
    }
  };


  // ✅ 이미지 업로드 (sceneId optional)
  const handleImageSubmit = async (event, sceneId = null, spaceType = null) => {
    event.preventDefault();

    const fileToSend = imageFiles.length > 0 ? imageFiles[0] : pendingImageFile;
    if (!fileToSend) return;

    const label = `이미지 업로드 1장`;

    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-images`,
        role: "user",
        type: "images",
        images: [
          {
            name: fileToSend.name,
            url: URL.createObjectURL(fileToSend),
          },
        ],
        text: label,
        timestamp: Date.now(),
      },
    ]);

    const formData = new FormData();
    formData.append("image", fileToSend);

    formData.append(
      "meta",
      JSON.stringify({
        lat: 37.5665,
        lot: 126.9780,
        label,
        // hhmm: "0900",  // 필요하면
      })
    );

    // ✅ scene_id
    if (sceneId !== null && sceneId !== undefined && String(sceneId).trim() !== "") {
      formData.append("scene_id", String(sceneId));
    }

    // ✅ space_type
    // ✅ room_type (거실/침실/주방/욕실)
    if (spaceType !== null && spaceType !== undefined && String(spaceType).trim() !== "") {
      formData.append("room_type", String(spaceType));
    }

    console.log("[handleImageSubmit] sceneId =", sceneId);
    for (const [k, v] of formData.entries()) console.log("[FormData]", k, v);


    setStatus("loading");
    try {
      const response = await fetchWithSession(IMAGE_API, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error("failed");

      const data = await response.json();

      // ✅ (합침) cv_result 파싱/정규화 (이미지 업로드 응답에서)
      const cvRaw =
        data?.cv_result ??
        data?.data?.cv_result ??
        data?.payload?.cv_result ??
        data?.result ??
        data?.data?.result ??
        null;

      const cv = normalizeCvResult(cvRaw);
      setCvResult(cvRaw ? cv : null);

      if (cv?.best_spot?.pt) {
        const [px, py] = cv.best_spot.pt;
        const spotsCount = Array.isArray(cv.spots) ? cv.spots.length : 0;

        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-cv-summary-image`,
            role: "bot",
            text: `✅ 추천 위치가 계산됐어요!\n- Best: (${px}, ${py})\n- 후보 개수: ${spotsCount}개`,
            timestamp: Date.now(),
          },
        ]);
      } else if (cvRaw) {
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-cv-summary-image-warn`,
            role: "bot",
            text: `⚠️ CV 결과는 받았지만(best_spot 없음) 표시할 추천 좌표를 찾지 못했어요. (응답 스키마 확인 필요)`,
            timestamp: Date.now(),
          },
        ]);
      }

      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      // ✅ ai_edit 도착하면: 후보 버튼 노출 준비
      const aiEditArrived = detectAiEditArrived(incoming);
      if (aiEditArrived) {
        const spotsLen = Array.isArray(cv?.spots) ? cv.spots.length : 0;
        const cnt = Math.min(5, spotsLen || 5); // spots 없으면 일단 5 가정
        setAltSpotCount(cnt);
        setSelectedSpotIndex(0);
        setShowAltSpots(true);
      }

      // ✅ scene_required 감지 후 UI 띄우고 종료
      const needScene = detectSceneRequired(incoming);
      if (needScene) {
        setStatus("connected");
        return;
      }

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setImageFiles([]);
      setNeedSceneSelect(false);
      setSelectedScene("");
      setSceneErrorText("");

      setStatus("connected");
    } catch (error) {
      setStatus("error");
    }
  };

  // time_range 전송
  const handleTimeSubmit = async (event) => {
    event.preventDefault();
    if (startHour === "" || endHour === "") return;
    const label = `${startHour}시 ~ ${endHour}시`;

    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-time`,
        role: "user",
        text: label,
        timestamp: Date.now(),
      },
    ]);

    setStatus("loading");
    try {
      const response = await fetchWithSession(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: label,
          filters: { ...selectedFilters },
        }),
      });
      if (!response.ok) throw new Error("failed");

      const data = await response.json();
      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setStartHour("");
      setEndHour("");
      setStatus("connected");
    } catch (error) {
      setStatus("error");
    }
  };

  // 상세입력/마음에 들어요
  const handleDetailChoice = (choice) => {
    if (choice === "detail") {
      setDetailMode(true);
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-user-detail`,
          role: "user",
          text: "상세 입력할게요",
          timestamp: Date.now(),
        },
      ]);
      return;
    }
    setDetailMode(false);
    sendChoiceMessage("마음에 들어요");
  };

  const sendChoiceMessage = async (text) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-user-choice`,
        role: "user",
        text,
        timestamp: Date.now(),
      },
    ]);

    setStatus("loading");
    try {
      const response = await fetchWithSession(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          filters: { ...selectedFilters },
        }),
      });
      if (!response.ok) throw new Error("failed");

      const data = await response.json();
      const incoming = normalizeMessages(data);
      const nextPayload = normalizePayload(data);

      if (incoming.length) setMessages((prev) => [...prev, ...incoming]);
      if (nextPayload) setPayload(nextPayload);

      setStatus("connected");
    } catch (error) {
      setStatus("error");
    }
  };

  const toggleFilterOption = (groupKey, value) => {
    setFiltersSent(false);
    setSelectedFilters((prev) => {
      const current = prev[groupKey] || [];
      const next = current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value];
      return { ...prev, [groupKey]: next };
    });
  };

  // ✅ Scene/RoomType 선택 후 재분석 (override 지원)
  const handleSceneResubmit = async (e, overrideSpace = null) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    const fileToSend = imageFiles.length > 0 ? imageFiles[0] : pendingImageFile;
    if (!fileToSend) return;

    const fakeEvent = { preventDefault: () => {}, stopPropagation: () => {} };

    // ✅ room_type 도 space처럼 처리
    if (sceneSelectMode === "space" || sceneSelectMode === "room_type") {
      const st = String(overrideSpace ?? selectedSpace ?? "").trim();
      if (!st) return;

      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-user-space`, role: "user", text: `공간 선택: ${st}`, timestamp: Date.now() },
      ]);

      // handleImageSubmit의 3번째 인자를 "room_type" 용으로 사용
      await handleImageSubmit(fakeEvent, null, st);
      return;
    }

    // default: scene mode
    const sceneId = String(selectedScene || "").trim();
    if (!sceneId) return;

    setMessages((prev) => [
      ...prev,
      { id: `${Date.now()}-user-scene`, role: "user", text: `scene 선택: ${sceneId}`, timestamp: Date.now() },
    ]);

    await handleImageSubmit(fakeEvent, sceneId, null);
  };


  return (
    <div className="chatPage">
      <div className="chatShell">
        {/* Header */}
        <header className="chatHeader">
          <div className="chatHeader__title">
            <h2 className="chatHeader__h2">추천 AI</h2>
            <p className="chatHeader__p">고객님의 취향에 맞는 식물을 추천해드립니다.</p>
          </div>
          <div className="chatHeader__status">
            <span className={`chatStatusDot chatStatusDot--${status}`} />
            <span className="chatStatusText">{statusText}</span>
          </div>
        </header>

        {/* List */}
        <div className="chatList" ref={listRef}>
          {!hasMessages && <div className="chatEmpty">아직 수신된 메시지가 없습니다.</div>}

          {messages.map((message) => {
            const isUser = message.role === "user";
            const rowClass = isUser ? "msgRow msgRow--user" : "msgRow msgRow--bot";

            return (
              <div key={message.id} className={rowClass}>
                {/* bot avatar */}
                {!isUser && <div className="msgAvatar" aria-hidden />}

                {/* bubble area */}
                <div className="msgBody">
                  {message.type === "payload" && payload?.photos?.length ? (
                    <div className="payloadCard">
                      <div className="payloadCard__title">사진과 속성</div>

                      <div className="payloadGallery">
                        {payload.photos.map((photo, index) => (
                          <div key={photo.id || index} className="payloadGallery__item">
                            <div className="payloadGallery__label">
                              {photo.label || `사진 ${index + 1}`}
                            </div>

                            {photo.url || photo.imageUrl ? (
                              <img
                                className="payloadGallery__img"
                                src={photo.url || photo.imageUrl}
                                alt={photo.label || `사진 ${index + 1}`}
                                onClick={() =>
                                  openLightbox(
                                    payload.photos.map((item, idx) => ({
                                      name: item.label || `사진 ${idx + 1}`,
                                      url: item.url || item.imageUrl,
                                    })),
                                    index
                                  )
                                }
                              />
                            ) : (
                              <div className="payloadGallery__empty">이미지 없음</div>
                            )}
                          </div>
                        ))}
                      </div>

                      {payload.attributeSchema.length > 0 && (
                        <div className="payloadTable">
                          <div
                            className="payloadTable__head"
                            style={attributeGridTemplate || undefined}
                          >
                            <span className="payloadTable__th">사진</span>
                            {payload.attributeSchema.map((schema) => (
                              <span key={schema.key} className="payloadTable__th">
                                {schema.label}
                              </span>
                            ))}
                          </div>

                          {payload.photos.map((photo, index) => (
                            <div
                              key={photo.id || index}
                              className="payloadTable__row"
                              style={attributeGridTemplate || undefined}
                            >
                              <span className="payloadTable__td payloadTable__td--label">
                                {photo.label || `사진 ${index + 1}`}
                              </span>
                              {payload.attributeSchema.map((schema) => (
                                <span key={schema.key} className="payloadTable__td">
                                  {photo.attributes?.[schema.key] || "-"}
                                </span>
                              ))}
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="payloadActions">
                        <div className="payloadActions__q">
                          마음에 들지 않으면 상세 입력으로 이어갈까요?
                        </div>
                        <div className="payloadActions__btns">
                          <Button
                            type="option"
                            onClick={() => handleDetailChoice("ok")}
                            text="마음에 들어요"
                          />
                          <Button
                            type="primary"
                            onClick={() => handleDetailChoice("detail")}
                            text="상세 입력"
                          />
                        </div>
                      </div>
                    </div>
                  ) : message.type === "images" ? (
                    <div className="imgMsg">
                      <div className="imgMsg__grid">
                        {message.images?.map((image) => (
                          <button
                            key={image.url}
                            type="button"
                            className="imgMsg__item"
                            onClick={() =>
                              openLightbox(
                                message.images.map((item) => ({
                                  name: item.name,
                                  url: item.url,
                                })),
                                message.images.findIndex((item) => item.url === image.url)
                              )
                            }
                          >
                            <div className="imgMsg__name">{image.name}</div>
                            <img className="imgMsg__img" src={image.url} alt={image.name} />
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="msgBubble">{message.text}</div>
                      {message.timestamp && <div className="msgTime">{formatTime(message.timestamp)}</div>}
                    </>
                  )}
                </div>
              </div>
            );
          })}

          {/* ✅ scene_required UI (합침) */}
          {needSceneSelect && (
            <div className="filterPanel" style={{ marginTop: 12 }}>
              <div className="filterGroup">
                <div className="filterGroup__title">
                  {sceneSelectMode === "space" ? "[공간 타입 선택]"
                    : sceneSelectMode === "room_type" ? "[공간 유형 선택]"
                    : "[공간(scene) 선택 필요]"}
                </div>

                <div style={{ marginBottom: 8, opacity: 0.9 }}>
                  {sceneErrorText || "이 사진은 선택이 필요합니다."}
                </div>

                {/* ✅ room_type_required는 버튼 4개 */}
                {sceneSelectMode === "room_type" ? (
                  <div className="optionBar__grid">
                    {spaceOptions.map((opt) => (
                      <Button
                        key={opt.id}
                        type="option"
                        onClick={() => {
                          console.log("[ROOM_TYPE CLICK]", opt.id);
                          alert("clicked: " + opt.id);
                          sendRoomTypeReanalyze(opt.id);
                        }}
                        text={opt.label}
                      />
                    ))}
                  </div>
                ) : (
                  /* 기존 select UI 유지 */
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <select
                      value={sceneSelectMode === "space" ? selectedSpace : selectedScene}
                      onChange={(e) =>
                        sceneSelectMode === "space"
                          ? setSelectedSpace(e.target.value)
                          : setSelectedScene(e.target.value)
                      }
                      style={{ padding: 6, minWidth: 260 }}
                    >
                      <option value="">선택하세요</option>
                      {(sceneSelectMode === "space" ? spaceOptions : sceneOptions).map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.label || s.id}
                        </option>
                      ))}
                    </select>
                    <button type="button" onClick={handleSceneResubmit}>
                      다시 분석
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          
          {showAltSpots && altSpotCount > 0 && (
            <div className="optionBar" style={{ marginTop: 10 }}>
              <div style={{ marginBottom: 6, opacity: 0.9 }}>
                다른 후보 보기 (최대 {altSpotCount}개)
              </div>
              <div className="optionBar__grid">
                {Array.from({ length: altSpotCount }, (_, i) => i).map((idx) => (
                  <Button
                    key={`alt-spot-${idx}`}
                    type={idx === selectedSpotIndex ? "primary" : "option"}
                    onClick={() => handlePickAltSpot(idx)}
                    text={`후보 ${idx + 1}`}
                  />
                ))}
              </div>
            </div>
          )}

          <label style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0" }}>
            <input
              type="checkbox"
              checked={regenSpotImage}
              onChange={(e) => setRegenSpotImage(e.target.checked)}
            />
            같은 후보 다시 누르면 이미지 재생성
          </label>

          {/* 옵션 버튼 */}
          {payload?.options?.length > 0 && (
            <div className="optionBar">
              <div className="optionBar__grid">
                {payload.options.map((option) => (
                  <Button
                    key={option}
                    type="option"
                    onClick={() => handleOptionSelect(option)}
                    text={option}
                  />
                ))}
              </div>
            </div>
          )}

          {/* filters */}
          {payload?.type === "filters" && (
            <div className="filterPanel">
              {activeFilterGroups.map((group) => (
                <div key={group.key} className="filterGroup">
                  <div className="filterGroup__title">[{group.label}]</div>
                  <div className="filterGroup__options">
                    {group.options.map((option) => (
                      <label key={`${group.key}-${option}`} className="filterItem">
                        <input
                          className="filterItem__check"
                          type="checkbox"
                          checked={(selectedFilters[group.key] || []).includes(option)}
                          disabled={filtersSent}
                          onChange={() => toggleFilterOption(group.key, option)}
                        />
                        <span className="filterItem__text">{option}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}

              {!filtersSent && (
                <div className="filterPanel__send">
                  <button type="button" className="chatBtn" onClick={sendWithFilters}>
                    전송
                  </button>
                </div>
              )}
            </div>
          )}

          {/* text input */}
          {(payload?.input?.type === "text" || detailMode) && !shouldRenderInlineDetailInput && (
            <form className="composer" onSubmit={handleSubmit}>
              <input
                className="composer__input"
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={textInputPlaceholder}
              />
              <button className="chatBtn" type="submit">
                전송
              </button>
            </form>
          )}

          {/* time_range */}
          {payload?.input?.type === "time_range" && (
            <form className="composer composer--time" onSubmit={handleTimeSubmit}>
              <div className="timeRange">
                <label className="timeRange__field">
                  <span className="timeRange__label">시작</span>
                  <select
                    className="timeRange__select"
                    value={startHour}
                    onChange={(event) => setStartHour(event.target.value)}
                  >
                    <option value="">선택</option>
                    {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                      <option key={hour} value={hour}>
                        {hour}시
                      </option>
                    ))}
                  </select>
                </label>

                <span className="timeRange__dash">~</span>

                <label className="timeRange__field">
                  <span className="timeRange__label">종료</span>
                  <select
                    className="timeRange__select"
                    value={endHour}
                    onChange={(event) => setEndHour(event.target.value)}
                  >
                    <option value="">선택</option>
                    {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                      <option key={hour} value={hour}>
                        {hour}시
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <button className="chatBtn" type="submit">
                전송
              </button>
            </form>
          )}

          {/* image */}
          {payload?.input?.type === "image" && (
            <form className="composer composer--image" onSubmit={handleImageSubmit}>
              <label className="filePick">
                <input
                  className="filePick__input"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageChange}
                />
                <span className="filePick__text">
                  {imageFiles.length ? `선택된 이미지 ${imageFiles.length}장` : "공간 사진을 업로드해주세요"}
                </span>
              </label>

              <button className="chatBtn" type="submit">
                전송
              </button>
            </form>
          )}
          <div ref={endRef} />
        </div>

        {/* Lightbox */}
        {lightboxImages.length > 0 && (
          <div className="lightbox" onClick={closeLightbox}>
            <div className="lightbox__bar" onClick={(event) => event.stopPropagation()}>
              <button className="lightbox__btn" type="button" onClick={closeLightbox}>
                닫기
              </button>
              <button
                className="lightbox__btn"
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  handleDownload();
                }}
              >
                이미지 다운로드
              </button>

              {lightboxImages.length > 1 && (
                <>
                  <button className="lightbox__btn" type="button" onClick={showPrev}>
                    이전
                  </button>
                  <button className="lightbox__btn" type="button" onClick={showNext}>
                    다음
                  </button>
                </>
              )}
            </div>

            <div className="lightbox__stage" onClick={(event) => event.stopPropagation()}>
              <img
                className="lightbox__img"
                src={lightboxImages[lightboxIndex]?.url}
                alt={lightboxImages[lightboxIndex]?.name || "확대 이미지"}
              />
              {lightboxImages[lightboxIndex]?.name && (
                <div className="lightbox__name">{lightboxImages[lightboxIndex].name}</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
