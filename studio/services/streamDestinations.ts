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
    url: 'rtmp://live.twitch.tv/app',
    keyHint: 'Creator Dashboard → Settings → Stream',
  },
  {
    id: 'youtube',
    label: 'YouTube',
    url: 'rtmp://a.rtmp.youtube.com/live2',
    keyHint: 'YouTube Studio → Go Live → Stream key',
  },
  {
    id: 'kick',
    label: 'Kick',
    url: 'rtmps://fa723fc1b171.global-contribute.live-video.net/app',
    keyHint: 'Creator Dashboard → Settings → Stream Key',
  },
  {
    id: 'x',
    label: 'X (Twitter)',
    url: 'rtmp://va.pscp.tv:80/x',
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

export const loadDestinations = (): StreamDestination[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as StreamDestination[];
      if (Array.isArray(parsed) && parsed.length) return parsed;
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
      || !data.destinations.every((d: StreamDestination) => d && typeof d.id === 'string'
        && PLATFORM_PRESETS.some(p => p.id === d.platform) && typeof d.url === 'string'
        && typeof d.key === 'string' && typeof d.enabled === 'boolean')) {
    throw new Error('Saved destinations could not be read. Save them again in OMA-BS.');
  }
  return data.destinations;
};
