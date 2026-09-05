import { afterEach, expect, it, vi } from 'vitest';
import { streamAudio } from './streamAudio';

afterEach(() => vi.unstubAllGlobals());
it('mixes each live input once and releases the mix without stopping owned input tracks', () => {
  const track = () => ({readyState:'live', stop:vi.fn()});
  const mic = track(), desktop = track(), ended = {...track(), readyState:'ended'}, output = track();
  class Stream {
    constructor(public tracks: unknown[]) {}
    getAudioTracks() { return this.tracks; }
    getTracks() { return this.tracks; }
  }
  const node = () => ({connect:vi.fn(function(this: unknown, target: unknown) { return target; }), disconnect:vi.fn()});
  const sources: ReturnType<typeof node>[] = [], gains: (ReturnType<typeof node> & {gain:{value:number}})[] = [];
  const destination = {...node(), stream:new Stream([output])};
  const silent = {...node(), offset:{value:1}, start:vi.fn(), stop:vi.fn()};
  const close = vi.fn(async () => {});
  class Context {
    createMediaStreamDestination() { return destination; }
    createMediaStreamSource() { const source = node(); sources.push(source); return source; }
    createGain() { const gain = {...node(), gain:{value:1}}; gains.push(gain); return gain; }
    createConstantSource() { return silent; }
    resume = async () => {};
    close = close;
  }
  vi.stubGlobal('MediaStream', Stream); vi.stubGlobal('AudioContext', Context);
  const mixed = streamAudio([new Stream([mic, desktop]), new Stream([mic, ended])] as unknown as MediaStream[]);
  expect(sources).toHaveLength(2);
  expect(gains.map(g => g.gain.value)).toEqual([0.5, 0.5]);
  gains.forEach(g => expect(g.connect).toHaveBeenCalledWith(destination));
  expect(mixed.stream.getAudioTracks()).toEqual([output]);
  expect(silent.offset.value).toBe(0);
  mixed.close(); mixed.close();
  expect(mic.stop).not.toHaveBeenCalled(); expect(desktop.stop).not.toHaveBeenCalled();
  expect(output.stop).toHaveBeenCalledTimes(1); expect(close).toHaveBeenCalledTimes(1);
});
