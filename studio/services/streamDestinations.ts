import { uid } from '../utils/id';

/**
 * Multistream destinations: each has an RTMP(S) ingest URL + stream key and can
 * be toggled per-broadcast. Persisted in this browser. The relay server fans a
 * single encode out to independently buffered RTMP(S) destinations.
 */

export type PlatformId = 'twitch' | 'youtube' | 'kick' | 'x' | 'tiktok' | 'custom';

export interface StreamDestination {
  id: string;
  platform: PlatformId;
  url: string;
  key: string;
  enabled: boolean;
}

export interface PlatformPreset {
  id: PlatformId;
  label: string;
  url: string;
  keyHint: string;
}

export const PLATFORM_PRESETS: PlatformPreset[] = [
  {
    id: 'twitch',
    label: 'Twitch',
    url: '',
    keyHint: 'Creator Dashboard → Settings → Stream',
  },
  {
    id: 'youtube',
    label: 'YouTube',
    url: '',
    keyHint: 'YouTube Studio → Go Live → Stream key',
  },
  {
    id: 'kick',
    label: 'Kick',
    url: '',
    keyHint: 'Creator Dashboard → Settings → Stream Key',
  },
  {
    id: 'x',
    label: 'X (Twitter)',
    url: '',
    keyHint: 'X Media Studio → Producer → Create broadcast',
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    url: '',
    keyHint: 'Paste the server URL and stream key supplied for your account',
  },
  {
    id: 'custom',
    label: 'Custom RTMP',
    url: '',
    keyHint: 'Any RTMP(S) ingest server',
  },
];

export const presetFor = (platform: PlatformId): PlatformPreset =>
  PLATFORM_PRESETS.find((p) => p.id === platform) ?? PLATFORM_PRESETS[PLATFORM_PRESETS.length - 1];

export const createDestination = (platform: PlatformId = 'twitch'): StreamDestination => ({
  id: uid(),
  platform,
  url: presetFor(platform).url,
  key: '',
  enabled: true,
});

const STORAGE_KEY = 'chromacanvas.stream-destinations';

const validDestination = (d: unknown): d is StreamDestination => {
  if (!d || typeof d !== 'object') return false;
  const value = d as StreamDestination;
  return typeof value.id === 'string' && value.id.length <= 128
    && PLATFORM_PRESETS.some(p => p.id === value.platform)
    && typeof value.url === 'string' && value.url.length <= 900
    && typeof value.key === 'string' && value.key.length <= 900
    && typeof value.enabled === 'boolean';
};

export const loadDestinations = (): StreamDestination[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length <= 16 && parsed.every(validDestination)) return parsed;
    }
  } catch {
    /* corrupted or unavailable storage */
  }
  return [createDestination('twitch')];
};

export const saveDestinations = (destinations: StreamDestination[]): void => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(destinations));
  } catch {
    /* storage unavailable */
  }
};

export const readyDestinations = (destinations: StreamDestination[]): StreamDestination[] =>
  destinations.filter((d) => d.enabled && d.url.trim() && d.key.trim());

export const loadNativeDestinations = async (): Promise<StreamDestination[]> => {
  const response = await fetch('/oma-bs-native-streams', {
    headers: { 'X-OMA-BS-Request': 'studio' }, cache: 'no-store',
  });
  if (!response.ok) throw new Error('Save destinations in the native Stream tab and open the studio through OMA-BS.');
  const data = await response.json();
  if (data.version !== 1 || !Array.isArray(data.destinations) || data.destinations.length > 16
      || !data.destinations.every(validDestination)) {
    throw new Error('Saved destinations could not be read. Save them again in OMA-BS.');
  }
  return data.destinations;
};
