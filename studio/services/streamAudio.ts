/** One mixed track for MediaRecorder; input tracks remain owned by their sources. */
export function streamAudio(streams: MediaStream[]) {
  const context = new AudioContext({ sampleRate: 48000 });
  const destination = context.createMediaStreamDestination();
  const tracks = [...new Set(streams.flatMap(s => s.getAudioTracks()))].filter(t => t.readyState === 'live');
  const nodes: AudioNode[] = [];
  const silent = context.createConstantSource();
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    try { silent.stop(); } catch { /* Setup may fail before start. */ }
    silent.disconnect();
    nodes.forEach(n => n.disconnect());
    destination.stream.getTracks().forEach(t => t.stop());
    void context.close().catch(() => {});
  };
  try {
  for (const track of tracks) {
    const source = context.createMediaStreamSource(new MediaStream([track]));
    const gain = context.createGain();
    gain.gain.value = 1 / Math.max(1, tracks.length);
    source.connect(gain).connect(destination);
    nodes.push(source, gain);
  }
  // An explicit silent source also gives silent scenes a continuous audio track.
  silent.offset.value = 0; silent.connect(destination); silent.start();
  void context.resume().catch(() => {});
  return { stream: destination.stream, close };
  } catch (error) { close(); throw error; }
}
