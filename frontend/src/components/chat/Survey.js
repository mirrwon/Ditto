import { useEffect, useMemo, useState } from "react";
import { fetchWithSession } from "../../services/session";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../constants/routes";
import "./Survey.css";

const API_BASE = "http://localhost:8000/api/chat";
const SURVEY_API = `${API_BASE}/survey`;
const API_ORIGIN = "http://localhost:8000";

/** 설문 옵션 이미지 URL을 정규화합니다. */
const resolveImageUrl = (url) => {
  if (!url) return null;
  const u = String(url);
  if (u.startsWith("http://") || u.startsWith("https://")) return u;
  if (u.startsWith("/")) return `${API_ORIGIN}${u}`;
  return u;
};

// 빈 값/없음 계열 값은 미적용으로 처리합니다.
const isNoneLikeValue = (value) => {
  const raw = String(value ?? "").trim();
  if (!raw) return true;
  const v = raw.toLowerCase();
  return v === "none" || v === "없음" || v === "해당없음" || v === "해당 없음";
};

const normalizeNone = (arr) => {
  if (!Array.isArray(arr)) return [];
  return arr
    .map((x) => String(x ?? "").trim())
    .filter((x) => !isNoneLikeValue(x));
};

const normalizeOption = (option, index) => {
  if (option == null) {
    return {
      value: `option-${index + 1}`,
      label: `Option ${index + 1}`,
      image: null,
      children: [],
    };
  }

  if (typeof option === "string") {
    return {
      value: option,
      label: option,
      image: null,
      children: [],
    };
  }

  const pickNonEmpty = (...cands) => {
    for (const c of cands) {
      if (c == null) continue;
      const s = String(c).trim();
      if (s) return s;
    }
    return "";
  };

  const hasExplicitEmptyValue =
    Object.prototype.hasOwnProperty.call(option, "value") && option.value === "";

  const value = hasExplicitEmptyValue
    ? ""
    : pickNonEmpty(
      option.value,
      option.key,
      option.id,
      option.label,
      `option-${index + 1}`
    );

  const label = pickNonEmpty(
    option.label,
    option.text,
      option.value,
    option.key,
    `Option ${index + 1}`
  );


  // 여러 필드에서 이미지 후보를 수집합니다.
  const rawImage =
    option.image ??
    option.img ??
    option.thumbnail ??
    option.thumb ??
    option.url ??
    option.src ??
    (Array.isArray(option.images) ? option.images[0] : null);

  const rawChildren = Array.isArray(option.children)
    ? option.children
    : Array.isArray(option.items)
    ? option.items
    : [];
  const children = rawChildren.map((child, idx) => normalizeOption(child, idx));

  return {
    value: String(value),
    label: String(label),
    image: resolveImageUrl(rawImage),
    children,
  };
};

const normalizeGroups = (payload) => {
  if (!payload) return [];

  const rawGroups = Array.isArray(payload.groups)
    ? payload.groups
    : Array.isArray(payload.items)
    ? payload.items
    : payload.options || payload.key || payload.label
    ? [payload]
    : [];

  return rawGroups
    .map((group, index) => {
      const options = Array.isArray(group.options)
        ? group.options.map((option, idx) => normalizeOption(option, idx))
        : [];

      return {
        key: group.key ?? group.id ?? `group-${index + 1}`,
        label: group.label ?? group.title ?? `Question ${index + 1}`,
        description: group.description ?? group.desc ?? "",
        ui: group.ui ?? group.view ?? group.render ?? null,
        multiple: Boolean(group.multiple) || (typeof group.max === "number" && group.max > 1),
        max: typeof group.max === "number" ? group.max : null,
        optional: Boolean(group.optional),
        options,
      };
    })
    .filter((group) => group.options.length > 0);
};

