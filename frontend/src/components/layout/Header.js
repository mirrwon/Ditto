import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ROUTES } from "../../constants/routes";
import "./Header.css";

const Header = ({ user, onLogout }) => {
  const nav = useNavigate();
  const location = useLocation();
  const [isLoading, setIsLoading] = useState(false);

  const closeMenu = () => {
  };

  const startLoadingThen = (fn) => {
    setIsLoading(true);

    window.setTimeout(() => {
      fn();

      setIsLoading(false);
    }, 400);
  };

  const handleNavClick = (path, beforeNavigate, isEnabled = true) => (e) => {
    if (!isEnabled) {
      e.preventDefault();
      return;
    }
    if (e?.ctrlKey || e?.metaKey) {
      return;
    }
    e.preventDefault();
    if (beforeNavigate) beforeNavigate();
    navigateOrReload(path);
  };

  const navigateOrReload = (path) => {
    closeMenu();

    if (location.pathname === path) {
      startLoadingThen(() => window.location.reload());
      return;
    }

    startLoadingThen(() => nav(path));
  };

  const goPlantBoard = () => {
    try {
      localStorage.removeItem("plantboard_selected_plant");
      localStorage.setItem("plantboard_active_view", "timelog");
    } catch {}
  };
  const goLogin = () => navigateOrReload(ROUTES.LOGIN);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    closeMenu();
    if (onLogout) onLogout();
    startLoadingThen(() => nav(ROUTES.LOGIN));
  };

  return (
    <>
      {isLoading && (
        <div className="loading-overlay" aria-live="polite" aria-busy="true">
          <div className="loading-spinner" />
        </div>
      )}

    <header className={`header ${location.pathname === ROUTES.HOME ? "header--home" : "header--default"}`}>
    <div className="header-top">
      <a
        className="header-logo typo-title"
        href={ROUTES.HOME}
        onClick={handleNavClick(ROUTES.HOME)}
        role="button"
        tabIndex={0}
      >
        Ditto
      </a>

      <nav className="header-nav">
        <a
          className="header-link"
          href={ROUTES.HOME}
          onClick={handleNavClick(ROUTES.HOME)}
        >
          Home
        </a>

        <a
          className="header-link"
          href={ROUTES.MYINFO}
          aria-disabled={!user}
          tabIndex={user ? 0 : -1}
          onClick={handleNavClick(ROUTES.MYINFO, undefined, !!user)}
        >
          Profile
        </a>

        <a
          className="header-link"
          href={ROUTES.UPLOAD}
          aria-disabled={!user}
          tabIndex={user ? 0 : -1}
          onClick={handleNavClick(ROUTES.UPLOAD, undefined, !!user)}
        >
          Chat
        </a>

        <a
          className="header-link"
          href={ROUTES.PLANTBOARD}
          aria-disabled={!user}
          tabIndex={user ? 0 : -1}
          onClick={handleNavClick(ROUTES.PLANTBOARD, goPlantBoard, !!user)}
        >
          PlantBoard
        </a>

        <a
          className="header-link"
          href={ROUTES.PLANT_DATA}
          onClick={handleNavClick(ROUTES.PLANT_DATA)}
        >
          Data
        </a>

        <a
          className="header-link"
          href={ROUTES.MAP}
          aria-disabled={!user}
          tabIndex={user ? 0 : -1}
          onClick={handleNavClick(ROUTES.MAP, undefined, !!user)}
        >
          Map
        </a>
        <button
          className="header-link header-auth"
          type="button"
          onClick={user ? handleLogout : goLogin}
        >
          {user ? "Logout" : "Login"}
        </button>
      </nav>
    </div>
      </header>
    </>
  );
};

export default Header;
