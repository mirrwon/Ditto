import { useEffect, useState } from "react";
import { fetchWithSession } from "../../services/session";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../constants/routes";
import PlantSelectPage from "./PlantSelectPage";

const API_BASE = "http://localhost:8000/api/chat";
const ANALYZE_API = `${API_BASE}/analyze`;

export default function AnalyzePage() {
  const nav = useNavigate();

  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;

    const run = async () => {
      setStatus("loading");
      setError("");

      // 1. 기존 데이터 정리
      try {
        sessionStorage.removeItem("selected_plant");
        sessionStorage.removeItem("ai_edit_url");
        sessionStorage.removeItem("render_result");
        sessionStorage.removeItem("last_render");
      } catch (e) {
        console.error("Session clear error:", e);
      }

      try {
        const meta = {
          lat: 37.5665,
          lot: 126.978,
          hhmm: new Date().toTimeString().slice(0, 5).replace(":", ""),
        };

        // 2. 서버 요청 (변수 선언 없이 세션에서 바로 파싱해서 투입)
        const res = await fetchWithSession(ANALYZE_API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            meta, 
            filters: JSON.parse(sessionStorage.getItem("survey_answers") || "{}") 
          }),
        });

        if (!res.ok) throw new Error("analyze_failed");
        // await res.json(); 
        const data = await res.json();

        sessionStorage.setItem("analyze_result", JSON.stringify(data));
        if (data?.sid) localStorage.setItem("sid", data.sid);

        if (!alive) return;
        setStatus("done");
      } catch (e) {
        if (!alive) return;
        setStatus("error");
        setError("Failed to analyze space.");
      }
    };

    run();
    return () => {
      alive = false;
    };
  }, []); 

  if (status === "loading") return <p className="surveyStatus">공간 분석 중...</p>;
  if (status === "error") return <p className="surveyStatus surveyStatus--error">{error}</p>;

  return (
    <PlantSelectPage
      onPicked={() => nav(ROUTES.RENDER)}
      onRetrySurvey={() => nav(ROUTES.SURVEY)}
    />
  );
}