const normalizeSurvey = (data) => {
  if (!data) return null;
  const payload = data.survey || data.payload || data.data || data;
  const groups = normalizeGroups(payload);

  if (!groups.length) return null;

  return {
    key: payload.key ?? payload.id ?? "survey",
    title: payload.title ?? payload.label ?? data.title ?? "Survey",
    description: payload.description ?? data.description ?? "",
    groups,
  };
};

export default function Survey() {
  const nav = useNavigate();

  const [survey, setSurvey] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | submitting | done | error
  const [selected, setSelected] = useState({});
  const [activeChildren, setActiveChildren] = useState({});
  const [loadError, setLoadError] = useState("");
  const [submitError, setSubmitError] = useState("");

  // 업로드를 먼저 하지 않았으면 /upload로 이동합니다.
  useEffect(() => {
    const ok = sessionStorage.getItem("ditto_uploaded") === "1";
    if (!ok) nav(ROUTES.UPLOAD);
  }, [nav]);

  useEffect(() => {
    let active = true;

    const fetchSurvey = async () => {
      setStatus("loading");
      setLoadError("");

      try {
        const response = await fetchWithSession(SURVEY_API, { method: "GET" });
        if (!response.ok) throw new Error("failed");

        const data = await response.json();
        const normalized = normalizeSurvey(data);
        if (!normalized) throw new Error("invalid");

        if (!active) return;
        setSurvey(normalized);
        setStatus("ready");
      } catch (error) {
        if (!active) return;
        setLoadError("Failed to load survey.");
        setStatus("error");
      }
    };

    fetchSurvey();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!survey?.groups) return;
    setSelected((prev) => {
      const next = {};
      survey.groups.forEach((group) => {
        next[group.key] = Array.isArray(prev[group.key]) ? prev[group.key] : [];
      });
      return next;
    });
  }, [survey]);

  const allAnswered = useMemo(() => {
    if (!survey?.groups?.length) return false;
    return survey.groups.every((group) => {
      if (group.optional) return true;
      return (selected[group.key] || []).length > 0;
    });
  }, [survey, selected]);

  const computeNextSelection = (current, value, isMultiple, max) => {
    const hasValue = current.includes(value);

    if (isNoneLikeValue(value)) {
      return hasValue ? current.filter((item) => item !== value) : [value];
    }

    const withoutNone = current.filter((item) => !isNoneLikeValue(item));

    if (isMultiple) {
      if (withoutNone.includes(value)) return withoutNone.filter((item) => item !== value);
      if (!max || withoutNone.length < max) return [...withoutNone, value];
      return withoutNone;
    }
    return withoutNone.includes(value) ? [] : [value];
  };

  const handleOptionToggle = (groupKey, value, isMultiple, max) => {
    setSelected((prev) => {
      const current = Array.isArray(prev[groupKey]) ? prev[groupKey] : [];
      const next = computeNextSelection(current, value, isMultiple, max);
      return { ...prev, [groupKey]: next };
    });
  };

  const handleParentToggle = (groupKey, option, isMultiple, max, currentSelection) => {
    const next = computeNextSelection(currentSelection, option.value, isMultiple, max);
    setSelected((prev) => ({ ...prev, [groupKey]: next }));
    setActiveChildren((prev) => ({
      ...prev,
      [groupKey]: option.children?.length && next.includes(option.value) ? option.value : null,
    }));
  };

  const toToken = (groupKey, vRaw) => {
    const v = String(vRaw || "").trim().toLowerCase();
    if (isNoneLikeValue(v)) return null;

    if (groupKey === "size") {
      if (v === "small" || v === "s" || v.includes("table")) return "small";
      if (v === "medium" || v === "m" || v.includes("medium")) return "medium";
      if (v === "large" || v === "l" || v.includes("floor")) return "large";
      return null;
    }

    if (groupKey === "style") {
      if (v === "natural" || v.includes("natural")) return "natural";
      if (v === "minimal" || v.includes("minimal")) return "minimal";
      if (v === "trendy" || v.includes("trendy")) return "trendy";
      return null;
    }

    if (groupKey === "Plant_style") {
      if (v === "flowery" || v.includes("flower")) return "flowery";
      if (v === "leafy" || v.includes("leaf")) return "leafy";
      if (v === "fruity" || v.includes("fruit")) return "fruity";
      return null;
    }

    if (groupKey === "caution") {
      if (v === "dog" || v.includes("dog")) return "dog";
      if (v === "cat" || v.includes("cat")) return "cat";
      if (v === "allergy" || v.includes("allergy")) return "allergy";
      if (v === "baby" || v.includes("baby")) return "baby";
      return null;
    }

    return null;
  };

  const tokenizeSelected = (sel) => {
    const out = {};
    Object.entries(sel || {}).forEach(([k, arr]) => {
      const tokens = (Array.isArray(arr) ? arr : [])
        .map((v) => toToken(k, v))
        .filter(Boolean);
      out[k] = Array.from(new Set(tokens));
    });
    return out;
  };

  const handleSubmit = async () => {
    if (!survey || !allAnswered || status === "submitting") return;

    setStatus("submitting");
    setSubmitError("");

    // 없음 계열 값을 제거하고 선택값을 토큰으로 정규화합니다.
    const cleaned = Object.fromEntries(
      Object.entries(selected || {}).map(([k, v]) => [k, normalizeNone(v)])
    );


    const tokenized = tokenizeSelected(cleaned);

    console.log("[DEBUG][submit.cleaned]", cleaned);
    console.log("[DEBUG][submit.tokenized]", tokenized);

    try {
      const response = await fetchWithSession(SURVEY_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          survey_key: survey.key,
          answers: tokenized,
        }),
      });

      if (!response.ok) throw new Error("survey_failed");

      setStatus("done");

      // PlantSelectPage에서 읽을 수 있도록 토큰화된 답변을 저장합니다.
      sessionStorage.setItem("survey_answers", JSON.stringify(tokenized));

      nav(ROUTES.ANALYZE);
    } catch (e) {
      setStatus("ready");
      setSubmitError("Failed to submit survey.");
    }
  };
  return (
    <div className="surveyPage">
      <div className="surveyShell">
        <div className="surveyCard">
          <header className="surveyHeader">
            <h2 className="surveyTitle">{survey?.title || "Survey"}</h2>
            {survey?.description && <p className="surveyDesc">{survey.description}</p>}
            {status === "loading" && <p className="surveyStatus">Loading survey...</p>}
            {loadError && <p className="surveyStatus surveyStatus--error">{loadError}</p>}
          </header>

          {survey?.groups?.map((group) => {
            const isMultiple = group.multiple;
            const selectedValues = selected[group.key] || [];

            const renderParentChecks = (options) => (
              <div className="surveyChecks">
                {options.map((option, index) => {
                  const isSelected = selectedValues.includes(option.value);
                  const hasImage = !!option.image;
                  const isNoneOption = isNoneLikeValue(option.value) || isNoneLikeValue(option.label);
                  const hasNoneSelected = selectedValues.some((v) => isNoneLikeValue(v));
                  const hasNormalSelected = selectedValues.some((v) => !isNoneLikeValue(v));
                  const isDimmed =
                    (isNoneOption && hasNormalSelected) || (!isNoneOption && hasNoneSelected);
                  return (
                    <label key={`${group.key}-${option.value}-${index}`} className="surveyCheck">
                      <input
                        className="surveyCheck__input"
                        type="checkbox"
                        checked={isSelected}
                        
                        onChange={() =>
                          handleParentToggle(group.key, option, isMultiple, group.max, selectedValues)
                        }
                      />

                      {/* 이미지가 있으면 이미지형 라벨 스타일을 사용합니다. */}
                      <span
                        className={
                          hasImage
                            ? `surveyCheck__label surveyCheck__label--image${isDimmed ? " surveyCheck__label--dimmed" : ""}`
                            : `surveyCheck__label${isDimmed ? " surveyCheck__label--dimmed" : ""}`
                        }
                      >
                        {hasImage && (
                          <img
                            className="surveyCheck__thumb"
                            src={option.image}
                            alt={option.label}
                            onError={(e) => {
                              // 깨진 이미지는 숨겨서 UI 노이즈를 줄입니다.
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        )}
                        <span className="surveyCheck__text">{option.label}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            );

            const renderChildChecks = (options, depth = 0, path = "") => (
              <div
                className="surveyChecks surveyChecks--nested"
                style={depth > 0 ? { marginTop: "8px", paddingLeft: `${depth * 16}px` } : undefined}
              >
                {options.map((option, index) => {
                  const isSelected = selectedValues.includes(option.value);
                  const optionKey = `${path}${option.value}-${index}`;
                  const hasImage = !!option.image;
                  const isNoneOption = isNoneLikeValue(option.value) || isNoneLikeValue(option.label);
                  const hasNoneSelected = selectedValues.some((v) => isNoneLikeValue(v));
                  const hasNormalSelected = selectedValues.some((v) => !isNoneLikeValue(v));
                  const isDimmed =
                    (isNoneOption && hasNormalSelected) || (!isNoneOption && hasNoneSelected);
                  return (
                    <div key={optionKey} className="surveyChildItem">
                      <label className="surveyCheck">
                        <input
                          className="surveyCheck__input"
                          type="checkbox"
                          checked={isSelected}
                          
                          onChange={() =>
                            handleOptionToggle(group.key, option.value, isMultiple, group.max)
                          }
                        />

                        <span
                          className={
                            hasImage
                              ? `surveyCheck__label surveyCheck__label--image${isDimmed ? " surveyCheck__label--dimmed" : ""}`
                              : `surveyCheck__label${isDimmed ? " surveyCheck__label--dimmed" : ""}`
                          }
                        >
                          {hasImage && (
                            <img
                              className="surveyCheck__thumb"
                              src={option.image}
                              alt={option.label}
                              onError={(e) => {
                                e.currentTarget.style.display = "none";
                              }}
                            />
                          )}
                          <span className="surveyCheck__text">{option.label}</span>
                        </span>
                      </label>

                      {option.children?.length && isSelected
                        ? renderChildChecks(option.children, depth + 1, `${optionKey}-`)
                        : null}
                    </div>
                  );
                })}
              </div>
            );

            const activeChildPanels = group.options
              .filter(
                (option) =>
                  option.children?.length &&
                  selectedValues.includes(option.value) &&
                  activeChildren[group.key] === option.value
              )
              .map((option, index) => (
                <div key={`${group.key}-childpanel-${index}`} className="surveyChildPanel">
                  {renderChildChecks(option.children, 0, `${group.key}-${option.value}-`)}
                </div>
              ));

            return (
              <section key={group.key} className="surveyGroup" data-group-key={group.key}>
                <div className="surveyGroup__header">
                  <h3 className="surveyGroup__title">{group.label}</h3>
                  {group.description && <p className="surveyGroup__desc">{group.description}</p>}
                  {group.max ? <p className="surveyGroup__meta">Select up to {group.max}</p> : null}
                </div>

                {renderParentChecks(group.options)}

                {activeChildPanels.length > 0 && (
                  <div className="surveyChildPanels">{activeChildPanels}</div>
                )}
              </section>
            );
          })}

          <footer className="surveyFooter">
            <button
              className="chatBtn"
              type="button"
              onClick={handleSubmit}
              disabled={!allAnswered || status === "submitting"}
            >
              {status === "submitting" ? "처리 중..." : "Submit"}
            </button>

            {submitError && <p className="surveyStatus surveyStatus--error">{submitError}</p>}
          </footer>
        </div>
      </div>
    </div>
  );
}