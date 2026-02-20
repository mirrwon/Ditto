import { useEffect, useMemo, useState } from "react";
import api from "../../services/api";
import { Swiper, SwiperSlide } from "swiper/react";
import { Autoplay } from "swiper/modules";
import "swiper/css";
import "swiper/css/pagination";

const buildImageUrl = (baseUrl, url) => {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  if (!baseUrl) return url;
  return `${baseUrl}${url}`;
};

const PlantPreview = ({ autoplayDelay = 2500 }) => {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [imageFallbackIndex, setImageFallbackIndex] = useState({});
  const maxSlidesPerView = 6;

  const baseUrl = useMemo(() => api.defaults.baseURL || "", []);
  const canLoop = items.length > maxSlidesPerView;

  useEffect(() => {
    const cacheKey = "plantPreviewCache_v1";
    const cacheTtlMs = 1000 * 60 * 10;

    const loadFromCache = () => {
      try {
        const raw = window.localStorage.getItem(cacheKey);
        if (!raw) return false;
        const parsed = JSON.parse(raw);
        if (!parsed?.ts || !Array.isArray(parsed?.items)) return false;
        if (Date.now() - parsed.ts > cacheTtlMs) return false;
        setItems(parsed.items);
        return true;
      } catch {
        return false;
      }
    };

    const saveToCache = (nextItems) => {
      try {
        window.localStorage.setItem(
          cacheKey,
          JSON.stringify({ ts: Date.now(), items: nextItems })
        );
      } catch {
        // ignore cache errors
      }
    };

    const fetchPlants = async () => {
      try {
        const res = await api.get("/api/plants", {
          params: { offset: 0, limit: 40 },
        });
        const nextItems = Array.isArray(res?.data?.items) ? res.data.items : [];
        setItems(nextItems);
        saveToCache(nextItems);
      } catch {
        setError("Failed to load plants.");
      }
    };

    if (!loadFromCache()) {
      fetchPlants();
    }
  }, []);

  if (error) return <p className="catalog-status">{error}</p>;

  const getImageCandidates = (url) => {
    if (!url) return [];
    const [basePart, queryPart] = url.split("?");
    const query = queryPart ? `?${queryPart}` : "";
    const match = basePart.match(/^(.*?)(\.[a-z0-9]+)$/i);
    if (!match) return [url];
    const stem = match[1];
    const ext = match[2].toLowerCase();
    const candidates = [
      url,
      `${stem}.gif${query}`,
      `${stem}.jpg${query}`,
      `${stem}.png${query}`,
      `${stem}.jpeg${query}`,
    ];
    return Array.from(new Set(candidates.filter(Boolean))).filter((item) => item !== url || ext);
  };

  return (
    <div className="plant-preview-marquee">
      <Swiper
        modules={[Autoplay]}
        spaceBetween={12} /* Tighter spacing for more items */
        slidesPerView={3}
        slidesPerGroup={2}
        breakpoints={{
          600: { slidesPerView: 3 },
          900: { slidesPerView: 4 },
          1200: { slidesPerView: 5 },
          1600: { slidesPerView: maxSlidesPerView },
        }}
        loop={canLoop}
        autoplay={{
          delay: autoplayDelay,
          disableOnInteraction: false,
        }}
        className="plant-preview-swiper"
      >
        {items.map((plant, index) => {
          const key = `${plant.id || plant.name}-${index}`;
          const baseImage = plant.image ? buildImageUrl(baseUrl, plant.image) : "";
          const candidates = getImageCandidates(baseImage);
          const fallbackIndex = imageFallbackIndex[key] || 0;
          const imageUrl = candidates[fallbackIndex] || candidates[0];
          const handleImageError = () => {
            if (candidates.length <= 1) return;
            setImageFallbackIndex((prev) => {
              const current = prev[key] || 0;
              const next = current + 1;
              if (next >= candidates.length) return prev;
              return { ...prev, [key]: next };
            });
          };

          return (
            <SwiperSlide key={key}>
              <article className="plant-preview-card">
                {imageUrl ? (
                  <img
                    src={imageUrl}
                    alt={plant.name}
                    className="plant-preview-image"
                    loading="lazy"
                    onError={handleImageError}
                  />
                ) : (
                  <div className="plant-preview-image plant-preview-image--placeholder" />
                )}
                <p className="plant-preview-name">{plant.name}</p>
              </article>
            </SwiperSlide>
          );
        })}
      </Swiper>
    </div>
  );
};

export default PlantPreview;
