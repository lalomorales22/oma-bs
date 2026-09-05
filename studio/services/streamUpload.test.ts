import { describe, expect, it, vi } from 'vitest';
import { streamUpload } from './streamUpload';

describe('stream upload', () => {
  const socket = () => ({readyState:0, bufferedAmount:0, send:vi.fn(), close:vi.fn()});
  it('preserves the opening WebM chunk and sends chunks in order after connection', () => {
    const ws = socket(), failed = vi.fn(), upload = streamUpload(ws, failed);
    const header = new Blob(['webm header']), frame = new Blob(['frame']);
    upload.push(header); upload.push(frame);
    expect(ws.send).not.toHaveBeenCalled();
    ws.readyState = 1; upload.flush();
    expect(ws.send.mock.calls).toEqual([[header], [frame]]);
    expect(failed).not.toHaveBeenCalled();
  });
  it('bounds both connecting and socket buffers and reports failure only once', () => {
    for (const readyState of [0, 1]) {
      const ws = socket(), failed = vi.fn(), upload = streamUpload(ws, failed);
      ws.readyState = readyState; ws.bufferedAmount = 8 * 1024 * 1024;
      upload.push(new Blob(['x'])); upload.push(new Blob(['y']));
      expect(ws.send).not.toHaveBeenCalled();
      expect(ws.close).toHaveBeenCalledTimes(1);
      expect(failed).toHaveBeenCalledTimes(1);
    }
  });
  it('handles send errors and discards queued data on cleanup', () => {
    const ws = socket(), failed = vi.fn(), upload = streamUpload(ws, failed);
    ws.readyState = 1; ws.send.mockImplementation(() => { throw Error('closed'); });
    upload.push(new Blob(['x']));
    expect(failed).toHaveBeenCalledTimes(1);
    const other = socket(), pending = streamUpload(other, failed);
    pending.push(new Blob(['header'])); pending.clear(); other.readyState = 1; pending.flush();
    expect(other.send).not.toHaveBeenCalled();
  });
});
