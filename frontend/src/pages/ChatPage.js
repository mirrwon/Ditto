import { useState } from "react";
import Chat from "../components/chat/Chat";
import Survey from "../components/chat/Survey";

const ChatPage = () => {
  const [surveyDone, setSurveyDone] = useState(false);

  if (!surveyDone) {
    return <Survey onComplete={() => setSurveyDone(true)} />;
  }

  return <Chat />;
};

export default ChatPage;
