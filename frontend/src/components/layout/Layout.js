import { useLocation } from "react-router-dom";
import Header from "./Header";
import Footer from "./Footer";
import { ROUTES } from "../../constants/routes";

const Layout = ({ user, children, onLogout }) => {
  const { pathname } = useLocation();

  // 헤더 숨길 페이지들
  const hideHeaderPaths = [ROUTES.LOGIN, ROUTES.REGISTER];
  const shouldHideHeader = hideHeaderPaths.includes(pathname);

  return (
  <>
    {!shouldHideHeader && (
      <div className="l-cover-center">
        <Header user={user} onLogout={onLogout} />
      </div>
    )}

    <main className="l-cover">
      <div className="l-cover-center">{children}</div>
    </main>
    <div className="l-cover-center">
      <Footer />
    </div>
  </>
);

};

export default Layout;
