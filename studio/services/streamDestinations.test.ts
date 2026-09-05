import { afterEach, expect, it, vi } from 'vitest';
import { createDestination, loadDestinations } from './streamDestinations';
afterEach(() => vi.unstubAllGlobals());
it('keeps an intentionally empty list and rejects damaged stored profiles', () => {
  vi.stubGlobal('localStorage', {getItem:() => '[]'});
  expect(loadDestinations()).toEqual([]);
  for (const raw of ['null', '[{"enabled":true,"url":42}]', '{bad json']) {
    vi.stubGlobal('localStorage', {getItem:() => raw});
    const restored = loadDestinations();
    expect(restored).toHaveLength(1);
    expect(restored[0].url).toBe(''); expect(restored[0].key).toBe('');
  }
});
it('requires account-supplied ingest addresses for all new providers', () => {
  for (const provider of ['twitch','youtube','kick','x','tiktok','custom'] as const) {
    expect(createDestination(provider)).toMatchObject({platform:provider,url:'',key:''});
  }
});
