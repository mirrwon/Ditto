import { useEffect, useMemo, useRef, useState } from "react";
import html2canvas from "html2canvas";
import DecorateForm from "./DecorateForm";
import "./Decorate.css";

// 템플릿 이미지가 없을 경우를 대비하여 null로 설정 (파일이 생기면 assets에 넣고 import 해주세요)
const TEMPLATE_BG = null;
const TEMPLATE_PRESETS = [
    { id: "white", name: "기본", color: "#ffffff" },
    { id: "peach", name: "피치", color: "#ffe5d9" },
    { id: "lemon", name: "레몬", color: "#fff4cc" },
    { id: "mint", name: "민트", color: "#dff7f1" },
    { id: "sky", name: "스카이", color: "#e3f1ff" },
    { id: "lav", name: "라벤더", color: "#efe4ff" },
];
const EMOJI_STICKERS = [
    "🌿", "🌸", "🌼", "🍀", "🪴", "☀️", "✨", "💧",
    "🎀", "🌈", "⭐", "🍓", "🍑", "🍋", "🦋", "🐝",
    "🐞", "🐰", "🐣", "🌷", "🌻", "🌙", "🫧", "🍃",
];

const DECORATE_STORAGE_KEY = "decorate_state_v1";


/* dataURL -> Blob */
const dataUrlToBlob = async (dataUrl) => {
    const res = await fetch(dataUrl);
    return await res.blob();
};

const shuffle = (arr) => {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
};

/* stickers around photo frame */
const placeAround = (texts, frameW, frameH, photoRect) => {
    const pad = 18;
    const items = (texts || []).filter(Boolean);
    const MAX = 16;
    const list = items.slice(0, MAX);
    const jitter = (n) => (Math.random() * 2 - 1) * n;

    const sideGap = 26;
    const tagBoxW = 170;
    const minSideY = photoRect.y + 14;
    const maxSideY = photoRect.y + photoRect.h - 18;

    const sideRows = 4;
    const sideYs = Array.from({ length: sideRows }, (_, i) => {
        if (sideRows === 1) return (minSideY + maxSideY) / 2;
        return minSideY + ((maxSideY - minSideY) * i) / (sideRows - 1);
    });

    const leftLeft = Math.max(pad, photoRect.x - sideGap - tagBoxW);
    const rightRight = 22;

    const sideSlots = [
        ...sideYs.map((y) => ({ zone: "side", side: "left", left: leftLeft, top: y })),
        ...sideYs.map((y) => ({ zone: "side", side: "right", right: rightRight, top: y })),
    ];

    const belowGapTop = 22;
    const belowMinY = photoRect.y + photoRect.h + belowGapTop;
    const bottomSafe = 70;
    const belowMaxY = Math.min(frameH - pad - bottomSafe, belowMinY + 120);
    const belowEnabled = belowMaxY > belowMinY + 30;

    const belowCols = 3;
    const belowRows = 2;
    const belowSlots = [];

    if (belowEnabled) {
        const usableW = Math.min(frameW - pad * 2, photoRect.w + 80);
        const startX = Math.max(pad, photoRect.x + (photoRect.w - usableW) / 2);

        const colXs = Array.from({ length: belowCols }, (_, c) => {
            const t = belowCols === 1 ? 0.5 : c / (belowCols - 1);
            return startX + usableW * t;
        });

        const rowYs = Array.from({ length: belowRows }, (_, r) => {
            const t = belowRows === 1 ? 0.5 : r / (belowRows - 1);
            return belowMinY + (belowMaxY - belowMinY) * t;
        });

        rowYs.forEach((y) => {
            colXs.forEach((x) => {
                belowSlots.push({ zone: "below", side: "left", left: x, top: y, anchor: "center" });
            });
        });
    }

    const slots = shuffle([...sideSlots, ...belowSlots]);
    const xJ = list.length > 12 ? 4 : 8;
    const yJ = list.length > 12 ? 3 : 6;
    const rJ = list.length > 12 ? 1.2 : 2;

    return list.map((text, idx) => {
        const s = slots[idx % slots.length];
        const base = {
            id: `${Date.now()}-${idx}`,
            text,
            side: s.side,
            top: s.top + jitter(yJ),
            rotate: jitter(rJ),
            anchor: s.anchor || "start",
        };

        if (s.side === "right") {
            return { ...base, right: s.right + jitter(xJ) };
        }
        return { ...base, left: s.left + jitter(xJ) };
    });
};

