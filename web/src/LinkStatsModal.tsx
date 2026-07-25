import { useEffect, useState } from "react";
import {
  Alert,
  Center,
  Divider,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import {
  ApiError,
  getLinkStats,
  type DailyClicks,
  type LinkStats,
} from "./api";
import classes from "./modules/LinkStatsModal.module.css";

interface LinkStatsModalProps {
  linkId: string | null;
  shortCode: string;
  onClose: () => void;
  onUnauthorized: () => void;
}

function formatDay(iso: string): string {
  // iso is a date like "2026-07-24"; parse as local calendar date.
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

// Vertical bars, one per active day. Single series → no legend; the section
// title names it. Bars share a scale, have rounded tops, a 2px gap, and a
// per-bar hover tooltip.
function DailyChart({ data }: { data: DailyClicks[] }) {
  const max = Math.max(...data.map((d) => d.clicks), 1);
  return (
    <div className={classes.chart} role="img" aria-label="Clicks by day">
      {data.map((d) => {
        const pct = (d.clicks / max) * 100;
        const label = `${formatDay(d.date)}: ${d.clicks} ${
          d.clicks === 1 ? "click" : "clicks"
        }`;
        return (
          <Tooltip key={d.date} label={label} withArrow position="top">
            <div className={classes.barCol}>
              <div className={classes.barTrack}>
                <div
                  className={classes.bar}
                  style={{ height: `max(4px, ${pct}%)` }}
                />
              </div>
              <span className={classes.barTick}>{formatDay(d.date)}</span>
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}

// Ranked horizontal bars. Label + count sit on the surface (ink tokens, always
// legible); the bar below encodes magnitude relative to the top entry.
function RankedList({
  items,
  emptyLabel,
}: {
  items: { label: string; clicks: number; muted?: boolean }[];
  emptyLabel: string;
}) {
  if (items.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {emptyLabel}
      </Text>
    );
  }
  const max = Math.max(...items.map((i) => i.clicks), 1);
  return (
    <Stack gap="sm">
      {items.map((item, i) => (
        <div key={i}>
          <Group justify="space-between" gap="xs" wrap="nowrap" mb={4}>
            <Text
              size="sm"
              c={item.muted ? "dimmed" : "#1a1a1a"}
              fs={item.muted ? "italic" : undefined}
              truncate
              title={item.label}
            >
              {item.label}
            </Text>
            <Text size="sm" fw={600} c="#1a1a1a">
              {item.clicks}
            </Text>
          </Group>
          <div className={classes.rankTrack}>
            <div
              className={classes.rankFill}
              style={{ width: `${(item.clicks / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </Stack>
  );
}

export default function LinkStatsModal({
  linkId,
  shortCode,
  onClose,
  onUnauthorized,
}: LinkStatsModalProps) {
  const [stats, setStats] = useState<LinkStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!linkId) return;
    let cancelled = false;
    setStats(null);
    setError(null);
    setLoading(true);
    getLinkStats(linkId)
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          onUnauthorized();
          return;
        }
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not load analytics. Please try again.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [linkId, onUnauthorized]);

  return (
    <Modal
      opened={linkId !== null}
      onClose={onClose}
      title={
        <Text fw={700} c="#1a1a1a">
          Analytics for <span className={classes.code}>/{shortCode}</span>
        </Text>
      }
      radius="md"
      size="lg"
      centered
    >
      {loading ? (
        <Center py={60}>
          <Loader color="dark" />
        </Center>
      ) : error ? (
        <Alert color="red" radius="md" variant="light">
          {error}
        </Alert>
      ) : stats ? (
        stats.total_clicks === 0 ? (
          <Center py={40}>
            <Stack align="center" gap={4}>
              <Text fw={600} c="#1a1a1a">
                No clicks yet
              </Text>
              <Text size="sm" c="dimmed">
                Analytics will appear once this link starts getting traffic.
              </Text>
            </Stack>
          </Center>
        ) : (
          <Stack gap="xl">
            <div>
              <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={2}>
                Total clicks
              </Text>
              <Text className={classes.hero}>{stats.total_clicks}</Text>
            </div>

            <div>
              <Text fw={600} c="#1a1a1a" mb="sm">
                Clicks by day
              </Text>
              <DailyChart data={stats.clicks_by_day} />
            </div>

            <Divider />

            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl">
              <div>
                <Text fw={600} c="#1a1a1a" mb="sm">
                  Top referrers
                </Text>
                <RankedList
                  emptyLabel="No referrer data yet."
                  items={stats.top_referrers.map((r) => ({
                    label: r.referrer ?? "Direct / none",
                    clicks: r.clicks,
                    muted: r.referrer === null,
                  }))}
                />
              </div>
              <div>
                <Text fw={600} c="#1a1a1a" mb="sm">
                  Top user agents
                </Text>
                <RankedList
                  emptyLabel="No user-agent data yet."
                  items={stats.top_user_agents.map((u) => ({
                    label: u.user_agent ?? "Unknown",
                    clicks: u.clicks,
                    muted: u.user_agent === null,
                  }))}
                />
              </div>
            </SimpleGrid>
          </Stack>
        )
      ) : null}
    </Modal>
  );
}
