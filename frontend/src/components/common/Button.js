// components/common/Button.js
// 버튼 스타일 통일, 중앙에서 관리

const Button = ({
  text,
  type = "primary",
  onClick,
  value,
  className = "",   
  ...rest
}) => {
  
  const uiClass =
    type === "primary"
      ? "ui-btn ui-btn-primary"
      : "ui-btn ui-btn-ghost";

  return (
    <button
      type="button"
      value={value}
      onClick={onClick}
      className={`${uiClass} ${className}`}  
      {...rest}
    >
      {text}
    </button>
  );
};

export default Button;
