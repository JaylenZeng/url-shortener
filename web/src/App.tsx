import "@mantine/core/styles.css";
import "@mantine/carousel/styles.css";
import { useState } from "react";
import { MantineProvider } from "@mantine/core";
import { theme } from "./theme";
import LoginPage from "./LoginPage";
import Dashboard from "./Dashboard";
import { clearToken, getToken } from "./api";

export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => getToken() !== null);

  function handleLogout() {
    clearToken();
    setAuthed(false);
  }

  return (
    <MantineProvider theme={theme}>
      {authed ? (
        <Dashboard onLogout={handleLogout} />
      ) : (
        <LoginPage onAuthenticated={() => setAuthed(true)} />
      )}
    </MantineProvider>
  );
}
