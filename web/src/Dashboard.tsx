import { useCallback, useEffect, useState } from "react";
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Center,
  CopyButton,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  ApiError,
  createLink,
  deleteLink,
  listLinks,
  shortUrl,
  type Link,
} from "./api";
import LinkStatsModal from "./LinkStatsModal";
import classes from "./modules/Dashboard.module.css";

function Logo() {
  return (
    <div className={classes.logo}>
      <img className={classes.logoImg} src="/url_logo.svg" alt="URL Shorty logo" />
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Accept bare domains like "example.com" by defaulting to https:// — the
// backend requires a full URL with a scheme.
function normalizeUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

interface DashboardProps {
  onLogout: () => void;
}

export default function Dashboard({ onLogout }: DashboardProps) {
  const [links, setLinks] = useState<Link[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [alias, setAlias] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [statsLink, setStatsLink] = useState<Link | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const data = await listLinks();
      setLinks(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onLogout();
        return;
      }
      setLoadError(
        err instanceof ApiError
          ? err.message
          : "Could not load your links. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [onLogout]);

  useEffect(() => {
    load();
  }, [load]);

  function openModal() {
    setUrl("");
    setAlias("");
    setCreateError(null);
    setModalOpen(true);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);

    if (!url.trim()) {
      setCreateError("Please enter a URL to shorten.");
      return;
    }

    setCreating(true);
    try {
      const link = await createLink({
        original_url: normalizeUrl(url),
        custom_alias: alias.trim() || undefined,
      });
      setLinks((prev) => [link, ...prev]);
      setModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onLogout();
        return;
      }
      setCreateError(
        err instanceof ApiError
          ? err.message
          : "Could not create the link. Please try again.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteLink(id);
      setLinks((prev) => prev.filter((l) => l.id !== id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onLogout();
        return;
      }
      // Surface failures inline via the load error banner; keep it simple.
      setLoadError(
        err instanceof ApiError
          ? err.message
          : "Could not delete the link. Please try again.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  const rows = links.map((link) => {
    const full = shortUrl(link.short_code);
    return (
      <Table.Tr
        key={link.id}
        className={classes.row}
        onClick={() => setStatsLink(link)}
      >
        <Table.Td>
          <Anchor
            href={full}
            target="_blank"
            rel="noreferrer"
            fw={600}
            onClick={(e) => e.stopPropagation()}
          >
            /{link.short_code}
          </Anchor>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" truncate maw={360} title={link.original_url}>
            {link.original_url}
          </Text>
        </Table.Td>
        <Table.Td>
          <Badge variant="light" color="dark" radius="sm">
            {link.click_count} {link.click_count === 1 ? "click" : "clicks"}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed">
            {formatDate(link.created_at)}
          </Text>
        </Table.Td>
        <Table.Td>
          <Group gap="xs" justify="flex-end" wrap="nowrap">
            <Tooltip label="View analytics" withArrow>
              <ActionIcon
                variant="subtle"
                color="gray"
                onClick={(e) => {
                  e.stopPropagation();
                  setStatsLink(link);
                }}
                aria-label="View analytics"
              >
                <ChartIcon />
              </ActionIcon>
            </Tooltip>
            <CopyButton value={full}>
              {({ copied, copy }) => (
                <Tooltip label={copied ? "Copied!" : "Copy short link"} withArrow>
                  <ActionIcon
                    variant="subtle"
                    color={copied ? "teal" : "gray"}
                    onClick={(e) => {
                      e.stopPropagation();
                      copy();
                    }}
                    aria-label="Copy short link"
                  >
                    <CopyIcon />
                  </ActionIcon>
                </Tooltip>
              )}
            </CopyButton>
            <Tooltip label="Delete" withArrow>
              <ActionIcon
                variant="subtle"
                color="red"
                loading={deletingId === link.id}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(link.id);
                }}
                aria-label="Delete link"
              >
                <TrashIcon />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Table.Td>
      </Table.Tr>
    );
  });

  return (
    <Box className={classes.page}>
      <div className={classes.container}>
        <Group justify="space-between" align="center" mb="xl">
          <Group gap="sm">
            <Logo />
            <Title order={3} fw={700} c="#1a1a1a">
              Your links
            </Title>
          </Group>
          <Group gap="sm">
            <Button
              size="md"
              radius="md"
              color="dark"
              onClick={openModal}
              leftSection={<PlusIcon />}
            >
              Create
            </Button>
            <Button size="md" radius="md" variant="subtle" color="gray" onClick={onLogout}>
              Sign out
            </Button>
          </Group>
        </Group>

        {loadError && (
          <Alert color="red" radius="md" variant="light" mb="md">
            {loadError}
          </Alert>
        )}

        {loading ? (
          <Center py={80}>
            <Loader color="dark" />
          </Center>
        ) : links.length === 0 ? (
          <div className={classes.empty}>
            <Text fw={600} c="#1a1a1a" size="lg">
              No links yet
            </Text>
            <Text c="dimmed" size="sm" mt={4} mb="lg">
              Create your first short link to start tracking clicks.
            </Text>
            <Button
              size="md"
              radius="md"
              color="dark"
              onClick={openModal}
              leftSection={<PlusIcon />}
            >
              Create a link
            </Button>
          </div>
        ) : (
          <div className={classes.tableCard}>
            <Table verticalSpacing="md" horizontalSpacing="lg" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Short link</Table.Th>
                  <Table.Th>Destination</Table.Th>
                  <Table.Th>Clicks</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>{rows}</Table.Tbody>
            </Table>
          </div>
        )}
      </div>

      <Modal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        title={
          <Text fw={700} c="#1a1a1a">
            Create a new link
          </Text>
        }
        radius="md"
        centered
      >
        <form onSubmit={handleCreate}>
          <Stack gap="md">
            {createError && (
              <Alert color="red" radius="md" variant="light" py="xs">
                {createError}
              </Alert>
            )}

            <TextInput
              label="Destination URL"
              placeholder="https://example.com/very/long/link"
              size="md"
              radius="md"
              value={url}
              onChange={(e) => setUrl(e.currentTarget.value)}
              disabled={creating}
              data-autofocus
              required
            />

            <TextInput
              label="Custom alias"
              description="Optional. 3–16 letters, numbers, - or _. Leave blank for a random code."
              placeholder="my-link"
              size="md"
              radius="md"
              value={alias}
              onChange={(e) => setAlias(e.currentTarget.value)}
              disabled={creating}
            />

            <Group justify="flex-end" mt="xs">
              <Button
                variant="subtle"
                color="gray"
                radius="md"
                onClick={() => setModalOpen(false)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button type="submit" color="dark" radius="md" loading={creating}>
                Create link
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <LinkStatsModal
        linkId={statsLink?.id ?? null}
        shortCode={statsLink?.short_code ?? ""}
        onClose={() => setStatsLink(null)}
        onUnauthorized={onLogout}
      />
    </Box>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 5v14M5 12h14"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 20V10M10 20V4M16 20v-7M22 20H2"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect
        x="9"
        y="9"
        width="11"
        height="11"
        rx="2"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M5 15V5a2 2 0 0 1 2-2h10"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
