import { useState } from "react";
import {
  Alert,
  Anchor,
  Button,
  Group,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  ApiError,
  login,
  register,
  storeToken,
  type TokenResponse,
} from "./api";
import ProjectShowcase from "./ProjectShowcase";
import classes from "./modules/LoginPage.module.css";

function Logo() {
  return (
    <div className={classes.logo}>
      <img className={classes.logoImg} src="/url_logo.svg" alt="URL Shorty logo" />
    </div>
  );
}

type Mode = "login" | "register";

interface LoginPageProps {
  onAuthenticated: () => void;
}

export default function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const isRegister = mode === "register";

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setSuccess(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    if (isRegister && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      let tokens: TokenResponse;
      if (isRegister) {
        // Registration returns the created user (no token), so log in right
        // after to get a session going seamlessly.
        await register(email, password);
        tokens = await login(email, password);
      } else {
        tokens = await login(email, password);
      }
      storeToken(tokens.access_token);
      setPassword("");
      // Session established and the JWT is stored — hand off to the dashboard.
      onAuthenticated();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={classes.page}>
      <div className={classes.left}>
        <div className={classes.formArea}>
          <form className={classes.form} onSubmit={handleSubmit}>
            <Logo />

            <Title order={2} ta="center" fw={700} c="#1a1a1a">
              {isRegister ? "Create your account" : "Welcome Back"}
            </Title>
            <Text ta="center" c="dimmed" size="sm" mt={6} mb="xl">
              {isRegister
                ? "Enter your email and a password to get started."
                : "Enter your username and password to continue."}
            </Text>

            <Stack gap="md">
              {error && (
                <Alert color="red" radius="md" variant="light" py="xs">
                  {error}
                </Alert>
              )}

              {success && (
                <Alert color="teal" radius="md" variant="light" py="xs">
                  {success}
                </Alert>
              )}

              <TextInput
                label="Email"
                placeholder="Enter your email address"
                type="email"
                autoComplete="email"
                size="md"
                radius="md"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                disabled={loading}
                required
              />

              <PasswordInput
                label="Password"
                placeholder="Enter your password"
                autoComplete={isRegister ? "new-password" : "current-password"}
                size="md"
                radius="md"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                disabled={loading}
                required
              />

              {!isRegister && (
                <Group justify="space-between" align="center">
                  {/* <Checkbox label="Remember me" size="sm" color="dark" /> */}
                  {/* <Anchor href="#" size="sm" fw={600} c="#1a1a1a">
                    Forgot password
                  </Anchor> */}
                </Group>
              )}

              <Button
                type="submit"
                fullWidth
                size="md"
                radius="md"
                color="dark"
                mt="xs"
                loading={loading}
              >
                {isRegister ? "Create Account" : "Sign In"}
              </Button>
            </Stack>

            <Text ta="center" size="sm" c="dimmed" mt="xl">
              {isRegister ? (
                <>
                  Already have an account?{" "}
                  <Anchor
                    component="button"
                    type="button"
                    fw={600}
                    c="#1a1a1a"
                    onClick={() => switchMode("login")}
                  >
                    Sign in
                  </Anchor>
                </>
              ) : (
                <>
                  Don&apos;t have an account?{" "}
                  <Anchor
                    component="button"
                    type="button"
                    fw={600}
                    c="#1a1a1a"
                    onClick={() => switchMode("register")}
                  >
                    Register
                  </Anchor>
                </>
              )}
            </Text>
          </form>
        </div>

        <div className={classes.footer}>
          <Text size="xs" c="dimmed">
            © 2026 Jaylen Zeng. All rights reserved.
          </Text>
          <Group gap="lg">
            {/* <Anchor href="#" size="xs" c="#1a1a1a">
              Privacy Policy
            </Anchor>
            <Anchor href="#" size="xs" c="#1a1a1a">
              Term &amp; Condition
            </Anchor> */}
          </Group>
        </div>
      </div>

      <div className={classes.right}>
        <ProjectShowcase />
      </div>
    </div>
  );
}
