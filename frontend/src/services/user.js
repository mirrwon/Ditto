import { readStoredUser } from "./session";

export const getStoredUsername = () => {
  try {
    const user = readStoredUser();
    return user?.user_name || user?.username || "";
  } catch (error) {
    return "";
  }
};
