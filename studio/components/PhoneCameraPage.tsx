import React, { useEffect, useRef, useState } from 'react';

/**
 * The page a phone lands on after scanning the QR code: grabs the camera and
 * streams it to the desktop over WebRTC (signaling via the dev server).
 * Deliberately dependency-light — it runs on whatever browser the phone has.
 */

interface Props {
  session: string;
}

type Status = 'starting' | 'insecure' | 'camera-denied' | 'connecting' | 'live' | 'error' | 'stopped';

export const PhoneCameraPage: React.FC<Props> = ({ session }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState<Status>('starting');
  const [detail, setDetail] = useState('');
  const [facing, setFacing] = useState<'environment' | 'user'>('environment');
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [enabled, setEnabled] = useState(true);
  const flipping = useRef(false);

  useEffect(() => {
    if (!enabled) { setStatus('stopped'); return; }
    let ws: WebSocket | null = null;
    let cancelled = false;
    let disconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const start = async () => {
      // On http:// pages phones don't even expose navigator.mediaDevices —
      // catch it here with real instructions instead of a cryptic undefined.
      if (!navigator.mediaDevices?.getUserMedia) {
        setStatus('insecure');
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: true,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;

        setStatus('connecting');
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${proto}://${location.host}/phone-signal?session=${session}&role=phone`);

        const pc = new RTCPeerConnection({
          iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
        });
        pcRef.current = pc;
        stream.getTracks().forEach((track) => pc.addTrack(track, stream));

        pc.onicecandidate = (e) => {
          if (e.candidate && ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ice', candidate: e.candidate }));
        };
        pc.onconnectionstatechange = () => {
          clearTimeout(disconnectTimer);
          if (pc.connectionState === 'disconnected') {
            disconnectTimer = setTimeout(() => {
              stream.getTracks().forEach(t => t.stop());
              pc.close(); ws?.close();
              if (!cancelled) { setStatus('error'); setDetail('Desktop disconnected. Camera and microphone stopped.'); }
            }, 5000);
          }
          if (pc.connectionState === 'connected') setStatus('live');
          if (pc.connectionState === 'failed') {
            stream.getTracks().forEach(t => t.stop());
            setStatus('error');
            setDetail('Connection failed — are both devices on the same Wi-Fi?');
          }
        };

        ws.onopen = async () => {
          try {
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'offer', sdp: pc.localDescription }));
          } catch {
            stream.getTracks().forEach(t => t.stop()); pc.close(); ws?.close();
            if (!cancelled) { setStatus('error'); setDetail('Phone pairing ended. Scan a new QR code.'); }
          }
        };
        ws.onmessage = async (event) => {
          try {
            const msg = JSON.parse(String(event.data));
            if (msg.type === 'answer') await pc.setRemoteDescription(msg.sdp);
            else if (msg.type === 'ice') await pc.addIceCandidate(msg.candidate).catch(() => {});
          } catch {
            /* ignore */
          }
        };
        ws.onerror = () => {
          stream.getTracks().forEach(t => t.stop());
          pc.close();
          setStatus('error');
          setDetail('Could not reach the desktop — keep the OMA-BS dev server running.');
        };
      } catch (e) {
        streamRef.current?.getTracks().forEach(t => t.stop());
        pcRef.current?.close(); ws?.close();
        if (cancelled) return;
        setStatus('camera-denied');
        setDetail(
          e instanceof Error && /NotAllowed/i.test(e.name)
            ? 'Camera permission was denied — allow it and reload.'
            : `Camera unavailable: ${e instanceof Error ? e.message : e}`,
        );
      }
    };

    void start();
    return () => {
      cancelled = true;
      clearTimeout(disconnectTimer);
      ws?.close();
      pcRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [session, enabled]);

  const flipCamera = async () => {
    if (flipping.current || !enabled || !streamRef.current) return;
    flipping.current = true;
    const next = facing === 'environment' ? 'user' : 'environment';
    let fresh: MediaStream | null = null;
    try {
      fresh = await navigator.mediaDevices.getUserMedia({video:{facingMode:next},audio:false});
      const old = streamRef.current;
      const sender = pcRef.current?.getSenders().find(s => s.track?.kind === 'video');
      if (!old || !sender || pcRef.current?.connectionState === 'closed') throw new Error('Camera connection ended');
      const track = fresh.getVideoTracks()[0];
      await sender.replaceTrack(track);
      if ((pcRef.current as RTCPeerConnection | null)?.connectionState === 'closed') throw new Error('Camera connection ended');
      old.getVideoTracks().forEach(t => { t.stop(); old.removeTrack(t); });
      old.addTrack(track);
      if (videoRef.current) videoRef.current.srcObject = old;
      setFacing(next);
    } catch {
      fresh?.getTracks().forEach(t => t.stop());
      setDetail('Could not switch cameras.');
    } finally { flipping.current = false; }
  };

  const STATUS_TEXT: Record<Status, string> = {
    starting: 'Starting camera…',
    insecure: '',
    'camera-denied': detail,
    connecting: 'Connecting to your desktop…',
    live: '🔴 LIVE — streaming to OMA-BS',
    error: detail,
    stopped: 'Camera and microphone stopped. Scan a new pairing QR to reconnect.',
  };

  if (status === 'insecure') {
    return (
      <div className="h-screen w-screen bg-black flex items-center justify-center p-6 text-white">
        <div className="max-w-sm space-y-5 text-center">
          <div className="text-5xl">🔒</div>
          <h1 className="text-xl font-bold">HTTPS needed for the camera</h1>
          <p className="text-sm text-zinc-400 leading-relaxed">
            Phones only allow camera access on secure pages, and this page loaded over
            plain <code className="text-zinc-200">http://</code>.
          </p>
          <div className="text-left bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-2 text-[13px] text-zinc-300">
            <p>
              <span className="font-bold text-lime-400">1.</span> On your computer, stop the dev
              server and run <code className="text-lime-300">npm run dev:phone</code>
            </p>
            <p>
              <span className="font-bold text-lime-400">2.</span> Open the{' '}
              <code className="text-lime-300">https://</code> Network URL it prints (accept the
              certificate warning)
            </p>
            <p>
              <span className="font-bold text-lime-400">3.</span> Click Phone Camera again and
              scan the new QR — accept the warning here too
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-black flex flex-col text-white overflow-hidden">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="flex-1 w-full object-cover bg-zinc-950"
      />
      <div className="shrink-0 p-4 pb-8 space-y-3 bg-black">
        <p
          className={`text-center text-sm font-bold ${
            status === 'live' ? 'text-lime-400' : status === 'error' || status === 'camera-denied' ? 'text-red-400' : 'text-zinc-300'
          }`}
        >
          {STATUS_TEXT[status]}
        </p>
        <div className="flex gap-3 justify-center">
          <button
            disabled={!enabled || status !== 'live'}
            onClick={() => void flipCamera()}
            className="px-5 py-3 bg-zinc-900 border border-zinc-700 rounded-full text-sm font-bold"
          >
            🔄 Flip Camera
          </button>
          {enabled && <button onClick={() => setEnabled(false)} className="px-5 py-3 bg-zinc-900 border border-zinc-700 rounded-full text-sm font-bold">Stop camera &amp; mic</button>}
          {(status === 'error' || status === 'camera-denied') && (
            <button
              onClick={() => location.reload()}
              className="px-5 py-3 bg-lime-700 rounded-full text-sm font-bold"
            >
              Retry
            </button>
          )}
        </div>
        <p className="text-center text-[10px] text-zinc-600">
          Keep this page open and the screen awake while streaming.
        </p>
      </div>
    </div>
  );
};