const DecorateContainer = ({ item, onSave, onCancel }) => {
    const captureRef = useRef(null);
    const photoWrapRef = useRef(null);

    const [baseImageUrl, setBaseImageUrl] = useState(item?.imageUrl || "");
    const [plant, setPlant] = useState(item?.plant || null);

    const [nickname, setNickname] = useState("");
    const [dday, setDday] = useState("");

    const [customTags, setCustomTags] = useState([]);
    const [emojiStickers, setEmojiStickers] = useState([]);
    const allTags = useMemo(() => [...customTags, ...emojiStickers], [customTags, emojiStickers]);

    const [stickers, setStickers] = useState([]);
    const [resultImageUrl, setResultImageUrl] = useState("");
    const [status, setStatus] = useState("idle");
    const [templatePresetId, setTemplatePresetId] = useState(TEMPLATE_PRESETS[0].id);

    const activeTemplate = useMemo(
        () => TEMPLATE_PRESETS.find((t) => t.id === templatePresetId) || TEMPLATE_PRESETS[0],
        [templatePresetId]
    );

    const isGenerating = status === "generating";
    const isSaving = status === "saving";

    useEffect(() => {
        try {
            const raw = localStorage.getItem(DECORATE_STORAGE_KEY);
            if (!raw) return;
            const saved = JSON.parse(raw);
            if (saved?.baseImageUrl && item?.imageUrl && saved.baseImageUrl !== item.imageUrl) {
                return;
            }
            if (saved?.baseImageUrl) setBaseImageUrl(saved.baseImageUrl);
            if (saved?.nickname) setNickname(saved.nickname);
            if (saved?.dday) setDday(saved.dday);
            if (Array.isArray(saved?.customTags)) setCustomTags(saved.customTags);
            if (Array.isArray(saved?.emojiStickers)) setEmojiStickers(saved.emojiStickers);
            if (saved?.templatePresetId) setTemplatePresetId(saved.templatePresetId);
        } catch {}
    }, [item?.imageUrl]);

    useEffect(() => {
        try {
            const payload = {
                baseImageUrl,
                nickname,
                dday,
                customTags,
                emojiStickers,
                templatePresetId,
            };
            localStorage.setItem(DECORATE_STORAGE_KEY, JSON.stringify(payload));
        } catch {}
    }, [baseImageUrl, nickname, dday, customTags, emojiStickers, templatePresetId]);

    // 태그/이미지 레이아웃 변경 시 스티커 즉시 갱신
    useEffect(() => {
        if (!baseImageUrl) {
            setStickers([]);
            return;
        }

        const frameEl = captureRef.current;
        const photoEl = photoWrapRef.current;
        if (!frameEl || !photoEl) return;

        if (!allTags.length) {
            setStickers([]);
            return;
        }

        const raf = requestAnimationFrame(() => {
            const frameRect = frameEl.getBoundingClientRect();
            const photoRect = photoEl.getBoundingClientRect();

            if (!frameRect.width || !photoRect.width) return;

            const relativePhoto = {
                x: photoRect.left - frameRect.left,
                y: photoRect.top - frameRect.top,
                w: photoRect.width,
                h: photoRect.height,
            };

            const previewStickers = placeAround(
                allTags,
                frameRect.width,
                frameRect.height,
                relativePhoto
            );

            setStickers(previewStickers);
        });

        return () => cancelAnimationFrame(raf);
    }, [allTags, baseImageUrl]);


    const addCustomTag = (raw) => {
        const trimmed = (raw || "").trim();
        if (!trimmed) return;
        const tag = trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
        setCustomTags((prev) => (prev.includes(tag) ? prev : [...prev, tag]));
    };

    const removeCustomTag = (tag) => {
        setCustomTags((prev) => prev.filter((t) => t !== tag));
    };

    const addEmojiSticker = (emoji) => {
        setEmojiStickers((prev) => [...prev, emoji]);
    };

    const removeEmojiSticker = (emoji) => {
        setEmojiStickers((prev) => {
            const idx = prev.lastIndexOf(emoji);
            if (idx === -1) return prev;
            const next = [...prev];
            next.splice(idx, 1);
            return next;
        });
    };

    const generateDecorated = async () => {
        if (!baseImageUrl) return;

        try {
            setStatus("generating");
            setResultImageUrl("");

            const frameEl = captureRef.current;
            if (!frameEl) return;

            await new Promise((r) => setTimeout(r, 100));

            const canvas = await html2canvas(frameEl, {
                backgroundColor: null,
                scale: 2,
                useCORS: true,
                allowTaint: true,
                logging: false,
            });

            setResultImageUrl(canvas.toDataURL("image/png"));
            setStatus("idle");
        } catch (e) {
            console.error(e);
            setStatus("error");
        }
    };

    const handleDownload = () => {
        if (!resultImageUrl) return;
        const a = document.createElement("a");
        a.href = resultImageUrl;
        a.download = `decorated-${Date.now()}.png`;
        a.click();
    };

    const handleFinalSave = async () => {
        if (!resultImageUrl || typeof onSave !== "function") return;
        try {
            setStatus("saving");
            const blob = await dataUrlToBlob(resultImageUrl);
            const file = new File([blob], `decorated-${Date.now()}.png`, { type: "image/png" });

            await onSave({
                file,
                nickname,
                dday,
                tags: allTags
            });
            setStatus("idle");
        } catch (e) {
            console.error(e);
            setStatus("error");
        }
    };

    return (
        <div className="decorate-page">
            <div className="decorate-center">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <h1 className="timelog__sectionTitle">사진 꾸미기</h1>
                    <button className="ui-btn ui-btn-ghost ui-btn--compact decorate-cancel" onClick={onCancel}>취소하고 돌아가기</button>
                </div>

                <div className="decorate-layout">
                    <DecorateForm
                        baseImageUrl={baseImageUrl}
                        plant={plant}
                        nickname={nickname}
                        dday={dday}
                        customTags={customTags}
                        emojiStickers={emojiStickers}
                        emojiOptions={EMOJI_STICKERS}
                        onChangeNickname={setNickname}
                        onChangeDday={setDday}
                        onAddCustomTag={addCustomTag}
                        onRemoveCustomTag={removeCustomTag}
                        onAddEmojiSticker={addEmojiSticker}
                        onRemoveEmojiSticker={removeEmojiSticker}
                        onGenerate={generateDecorated}
                        status={status}
                    />

                    <div className="decorate-preview">
                        <div className="template-picker-row">
                            <div className="template-picker__label">템플릿 배경</div>
                            <div className="template-picker">
                                {TEMPLATE_PRESETS.map((tpl) => (
                                    <button
                                        key={tpl.id}
                                        type="button"
                                        className={`template-swatch ${templatePresetId === tpl.id ? "is-active" : ""}`}
                                        style={{ background: tpl.color }}
                                        onClick={() => setTemplatePresetId(tpl.id)}
                                        title={tpl.name}
                                        aria-label={tpl.name}
                                    />
                                ))}
                            </div>
                        </div>
                        <div
                            className="template-frame--brand"
                            ref={captureRef}
                            style={{ background: activeTemplate?.color || "#ffffff" }}
                        >
                            <img
                                className="template-bg"
                                src={TEMPLATE_BG}
                                alt=""
                                crossOrigin="anonymous"
                                onError={(e) => {
                                    e.target.style.display = "none";
                                }}
                            />

                            <div className="tpl-photoSlot" ref={photoWrapRef}>
                                {baseImageUrl ? (
                                    <img
                                        className="tpl-photo"
                                        src={baseImageUrl}
                                        alt="photo"
                                        crossOrigin="anonymous"
                                    />
                                ) : (
                                    <div className="tpl-empty">이미지가 없습니다.</div>
                                )}
                            </div>

                            <div className="tpl-title">{nickname || "식물 별명"}</div>
                            <div className="tpl-sub">{dday ? `함께한지 D+${dday}` : "함께한 날짜를 입력해줘"}</div>

                            {stickers.map((s) => {
                                const posStyle = s.side === "right"
                                    ? { right: s.right, left: "unset" }
                                    : { left: s.left, right: "unset" };

                                return (
                                    <div
                                        key={s.id}
                                        className="template-sticker--brand"
                                        style={{
                                            position: "absolute",
                                            top: s.top,
                                            ...posStyle,
                                            transform: `rotate(${s.rotate}deg)`,
                                            textAlign: s.anchor === 'center' ? 'center' : 'left'
                                        }}
                                    >
                                        {s.text}
                                    </div>
                                );
                            })}
                        </div>

                        {resultImageUrl && (
                            <div className="decorate-result">
                                <div className="decorate-result__title">완성된 미리보기</div>
                                <img className="decorate-result__img" src={resultImageUrl} alt="result" />
                                <div className="decorate-result__actions">
                                    <button type="button" className="ui-btn ui-btn-ghost ui-btn--compact" onClick={handleDownload}>
                                        🖼️ 다운로드
                                    </button>
                                    <button type="button" className="ui-btn ui-btn-primary ui-btn--compact" onClick={handleFinalSave} disabled={isSaving}>
                                        {isSaving ? "저장 중..." : "💾 타임로그에 저장"}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DecorateContainer;
