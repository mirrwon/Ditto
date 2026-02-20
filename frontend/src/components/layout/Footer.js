import "./Footer.css";

const Footer = () => {
  return (
    <footer className="site-footer">
      <div className="site-footer__content">
        <div className="site-footer__brand">
          <h3 className="site-footer__logo">Ditto</h3>
          <p className="site-footer__muted">© 2026 Ditto.</p>
        </div>

        <div className="site-footer__cols">
          <div className="site-footer__col">
            <p className="site-footer__title">BRAND STORY</p>
            <p className="site-footer__text">
              작은 초록을 일상으로,
              <br />
              Ditto가 전하는 식물 이야기.
            </p>
          </div>

          <div className="site-footer__col">
            <p className="site-footer__title">CONTACT</p>
            <p className="site-footer__text">help@ditto.com</p>
            <p className="site-footer__text">000-0000-0000</p>
          </div>

          <div className="site-footer__col">
            <p className="site-footer__title">INFO</p>
            <p className="site-footer__text">Seoul, Korea</p>
            <p className="site-footer__text">Biz 000-00-00000</p>
          </div>
        </div>
      </div>

      <div className="site-footer__bottom"/>
      
    </footer>
  );
};

export default Footer;
