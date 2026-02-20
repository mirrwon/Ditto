import { useState } from "react";
import "../../pages/Home.css";

const FAQ_list = [
  {
    id: 1,
    q: "식물 추천은 어떻게 이루어지나요?",
    a: "실내 이미지를 업로드하면 공간 분석과 선택 옵션을 기반으로 맞춤 식물을 추천해드립니다.",
  },
  {
    id: 2,
    q: "추천받은 식물은 실제 공간에 어떻게 적용되나요?",
    a: "공간 환경을 분석해 적합한 위치에 식물을 합성한 최종 이미지를 제공합니다.",
  },
  {
    id: 3,
    q: "다마고치 기능은 무엇인가요?",
    a: "업로드한 공간이 픽셀아트 방으로 변환되며, 식물 특성에 맞는 캐릭터가 대화를 제공합니다.",
  },
];

const FAQ_more = [
  {
    id: 1,
    q: "옵션은 꼭 선택해야 하나요?",
    a: "아니요. 알러지, 반려동물, 분위기 등은 선택사항이며 입력한 정보에 따라 추천이 달라집니다.",
  },
  {
    id: 2,
    q: "이미지는 저장할 수 있나요?",
    a: "네. 저장하면 식물게시판 타임로그에 자동 등록됩니다.",
  },
  {
    id: 3,
    q: "타임로그는 무엇인가요?",
    a: "물주기, 비료주기 등 식물 관리 기록을 남길 수 있는 기능입니다.",
  },
  {
    id: 4,
    q: "다이어리는 무엇인가요?",
    a: "식물 사진과 함께 일기를 작성하는 기록 공간입니다.",
  },
  {
    id: 5,
    q: "식물도감과 지도 기능은 무엇인가요?",
    a: "식물 검색 및 관리법 확인이 가능하며, 주변 꽃집 정보도 제공합니다.",
  },
];

const FAQs = () => {
  const [open, setOpen] = useState(false);

  return (
    <section className="faq">
      <div className="catalog-header catalog-header--faq">
        <div className="catalog-header__left">
          <h2 className="catalog-title faq__title">FAQ</h2>
        </div>
        <button
          className="catalog-more"
          type="button"
          onClick={() => setOpen(true)}
        >
          MORE
        </button>
      </div>
      <div className="catalog-divider" />

      <ol className="faq__list">
        {FAQ_list.map((item, idx) => (
          <li key={item.id} className="faq__item">
            <span className="faq__number">Q{idx + 1}.</span>
            <p className="faq__question">{item.q}</p>
            <p className="faq__answer">{item.a}</p>
          </li>
        ))}
      </ol>

      {open && (
        <div className="faq-modal" role="dialog" aria-modal="true">
          <button
            className="faq-modal__backdrop"
            type="button"
            onClick={() => setOpen(false)}
            aria-label="닫기"
          />
          <div className="faq-modal__panel">
            <div className="faq-modal__header">
              <h3 className="faq-modal__title">자주 묻는 질문</h3>
              <button
                className="faq-modal__close"
                type="button"
                onClick={() => setOpen(false)}
              >
                닫기
              </button>
            </div>
            <ul className="faq-modal__list">
              {FAQ_more.map((item, idx) => (
                <li key={item.id} className="faq-modal__item">
                  <span className="faq-modal__number">Q{idx + 1}.</span>
                  <div className="faq-modal__content">
                    <p className="faq-modal__question">{item.q}</p>
                    <p className="faq-modal__answer">{item.a}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
};

export default FAQs;
