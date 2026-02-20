import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api from "../services/api";
import { readStoredUser } from "../services/session";
import "./Map.css";

const DEFAULT_RADIUS = 3000;

const formatDistance = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "";
  if (parsed >= 1000) {
    const km = (parsed / 1000).toFixed(parsed >= 10000 ? 0 : 1);
    return `${km}km`;
  }
  return `${Math.round(parsed)}m`;
};

const resolveErrorMessage = (error) => {
  const detail = error?.response?.data?.detail;
  if (detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item?.msg).filter(Boolean).join(" ");
    }
  }
  return "꽃집 정보를 불러오지 못했어요.";
};

const MapPage = () => {
  const [shops, setShops] = useState([]);
  const [address, setAddress] = useState("");
  const [coord, setCoord] = useState(null);
  const [error, setError] = useState("");
  const [mapError, setMapError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedShop, setSelectedShop] = useState(null);

  const storedUser = useMemo(() => readStoredUser(), []);
  const kakaoKey = useMemo(() => process.env.REACT_APP_KAKAO_JS_KEY || "", []);
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const markerByKeyRef = useRef(new Map());
  const infoWindowRef = useRef(null);
  const kakaoLoaderRef = useRef(null);
  const focusTimerRef = useRef(null);

  const getShopKey = useCallback((shop) => {
    if (!shop) return "";
    return (
      shop.id ||
      `${shop.name || ""}|${shop.address || ""}|${shop.x || ""}|${shop.y || ""}`
    );
  }, []);

  const loadKakaoSdk = useCallback(() => {
    if (window.kakao && window.kakao.maps) {
      return Promise.resolve(window.kakao);
    }
    if (!kakaoKey) {
      return Promise.reject(new Error("missing_kakao_key"));
    }
    if (kakaoLoaderRef.current) return kakaoLoaderRef.current;

    kakaoLoaderRef.current = new Promise((resolve, reject) => {
      const existing = document.getElementById("kakao-map-sdk");
      if (existing) {
        existing.addEventListener("load", () => {
          if (window.kakao && window.kakao.maps) {
            window.kakao.maps.load(() => resolve(window.kakao));
          } else {
            reject(new Error("kakao_sdk_unavailable"));
          }
        });
        existing.addEventListener("error", () =>
          reject(new Error("kakao_sdk_load_failed"))
        );
        return;
      }

      const script = document.createElement("script");
      script.id = "kakao-map-sdk";
      script.async = true;
      script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${kakaoKey}&autoload=false`;
      script.onload = () => {
        if (window.kakao && window.kakao.maps) {
          window.kakao.maps.load(() => resolve(window.kakao));
        } else {
          reject(new Error("kakao_sdk_unavailable"));
        }
      };
      script.onerror = () => reject(new Error("kakao_sdk_load_failed"));
      document.head.appendChild(script);
    });

    return kakaoLoaderRef.current;
  }, [kakaoKey]);

  const fetchShops = useCallback(async () => {
    if (!storedUser) {
      setError("로그인 정보가 필요합니다.");
      setShops([]);
      setAddress("");
      setCoord(null);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await api.get("/api/map/flowers", {
        params: { radius: DEFAULT_RADIUS, include_parking: true },
      });

      const payload = response?.data;
      if (!payload?.ok) {
        setError("꽃집 정보를 불러오지 못했어요.");
        setShops([]);
        setAddress("");
        return;
      }

      const nextItems = Array.isArray(payload.items) ? payload.items : [];
      setShops(nextItems);
      if (nextItems.length > 0) {
        setSelectedShop((prev) => prev || nextItems[0]);
      }

      setAddress(payload.address || "");
      if (payload?.coord?.x && payload?.coord?.y) {
        setCoord({
          x: Number(payload.coord.x),
          y: Number(payload.coord.y),
        });
      } else {
        setCoord(null);
      }
    } catch (err) {
      setError(resolveErrorMessage(err));
      setShops([]);
      setAddress("");
      setCoord(null);
    } finally {
      setLoading(false);
    }
  }, [storedUser]);

  useEffect(() => {
    fetchShops();
  }, [fetchShops]);

  const focusShopOnMap = useCallback(
    (shop) => {
      if (!shop) return;
      const key = getShopKey(shop);
      if (!key) return;

      loadKakaoSdk()
        .then((kakao) => {
          const map = mapRef.current;
          const entry = markerByKeyRef.current.get(key);
          if (!map || !entry?.marker) return;

          const { marker, shop: entryShop } = entry;
          const position = marker.getPosition();

          if (focusTimerRef.current) {
            clearTimeout(focusTimerRef.current);
            focusTimerRef.current = null;
          }

          map.panTo(position);

          const name = entryShop?.name || "꽃집";
          const addr = entryShop?.road_address || entryShop?.address || "";
          const content = `
            <div style="padding:6px 8px;font-size:12px;line-height:1.4;">
              <strong>${name}</strong><br />
              ${addr}
            </div>
          `;

          if (!infoWindowRef.current) {
            infoWindowRef.current = new kakao.maps.InfoWindow({ zIndex: 1 });
          }
          infoWindowRef.current.setContent(content);
          infoWindowRef.current.open(map, marker);

          const baseImage = marker.getImage();
          if (baseImage) {
            marker.setZIndex(10);
            focusTimerRef.current = setTimeout(() => {
              marker.setZIndex(0);
            }, 1200);
          }
        })
        .catch(() => {
          setMapError("지도에서 위치를 표시하지 못했어요.");
        });
    },
    [getShopKey, loadKakaoSdk]
  );

  useEffect(() => {
    if (!coord || !mapContainerRef.current) return;

    let cancelled = false;

    loadKakaoSdk()
      .then((kakao) => {
        if (cancelled || !mapContainerRef.current) return;
        setMapError("");

        const center = new kakao.maps.LatLng(coord.y, coord.x);
        if (!mapRef.current) {
          mapRef.current = new kakao.maps.Map(mapContainerRef.current, {
            center,
            level: 4,
          });
        } else {
          mapRef.current.setCenter(center);
        }

        markersRef.current.forEach((marker) => marker.setMap(null));
        markersRef.current = [];
        markerByKeyRef.current = new Map();

        const bounds = new kakao.maps.LatLngBounds();
        bounds.extend(center);

        const homeMarker = new kakao.maps.Marker({
          position: center,
          map: mapRef.current,
          title: "현재 위치",
        });
        markersRef.current.push(homeMarker);

        if (!infoWindowRef.current) {
          infoWindowRef.current = new kakao.maps.InfoWindow({ zIndex: 1 });
        }

        shops.forEach((shop) => {
          const lat = Number(shop?.y);
          const lng = Number(shop?.x);
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

          const position = new kakao.maps.LatLng(lat, lng);
          bounds.extend(position);

          const marker = new kakao.maps.Marker({
            position,
            map: mapRef.current,
            title: shop?.name || "",
          });

          kakao.maps.event.addListener(marker, "click", () => {
            const name = shop?.name || "꽃집";
            const addr = shop?.road_address || shop?.address || "";
            const content = `
              <div style="padding:6px 8px;font-size:12px;line-height:1.4;">
                <strong>${name}</strong><br />
                ${addr}
              </div>
            `;
            infoWindowRef.current?.setContent(content);
            infoWindowRef.current?.open(mapRef.current, marker);
            setSelectedShop(shop);
          });

          markersRef.current.push(marker);
          const shopKey = getShopKey(shop);
          if (shopKey) {
            markerByKeyRef.current.set(shopKey, { marker, shop });
          }
        });

        if (shops.length > 0) {
          mapRef.current.setBounds(bounds);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err?.message === "missing_kakao_key") {
          setMapError("Kakao 지도 키가 필요합니다. .env를 확인해주세요.");
        } else {
          setMapError("Kakao 지도를 불러오지 못했어요.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [coord, loadKakaoSdk, shops, getShopKey]);

  return (
    <div className="l-cover map-page">
      <div className="l-cover-center map-center">
        <h1 className="map-title">Store</h1>
        <div className="map-divider" />

        <section className="map-panel">
          <div className="map-info">
            <p className="map-label">현재 위치</p>
            <p className="map-address">
              {address || "위치 정보를 불러오는 중입니다."}
            </p>
            <p className="map-radius">검색 반경: 3km</p>
          </div>
          <div className="map-actions">
            <button
              type="button"
              className="ui-btn ui-btn-primary ui-btn--compact map-refresh"
              onClick={fetchShops}
              disabled={loading}
            >
              다시 검색
            </button>
          </div>
        </section>

        <section className="map-layout">
          <aside className="map-sidebar">
            <p className="map-sidebar__title">내 주변 꽃집</p>
            <ul className="map-sidebar__list">
              {shops.map((shop) => (
                <li key={getShopKey(shop)}>
                  <button
                    type="button"
                    className={`map-sidebar__item ${
                      selectedShop === shop ? "active" : ""
                    }`}
                    onClick={() => {
                      setSelectedShop(shop);
                      focusShopOnMap(shop);
                    }}
                  >
                    {shop?.name || "꽃집"}
                  </button>
                </li>
              ))}
            </ul>
            <div className="map-detail">
              <div className="map-detail__body">
                <h2 className="map-detail__title">
                  {selectedShop?.name || "꽃집을 선택하세요"}
                </h2>
                <p className="map-detail__address">
                  {selectedShop?.road_address || selectedShop?.address || "-"}
                </p>
                {selectedShop?.phone ? (
                  <p className="map-detail__meta">{selectedShop.phone}</p>
                ) : null}
                {selectedShop?.distance ? (
                  <p className="map-detail__meta">
                    거리: {formatDistance(selectedShop.distance)}
                  </p>
                ) : null}
              </div>
            </div>
          </aside>

          <div className="map-canvas-wrap">
            {mapError ? <p className="map-error">{mapError}</p> : null}
            {!coord && !error ? (
              <p className="map-status">잠시만 기다려주세요.</p>
            ) : null}
            <div ref={mapContainerRef} className="map-canvas" />
          </div>
        </section>

        {loading ? <p className="map-status">불러오는 중..</p> : null}
        {error ? <p className="map-error">{error}</p> : null}
        {!loading && !error && shops.length === 0 ? (
          <p className="map-status">주변 꽃집을 찾지 못했어요.</p>
        ) : null}
      </div>
    </div>
  );
};

export default MapPage;
