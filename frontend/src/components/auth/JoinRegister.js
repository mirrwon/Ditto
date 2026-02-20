import { useEffect, useState } from "react";
import "../../pages/auth/Register.css";
import { readStoredUser, storeUser } from "../../services/session";

const decodePayload = (value) => {
  try {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "="
    );
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, "0")}`)
        .join("")
    );
    return JSON.parse(json);
  } catch (error) {
    return null;
  }
};

const isShortHeading = (line) => {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (/^[-*]\s+/.test(trimmed)) return false;
  if (/^\d+\.\s*/.test(trimmed)) return false;
  if (/^제\s*\d+\s*조/.test(trimmed)) return true;
  return trimmed.length <= 20;
};

const renderMarkdown = (text) => {
  if (!text) return null;
  const normalized = text.replace(/^\uFEFF/, "");
  const blocks = normalized.split(/\r?\n\s*\r?\n/);

  return blocks.map((block, blockIndex) => {
    const lines = block
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    if (!lines.length) return null;

    const firstLine = lines[0];
    const headingMatch = firstLine.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch && lines.length === 1) {
      const level = Math.min(4, headingMatch[1].length + 1);
      const HeadingTag = `h${level}`;
      return (
        <HeadingTag key={`block-${blockIndex}`}>
          {headingMatch[2].trim()}
        </HeadingTag>
      );
    }

    const isOrderedList = lines.every((line) => /^\d+\.\s*/.test(line));
    if (isOrderedList) {
      return (
        <ol key={`block-${blockIndex}`}>
          {lines.map((line, lineIndex) => (
            <li key={`item-${blockIndex}-${lineIndex}`}>
              {line.replace(/^\d+\.\s*/, "")}
            </li>
          ))}
        </ol>
      );
    }

    const isUnorderedList = lines.every((line) => /^[-*]\s+/.test(line));
    if (isUnorderedList) {
      return (
        <ul key={`block-${blockIndex}`}>
          {lines.map((line, lineIndex) => (
            <li key={`item-${blockIndex}-${lineIndex}`}>
              {line.replace(/^[-*]\s+/, "")}
            </li>
          ))}
        </ul>
      );
    }

    if (lines.length === 1 && isShortHeading(firstLine)) {
      return <h2 key={`block-${blockIndex}`}>{firstLine}</h2>;
    }

    return (
      <p key={`block-${blockIndex}`}>
        {lines.map((line, lineIndex) => (
          <span key={`line-${blockIndex}-${lineIndex}`}>
            {line}
            {lineIndex < lines.length - 1 && <br />}
          </span>
        ))}
      </p>
    );
  });
};

const JoinRegister = ({ onSubmit }) => {
  const [isOauth, setIsOauth] = useState(false);
  const [formData, setFormData] = useState({
    profileImage: null,
    username: "",
    password: "",
    confirmPassword: "",
    name: "",
    age: "",
    gender: "",
    birthDate: "",
    phone: "",
    email: "",
    zipcode: "",
    address1: "",
    address2: "",
    termsAccepted: false,
    locationAccepted: false,
  });

  const [previewUrl, setPreviewUrl] = useState("");
  const [formError, setFormError] = useState("");
  const [modalState, setModalState] = useState({
    isOpen: false,
    title: "",
    content: "",
    loading: false,
    error: "",
  });

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, "").slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 7) {
      return `${digits.slice(0, 3)}-${digits.slice(3)}`;
    }
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const nextValue =
      type === "checkbox" ? checked : name === "phone" ? formatPhone(value) : value;
    setFormData((prev) => ({
      ...prev,
      [name]: nextValue,
    }));
    setFormError("");
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") !== "google") return;
    setIsOauth(true);
    const payload = params.get("payload");
    if (!payload) return;
    const data = decodePayload(payload);
    if (!data) return;
    storeUser(data);
  }, []);

  useEffect(() => {
    if (!isOauth) return;
    const user = readStoredUser();
    if (!user) return;
    setFormData((prev) => ({
      ...prev,
      username: user.user_name || user.username || "",
      email: user.email || "",
      name: user.name || "",
    }));
  }, [isOauth]);

  const handleProfileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFormData((prev) => ({
      ...prev,
      profileImage: file,
    }));

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setFormError("");
  };

  const handleAddressSearch = () => {
    if (!window.daum || !window.daum.Postcode) {
      setFormError("Address search is unavailable.");
      return;
    }

    new window.daum.Postcode({
      oncomplete: (data) => {
        const address =
          data.roadAddress || data.jibunAddress || data.address || "";
        setFormData((prev) => ({
          ...prev,
          zipcode: data.zonecode || "",
          address1: address,
        }));
        setFormError("");
      },
    }).open();
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!isOauth && formData.password !== formData.confirmPassword) {
      setFormError("비밀번호가 일치하지 않습니다.");
      return;
    }

    if (!formData.termsAccepted || !formData.locationAccepted) {
      setFormError("필수 약관에 동의해주세요.");
      return;
    }

    const payload = {
      ...(isOauth ? {} : { username: formData.username }),
      password: isOauth ? undefined : formData.password,
      name: formData.name,
      age: formData.age,
      gender: formData.gender,
      birthDate: formData.birthDate,
      phone: formData.phone,
      email: formData.email,
      zipcode: formData.zipcode,
      address1: formData.address1,
      address2: formData.address2,
      profileImage: formData.profileImage,
    };

    onSubmit(payload);
  };

  const openModal = async (type) => {
    const isTerms = type === "terms";
    const title = isTerms ? "이용약관" : "위치정보 이용약관";
    const url = isTerms ? "/terms_v1.md" : "/terms_location_v1.md";

    setModalState((prev) => ({
      ...prev,
      isOpen: true,
      title,
      loading: true,
      error: "",
    }));

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error("약관을 불러오지 못했습니다.");
      }
      const text = await response.text();
      setModalState((prev) => ({
        ...prev,
        content: text,
        loading: false,
      }));
    } catch (err) {
      setModalState((prev) => ({
        ...prev,
        content: "",
        loading: false,
        error: err.message || "약관을 불러오지 못했습니다.",
      }));
    }
  };

  const closeModal = () => {
    setModalState((prev) => ({
      ...prev,
      isOpen: false,
    }));
  };

  return (
    <div className="register-container">
      <h2 className="register-title">회원가입</h2>
      <div className="ui-line register-divider" />

      <div className="register-form">
        {/* 프로필 */}
        <span className="register-label">프로필 사진</span>

        <div className="profile-row">
          <div className="profile-preview-box">
            {previewUrl && <img src={previewUrl} alt="프로필 미리보기" />}
          </div>

          <input
            id="profileImage"
            type="file"
            accept="image/*"
            onChange={handleProfileChange}
            className="profile-input"
          />

          <label
            htmlFor="profileImage"
            className="ui-btn ui-btn-primary profile-btn"
          >
            프로필 사진 추가
          </label>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="register-field-label" htmlFor="register-username">
            아이디
          </label>
          <input
            id="register-username"
            name="username"
            type="text"
            value={formData.username}
            onChange={handleChange}
            placeholder="아이디"
            className="ui-input"
            required={!isOauth}
            disabled={isOauth}
          />

          <label className="register-field-label" htmlFor="register-password">
            비밀번호
          </label>
          <input
            id="register-password"
            name="password"
            type="password"
            value={formData.password}
            onChange={handleChange}
            placeholder="비밀번호"
            className="ui-input"
            required={!isOauth}
            disabled={isOauth}
          />

          <label className="register-field-label" htmlFor="register-confirm-password">
            비밀번호 확인
          </label>
          <input
            id="register-confirm-password"
            name="confirmPassword"
            type="password"
            value={formData.confirmPassword}
            onChange={handleChange}
            placeholder="비밀번호 확인"
            className="ui-input"
            required={!isOauth}
            disabled={isOauth}
          />

          <label className="register-field-label" htmlFor="register-name">
            이름
          </label>
          <input
            id="register-name"
            name="name"
            type="text"
            value={formData.name}
            onChange={handleChange}
            placeholder="이름"
            className="ui-input"
            required
          />

          {/* 성별 */}
          <label className="register-field-label" htmlFor="register-gender">
            성별
          </label>
          <select
            id="register-gender"
            name="gender"
            value={formData.gender}
            onChange={handleChange}
            className="ui-input"
            required
          >
            <option value="">성별 선택</option>
            <option value="male">남성</option>
            <option value="female">여성</option>
          </select>

          <label className="register-field-label" htmlFor="register-birthdate">
            생년월일
          </label>
          <input
            id="register-birthdate"
            name="birthDate"
            type="date"
            value={formData.birthDate}
            onChange={handleChange}
            min="1900-01-01"
            max="2099-12-31"
            className="ui-input"
            required
          />

          <label className="register-field-label" htmlFor="register-phone">
            전화번호
          </label>
          <input
            id="register-phone"
            name="phone"
            type="tel"
            value={formData.phone}
            onChange={handleChange}
            placeholder="010-0000-0000"
            inputMode="numeric"
            maxLength={13}
            className="ui-input"
            required
          />

          <label className="register-field-label" htmlFor="register-email">
            이메일
          </label>
          <input
            id="register-email"
            name="email"
            type="email"
            value={formData.email}
            onChange={handleChange}
            placeholder="email@example.com"
            className="ui-input"
            required={!isOauth}
            disabled={isOauth}
          />

          <label className="register-field-label" htmlFor="register-zipcode">
            우편번호
          </label>
          <div className="address-row">
            <input
              id="register-zipcode"
              name="zipcode"
              type="text"
              value={formData.zipcode}
              onChange={handleChange}
              placeholder="우편번호"
              className="ui-input"
              readOnly
            />
            <button
              type="button"
              onClick={handleAddressSearch}
              className="ui-btn ui-btn-primary ui-btn--compact address-search"
            >
              주소 검색
            </button>
          </div>

          <label className="register-field-label" htmlFor="register-address1">
            주소
          </label>
          <input
            id="register-address1"
            name="address1"
            type="text"
            value={formData.address1}
            onChange={handleChange}
            placeholder="기본 주소"
            className="ui-input"
          />

          <label className="register-field-label" htmlFor="register-address2">
            상세 주소
          </label>
          <input
            id="register-address2"
            name="address2"
            type="text"
            value={formData.address2}
            onChange={handleChange}
            placeholder="상세 주소"
            className="ui-input"
          />

          <div className="">
            <label className="">
              <input
                type="checkbox"
                name="termsAccepted"
                checked={formData.termsAccepted}
                onChange={handleChange}
              />
              <span>이용약관 동의 (필수)</span>
            </label>
            <button
              type="button"
              onClick={() => openModal("terms")}
              className=""
            >
              보기
            </button>
          </div>

          <div className="">
            <label className="">
              <input
                type="checkbox"
                name="locationAccepted"
                checked={formData.locationAccepted}
                onChange={handleChange}
              />
              <span>위치정보 이용약관 동의 (필수)</span>
            </label>
            <button
              type="button"
              onClick={() => openModal("location")}
              className=""
            >
              보기
            </button>
          </div>

          {formError && (
            <p className="register-error">{formError}</p>
          )}

          <button
            type="submit"
            className="ui-btn ui-btn-primary register-submit"
          >
            가입
          </button>
        </form>
      </div>

      {modalState.isOpen && (
        <div className="" role="dialog" aria-modal="true">
          <div className="">
            <div className="">
              <h3>{modalState.title}</h3>
              <button
                type="button"
                className=""
                onClick={closeModal}
                aria-label="닫기"
              >
                닫기
              </button>
            </div>
            <div className="">
              {modalState.loading && <p>불러오는 중...</p>}
              {modalState.error && (
                <p className="">{modalState.error}</p>
              )}
              {!modalState.loading && !modalState.error && (
                <div className="terms-content">
                  {renderMarkdown(modalState.content)}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default JoinRegister;
