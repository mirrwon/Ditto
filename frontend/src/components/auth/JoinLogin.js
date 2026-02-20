import { useEffect, useState } from "react";
import { storeUser } from "../../services/session";

const GOOGLE_OAUTH_URL = "http://localhost:8000/api/auth/google";

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

const JoinLogin = ({ onSubmit }) => {
  const [formData, setFormData] = useState({
    username: "",
    password: "",
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") !== "google") return;
    const payload = params.get("payload");
    if (!payload) return;
    const data = decodePayload(payload);
    if (!data) return;
    storeUser(data);
    if (data.needsProfile) {
      window.location.replace(
        `/register?oauth=google&payload=${encodeURIComponent(payload)}`
      );
      return;
    }
    window.location.replace("/");
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value,
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const handleGoogleLogin = () => {
    window.location.href = GOOGLE_OAUTH_URL;
  };

  return (
    <form className="join-login" onSubmit={handleSubmit}>
      <div className="join-login__row">
        <input
          className="ui-input"
          type="text"
          name="username"
          value={formData.username}
          onChange={handleChange}
          placeholder="아이디"
        />
      </div>

      <div className="join-login__row">
        <input
          className="ui-input"
          type="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          placeholder="비밀번호"
        />
      </div>

      <div className="ui-line login-bottom-line" />

      <div className="join-login__row">
        <button className="ui-btn ui-btn-secondary" type="button" onClick={handleGoogleLogin}>
          Google로 로그인
        </button>
      </div>

      <button className="ui-btn ui-btn-primary" type="submit">
        로그인
      </button>
    </form>
  );
};

export default JoinLogin;
