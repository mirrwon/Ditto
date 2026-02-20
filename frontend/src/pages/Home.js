import { useNavigate } from "react-router-dom";
import ProcessCarousel from "../components/home/ProcessCarousel";
import FAQs from "../components/home/FAQs";
import PlantPreview from "../components/home/PlantPreview";
import { ROUTES } from "../constants/routes";
import "./Home.css";

const Home = () => {
  const nav = useNavigate();
  const sharedAutoplayDelay = 2500;
  // const nav = useNavigate();

  // const goChat = () => {
  //   nav(ROUTES.CHAT)
  // }

  return (
    <div className="home">
      <section className="home-section">
        <ProcessCarousel autoplayDelay={sharedAutoplayDelay} />
      </section>

      <section className="home-section home-plants">
        <div className="catalog-header">
          <div className="catalog-header__left">
            <h2 className="catalog-title">Plant Catalog</h2>
          </div>
          <button
            className="catalog-more"
            type="button"
            onClick={() => nav(ROUTES.PLANT_DATA)}
          >
            MORE
          </button>
        </div>

        <div className="catalog-divider" />
        <PlantPreview />
        
      </section>

      <section className="home-section">
        <FAQs />
      </section>

    </div>
  );
};

export default Home;
