import { useMemo } from "react";

import { Swiper, SwiperSlide } from "swiper/react";
import { Autoplay, Pagination } from "swiper/modules";
import "swiper/css";
import "swiper/css/pagination";


 // ProcessCarousel (Before / After)
export default function ProcessCarousel({ autoplayDelay = 2500 }) {

  const sets = useMemo(
    () => [
      {
        id: "set1",
        before: "/images/ex1-before.jpg",
        after: "/images/ex1-after.png",
      },
      {
        id: "set2",
        before: "/images/ex2-before.jpg",
        after: "/images/ex2-after.png",
      },
      {
        id: "set3",
        before: "/images/ex3-before.jpg",
        after: "/images/ex3-after.png",
      },
    ],
    []
  );

  return (
    <section className="home-carousel">
      <Swiper
        modules={[Autoplay, Pagination]}
        loop
        autoplay={{ delay: autoplayDelay, disableOnInteraction: false }}
        pagination={{ clickable: true }}
        spaceBetween={16}
        slidesPerView={1} //  한 슬라이드에 "세트 1개(비포/애프터 2장)"
      >
        {sets.map((s) => (
          <SwiperSlide key={s.id}>
            <article className="process-card">
              <div className="ba-grid">
                <figure className="ba-item">
                  <img className="ba-img" src={s.before} alt="before" />
                </figure>

                <figure className="ba-item">
                  <img className="ba-img" src={s.after} alt="after" />
                </figure>
              </div>
            </article>
          </SwiperSlide>
        ))}
      </Swiper>
    </section>
  );
}
