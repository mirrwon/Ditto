import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchWithSession } from "../../services/session";
import { ROUTES } from "../../constants/routes"; 
import "./Survey.css"; // 기존스타일 재사용

const API_BASE = "http://localhost:8000/api/chat";
const API_ROOT = API_BASE.replace(/\/api\/chat$/, "");
const CHAT_IMAGE_API = `${API_BASE}/image`;

export default function UploadPage() {
  const nav = useNavigate();

  const [uploadFiles, setUploadFiles] = useState([]);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState("");
  const [uploadStatus, setUploadStatus] = useState("idle"); // idle|uploading|done|error
  const [uploadError, setUploadError] = useState("");

  const [needRoomType, setNeedRoomType] = useState(false);
  const [roomOptions, setRoomOptions] = useState(["거실", "침실", "주방", "욕실"]);

  useEffect(() => {
    return () => {
      if (uploadPreviewUrl) URL.revokeObjectURL(uploadPreviewUrl);
    };
  }, [uploadPreviewUrl]);

  const handleUploadChange = (event) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    if (uploadPreviewUrl) URL.revokeObjectURL(uploadPreviewUrl);
    setUploadFiles(files);
    setUploadPreviewUrl(files[0] ? URL.createObjectURL(files[0]) : "");
    setUploadError("");
  };

  const doUploadToChatImage = async (roomType = "") => {
    if (uploadFiles.length === 0) throw new Error("no_file");

    const formData = new FormData();
    uploadFiles.forEach((file) => formData.append("files", file));

    // ✅ room_type을 서버가 기대하는 키로 정확히 전달
    // (서버에서 room_type 말고 roomType 등을 기대하면 여기만 바꾸면 됨)
    if (roomType) formData.append("room_type", roomType);

    const response = await fetchWithSession(CHAT_IMAGE_API, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error("upload_failed");
    return await response.json();
  };

  // ✅ 업로드 성공 시 공통 처리(플래그 저장 + 서버 응답 저장 + 페이지 이동)
  const finishAndGoSurvey = (serverPayload, chosenRoomType = "") => {
    // 1) Survey 강제 리다이렉트(Upload 안거치면 튕김) 방지 플래그
    sessionStorage.setItem("ditto_uploaded", "1");

    // 2) AnalyzePage 등 다음 페이지에서 쓸 수도 있으니 서버 응답 저장 (선택)
    //    (원치 않으면 이 2줄 지워도 됨)
    sessionStorage.setItem("ditto_upload_result", JSON.stringify(serverPayload ?? {}));
    if (chosenRoomType) sessionStorage.setItem("ditto_room_type", chosenRoomType);

    // 3) 파일/프리뷰 정리
    setUploadFiles([]);
    if (uploadPreviewUrl) URL.revokeObjectURL(uploadPreviewUrl);
    setUploadPreviewUrl("");

    sessionStorage.setItem("ditto_uploaded", "1");

    // 4) Survey로 이동
    nav(ROUTES?.SURVEY || "/survey");
  };

  const saveRoomImage = (serverPayload) => {
    const savedImage =
      serverPayload?.saved_image ||
      serverPayload?.data?.saved_image ||
      serverPayload?.payload?.saved_image ||
      null;
    if (!savedImage) return;

    const roomImageUrl = `${API_ROOT}/uploads/${savedImage}`;
    sessionStorage.setItem("room_image_url", roomImageUrl);
    sessionStorage.setItem("room_image_filename", savedImage);
  };

  const handleUploadSubmit = async (event) => {
    event.preventDefault();
    if (uploadFiles.length === 0 || uploadStatus === "uploading") return;

    setUploadStatus("uploading");
    setUploadError("");

    try {
      const data = await doUploadToChatImage("");

      // room_type 필요
      if (data?.need_room_type) {
        setNeedRoomType(true);
        const opts = data?.payload?.options;
        if (Array.isArray(opts) && opts.length) setRoomOptions(opts);
        setUploadStatus("idle");
        return;
      }

      // room_type 불필요(자동 확정) → 2페이지로 이동
      setNeedRoomType(false);
      setUploadStatus("done");

      saveRoomImage(data);
      finishAndGoSurvey(data, "");
    } catch (e) {
      setUploadStatus("idle");
      setUploadError("Failed to upload images.");
    }
  };

  const handlePickRoomType = async (rt) => {
    if (!rt) return;

    setUploadStatus("uploading");
    setUploadError("");

    try {
      const data2 = await doUploadToChatImage(rt);

      if (data2?.need_room_type) {
        setUploadStatus("idle");
        setUploadError("선택한 공간으로도 확정이 어려워요. 다른 공간을 선택해보세요.");
        return;
      }

      setNeedRoomType(false);
      setUploadStatus("done");

      saveRoomImage(data2);
      finishAndGoSurvey(data2, rt);
    } catch (e) {
      setUploadStatus("idle");
      setUploadError("Failed to upload images.");
    }
  };

  return (
    <div className="surveyPage">
      <div className="surveyShell">
        <div className="surveyCard">
          <div className="surveyGate">
            <header className="surveyHeader">
              <h2 className="surveyTitle">방 사진을 업로드 해주세요</h2>
              <p className="surveyDesc">최적의 스팟을 추천해 드릴게요</p>
            </header>

            <form className="surveyUpload surveyUpload--gate" onSubmit={handleUploadSubmit}>
              <label className="surveyUpload__pick">
                <input
                  className="surveyUpload__input"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleUploadChange}
                />
                <span className="surveyUpload__text">
                  {uploadFiles.length ? `선택된 이미지 ${uploadFiles.length}개` : "이미지 업로드"}
                </span>
              </label>

              <button
                className="chatBtn"
                type="submit"
                disabled={uploadFiles.length === 0 || uploadStatus === "uploading"}
              >
                {uploadStatus === "uploading" ? "업로드 중.." : "업로드"}
              </button>
            </form>

            {uploadPreviewUrl && (
              <div className="surveyUploadPreview">
                <img className="surveyUploadPreview__img" src={uploadPreviewUrl} alt="preview" />
              </div>
            )}

            {uploadError && <p className="surveyStatus surveyStatus--error">{uploadError}</p>}

            {needRoomType && (
              <div style={{ marginTop: 12 }}>
                <p className="surveyDesc">사진에서 공간을 확정할 수 없어요. 공간을 선택해주세요.</p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                  {roomOptions.map((rt) => (
                    <button
                      key={rt}
                      type="button"
                      className="chatBtn"
                      onClick={() => handlePickRoomType(rt)}
                      disabled={uploadStatus === "uploading"}
                    >
                      {rt}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
