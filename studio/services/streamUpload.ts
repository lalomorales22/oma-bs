/** Preserve the WebM header while connecting and bound browser-side upload RAM. */
export function streamUpload(socket: Pick<WebSocket, 'readyState' | 'bufferedAmount' | 'send' | 'close'>, failed: () => void) {
  const limit = 8 * 1024 * 1024;
  const pending: Blob[] = [];
  let bytes = 0, stopped = false;
  const stop = () => {
    if (stopped) return;
    stopped = true; pending.length = 0; bytes = 0;
    socket.close(); failed();
  };
  const flush = () => {
    if (stopped || socket.readyState !== 1) return;
    try {
      while (pending.length) {
        const chunk = pending[0];
        if (socket.bufferedAmount + chunk.size > limit) { stop(); return; }
        socket.send(chunk); pending.shift(); bytes -= chunk.size;
      }
    } catch { stop(); }
  };
  return {
    flush,
    push(chunk: Blob) {
      if (stopped) return;
      if (socket.readyState > 1) { stop(); return; }
      if (bytes + socket.bufferedAmount + chunk.size > limit) { stop(); return; }
      pending.push(chunk); bytes += chunk.size; flush();
    },
    clear() { stopped = true; pending.length = 0; bytes = 0; },
  };
}
