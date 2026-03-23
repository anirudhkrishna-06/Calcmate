import React, { useEffect, useRef, useState } from 'react';
import ProblemPanel from '../components/cognitive/ProblemPanel';
import CognitiveIDE from '../components/cognitive/CognitiveIDE';
import TimelinePanel from '../components/cognitive/TimelinePanel';

const API_BASE_URL = 'http://127.0.0.1:8000';
const WS_BASE_URL = 'ws://127.0.0.1:8000';
const CHUNK_DURATION_MS = 4000;
const ANALYSER_FFT_SIZE = 1024;
const MIN_VOICE_THRESHOLD = 0.012;
const NOISE_MULTIPLIER = 2.4;

function formatTimer(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function createIdleWaveform() {
    return Array.from({ length: 20 }, () => 10);
}

function normaliseCategory(category) {
    if (["understanding", "parameter", "strategy", "delay", "deviation", "execution", "intervention", "signal", "system"].includes(category)) {
        return category;
    }
    return 'signal';
}

function timelineItemFromSocket(data) {
    return {
        id: data.event_id || `evt-${data.timestamp || data.timeLabel || Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        type: normaliseCategory(data.category || data.type),
        title: data.message || 'Timeline update',
        detail: data.detail || 'The cognitive runtime recorded a new observation.',
        timeLabel: formatTimer(Math.round(data.timestamp || data.at_seconds || 0)),
    };
}

function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const result = reader.result;
            if (typeof result !== 'string') {
                reject(new Error('Unable to encode audio chunk.'));
                return;
            }
            const encoded = result.includes(',') ? result.split(',')[1] : result;
            resolve(encoded);
        };
        reader.onerror = () => reject(reader.error || new Error('Unable to encode audio chunk.'));
        reader.readAsDataURL(blob);
    });
}

function selectRecorderMimeType() {
    const candidates = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
    ];

    if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
        return '';
    }

    const supported = candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
    return supported || '';
}

export default function ThinkingSessionPage() {
    const [uiState, setUiState] = useState('pre_session');
    const [timer, setTimer] = useState(0);
    const [micStatus, setMicStatus] = useState('idle');
    const [statusText, setStatusText] = useState('Idle...');
    const [sessionPhase, setSessionPhase] = useState('understanding');
    const [lifecycleState, setLifecycleState] = useState('initializing');
    const [waveform, setWaveform] = useState(() => createIdleWaveform());
    const [problemText, setProblemText] = useState('The problem will appear here when the session starts.');
    const [timelineEvents, setTimelineEvents] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [runtimeNote, setRuntimeNote] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isIntervening, setIsIntervening] = useState(false);

    const wsRef = useRef(null);
    const heartbeatRef = useRef(null);
    const timerRef = useRef(0);
    const sessionIdRef = useRef(null);
    const sessionStartedAtRef = useRef(null);
    const chunkIndexRef = useRef(0);
    const mediaRecorderRef = useRef(null);
    const mediaStreamRef = useRef(null);
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const animationFrameRef = useRef(null);
    const featureStatsRef = useRef(null);
    const interventionTimeoutRef = useRef(null);
    const recordingTimerRef = useRef(null);
    const recorderChunksRef = useRef([]);
    const streamingEnabledRef = useRef(false);
    const desiredMicStateRef = useRef('idle');
    const recorderMimeTypeRef = useRef('');

    useEffect(() => {
        timerRef.current = timer;
    }, [timer]);

    useEffect(() => {
        sessionIdRef.current = sessionId;
    }, [sessionId]);

    useEffect(() => {
        desiredMicStateRef.current = micStatus;
    }, [micStatus]);

    useEffect(() => {
        if (isIntervening) {
            setStatusText('Intervention...');
            return;
        }
        if (isAnalyzing) {
            setStatusText('Analyzing...');
            return;
        }
        if (uiState === 'completed' || uiState !== 'active') {
            setStatusText('Idle...');
            return;
        }
        setStatusText(micStatus === 'recording' ? 'Listening...' : 'Idle...');
    }, [isAnalyzing, isIntervening, micStatus, uiState]);

    useEffect(() => {
        if (uiState !== 'active') return undefined;
        const interval = window.setInterval(() => {
            setTimer((current) => current + 1);
        }, 1000);
        return () => window.clearInterval(interval);
    }, [uiState]);

    useEffect(() => () => {
        cleanupAudio();
        cleanupSocket();
        if (interventionTimeoutRef.current) {
            window.clearTimeout(interventionTimeoutRef.current);
        }
    }, []);

    function appendTimelineEvent(nextEvent) {
        setTimelineEvents((current) => {
            if (current.some((event) => event.id === nextEvent.id)) {
                return current;
            }
            return [...current, nextEvent];
        });
    }

    function resetFeatureStats() {
        featureStatsRef.current = {
            frameCount: 0,
            voicedFrames: 0,
            energyTotal: 0,
            peakEnergy: 0,
            currentSilenceSeconds: 0,
            maxSilenceSeconds: 0,
            leadingSilenceSeconds: 0,
            trailingSilenceSeconds: 0,
            startedSpeaking: false,
            noiseFloor: MIN_VOICE_THRESHOLD / 2,
            speechThreshold: MIN_VOICE_THRESHOLD,
            lastFrameAt: performance.now(),
        };
    }

    function consumeFeatureStats() {
        const stats = featureStatsRef.current;
        if (!stats || stats.frameCount === 0) {
            resetFeatureStats();
            return {
                rms_energy: 0,
                speech_ratio: 0,
                leading_silence: 0,
                trailing_silence: 0,
                noise_floor: 0,
                voiced_frames: 0,
                extra: {
                    peak_energy: 0,
                    speech_threshold: 0,
                    silence_ratio: 1,
                },
            };
        }

        const voicedRatio = stats.voicedFrames / stats.frameCount;
        const rmsEnergy = stats.energyTotal / stats.frameCount;
        const payload = {
            rms_energy: Number(rmsEnergy.toFixed(4)),
            speech_ratio: Number(voicedRatio.toFixed(3)),
            leading_silence: Number(stats.leadingSilenceSeconds.toFixed(2)),
            trailing_silence: Number(stats.trailingSilenceSeconds.toFixed(2)),
            noise_floor: Number(stats.noiseFloor.toFixed(4)),
            voiced_frames: Number(voicedRatio.toFixed(3)),
            extra: {
                peak_energy: Number(stats.peakEnergy.toFixed(4)),
                speech_threshold: Number(stats.speechThreshold.toFixed(4)),
                silence_ratio: Number((1 - voicedRatio).toFixed(3)),
                max_silence_seconds: Number(stats.maxSilenceSeconds.toFixed(2)),
            },
        };
        resetFeatureStats();
        return payload;
    }

    function cleanupSocket() {
        if (heartbeatRef.current) {
            window.clearInterval(heartbeatRef.current);
            heartbeatRef.current = null;
        }
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    }

    function cleanupAudio() {
        streamingEnabledRef.current = false;
        desiredMicStateRef.current = 'idle';
        recorderMimeTypeRef.current = '';
        recorderChunksRef.current = [];
        if (recordingTimerRef.current) {
            window.clearTimeout(recordingTimerRef.current);
            recordingTimerRef.current = null;
        }
        if (animationFrameRef.current) {
            window.cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }
        if (mediaRecorderRef.current) {
            const recorder = mediaRecorderRef.current;
            if (recorder.state !== 'inactive') {
                recorder.stop();
            }
            mediaRecorderRef.current = null;
        }
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((track) => track.stop());
            mediaStreamRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
        analyserRef.current = null;
        setWaveform(createIdleWaveform());
    }

    function connectSocket(nextSessionId) {
        cleanupSocket();
        const socket = new WebSocket(`${WS_BASE_URL}/ws/session/${nextSessionId}`);
        socket.onmessage = (message) => {
            const payload = JSON.parse(message.data);
            const { type, data } = payload;
            if (type === 'session_snapshot') {
                setLifecycleState(data.lifecycle_state || 'active');
                setSessionPhase(data.phase || 'understanding');
                setTimelineEvents((data.timeline || []).map((item) => timelineItemFromSocket({
                    event_id: item.event_id,
                    category: item.category,
                    message: item.message,
                    detail: item.payload?.detail,
                    timestamp: item.at_seconds,
                })));
                return;
            }
            if (type === 'phase_change') {
                setSessionPhase(data.phase || 'understanding');
                setLifecycleState(data.lifecycle_state || 'active');
                if (data.lifecycle_state === 'closed') {
                    setUiState('completed');
                    setMicStatus('idle');
                }
                return;
            }
            if (type === 'status_update') {
                if (!isAnalyzing && !isIntervening) {
                    setStatusText(data.status || 'Idle...');
                }
                return;
            }
            if (type === 'timeline_event') {
                appendTimelineEvent(timelineItemFromSocket(data));
                return;
            }
            if (type === 'intervention') {
                setIsIntervening(true);
                appendTimelineEvent(
                    timelineItemFromSocket({
                        event_id: `intervention-${data.timestamp}`,
                        category: 'intervention',
                        message: 'Intervention triggered',
                        detail: data.message,
                        timestamp: data.timestamp,
                    }),
                );
                if (interventionTimeoutRef.current) {
                    window.clearTimeout(interventionTimeoutRef.current);
                }
                interventionTimeoutRef.current = window.setTimeout(() => {
                    setIsIntervening(false);
                }, 1400);
            }
        };
        socket.onopen = () => {
            heartbeatRef.current = window.setInterval(() => {
                if (socket.readyState === WebSocket.OPEN) {
                    socket.send('ping');
                }
            }, 20000);
        };
        socket.onclose = () => {
            if (heartbeatRef.current) {
                window.clearInterval(heartbeatRef.current);
                heartbeatRef.current = null;
            }
        };
        wsRef.current = socket;
    }

    async function streamChunk(blob) {
        if (!streamingEnabledRef.current || !sessionIdRef.current || !sessionStartedAtRef.current) return;
        const chunkIndex = chunkIndexRef.current + 1;
        chunkIndexRef.current = chunkIndex;
        const endTime = (performance.now() - sessionStartedAtRef.current) / 1000;
        const startTime = Math.max(0, endTime - CHUNK_DURATION_MS / 1000);
        const audioBlob = await blobToBase64(blob);
        const frontendFeatures = consumeFeatureStats();
        frontendFeatures.extra = {
            ...frontendFeatures.extra,
            mime_type: blob.type || recorderMimeTypeRef.current || 'audio/webm',
            chunk_size_bytes: blob.size,
            chunk_duration_ms: CHUNK_DURATION_MS,
        };

        setIsAnalyzing(true);
        try {
            await fetch(`${API_BASE_URL}/stream_audio_chunk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionIdRef.current,
                    chunk_id: `chunk_${chunkIndex}`,
                    audio_blob: audioBlob,
                    start_time: Number(startTime.toFixed(2)),
                    end_time: Number(endTime.toFixed(2)),
                    frontend_features: frontendFeatures,
                    transcript_hint: null,
                }),
            });
        } finally {
            setIsAnalyzing(false);
        }
    }

    function scheduleRecorderStop() {
        if (recordingTimerRef.current) {
            window.clearTimeout(recordingTimerRef.current);
        }
        recordingTimerRef.current = window.setTimeout(() => {
            const recorder = mediaRecorderRef.current;
            if (recorder && recorder.state === 'recording') {
                recorder.stop();
            }
        }, CHUNK_DURATION_MS);
    }

    function startRecorderCycle(stream) {
        if (!streamingEnabledRef.current || desiredMicStateRef.current !== 'recording') {
            return;
        }

        const mimeType = selectRecorderMimeType();
        const recorder = mimeType
            ? new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 128000 })
            : new MediaRecorder(stream, { audioBitsPerSecond: 128000 });

        recorderMimeTypeRef.current = recorder.mimeType || mimeType;
        recorderChunksRef.current = [];
        recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                recorderChunksRef.current.push(event.data);
            }
        };
        recorder.onstop = async () => {
            if (recordingTimerRef.current) {
                window.clearTimeout(recordingTimerRef.current);
                recordingTimerRef.current = null;
            }
            const chunks = recorderChunksRef.current;
            recorderChunksRef.current = [];
            const blob = chunks.length > 0 ? new Blob(chunks, { type: recorder.mimeType || recorderMimeTypeRef.current || 'audio/webm' }) : null;
            if (blob && blob.size > 0 && streamingEnabledRef.current) {
                await streamChunk(blob);
            }
            if (streamingEnabledRef.current && desiredMicStateRef.current === 'recording' && mediaStreamRef.current) {
                resetFeatureStats();
                startRecorderCycle(mediaStreamRef.current);
            }
        };
        recorder.start();
        mediaRecorderRef.current = recorder;
        scheduleRecorderStop();
    }

    async function initializeAudioRuntime() {
        if (!navigator.mediaDevices?.getUserMedia) {
            throw new Error('Microphone access is not supported in this browser.');
        }

        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: { ideal: 1 },
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            },
        });
        const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
        const audioContext = new AudioContextCtor();
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = ANALYSER_FFT_SIZE;
        analyser.smoothingTimeConstant = 0.72;
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        mediaStreamRef.current = stream;
        audioContextRef.current = audioContext;
        analyserRef.current = analyser;
        resetFeatureStats();
        streamingEnabledRef.current = true;
        desiredMicStateRef.current = 'recording';
        startRecorderCycle(stream);

        const waveformBuffer = new Uint8Array(analyser.frequencyBinCount);
        const timeDomainBuffer = new Uint8Array(analyser.fftSize);

        const draw = () => {
            const activeAnalyser = analyserRef.current;
            if (!activeAnalyser || !streamingEnabledRef.current) return;
            activeAnalyser.getByteFrequencyData(waveformBuffer);
            activeAnalyser.getByteTimeDomainData(timeDomainBuffer);

            const bars = Array.from({ length: 20 }, (_, index) => {
                const start = Math.floor((index * waveformBuffer.length) / 20);
                const end = Math.floor(((index + 1) * waveformBuffer.length) / 20);
                const slice = waveformBuffer.slice(start, end);
                const average = slice.length === 0 ? 0 : slice.reduce((sum, value) => sum + value, 0) / slice.length;
                return Math.max(8, Math.round((average / 255) * 100));
            });
            setWaveform(bars);

            let rms = 0;
            for (let index = 0; index < timeDomainBuffer.length; index += 1) {
                const centered = (timeDomainBuffer[index] - 128) / 128;
                rms += centered * centered;
            }
            rms = Math.sqrt(rms / timeDomainBuffer.length);

            const now = performance.now();
            const stats = featureStatsRef.current;
            if (stats) {
                const deltaSeconds = Math.min((now - stats.lastFrameAt) / 1000, 0.08);
                stats.lastFrameAt = now;
                stats.frameCount += 1;
                stats.energyTotal += rms;
                stats.peakEnergy = Math.max(stats.peakEnergy, rms);

                const adaptiveNoiseFloor = Math.max(MIN_VOICE_THRESHOLD / 2, stats.noiseFloor);
                const speechThreshold = Math.max(MIN_VOICE_THRESHOLD, adaptiveNoiseFloor * NOISE_MULTIPLIER);
                stats.speechThreshold = speechThreshold;

                const isVoiced = rms >= speechThreshold;
                if (isVoiced) {
                    stats.voicedFrames += 1;
                    stats.startedSpeaking = true;
                    stats.currentSilenceSeconds = 0;
                    stats.trailingSilenceSeconds = 0;
                } else {
                    stats.noiseFloor = stats.noiseFloor * 0.92 + rms * 0.08;
                    stats.currentSilenceSeconds += deltaSeconds;
                    stats.maxSilenceSeconds = Math.max(stats.maxSilenceSeconds, stats.currentSilenceSeconds);
                    if (!stats.startedSpeaking) {
                        stats.leadingSilenceSeconds += deltaSeconds;
                    } else {
                        stats.trailingSilenceSeconds = stats.currentSilenceSeconds;
                    }
                }
            }

            animationFrameRef.current = window.requestAnimationFrame(draw);
        };

        animationFrameRef.current = window.requestAnimationFrame(draw);
    }

    async function handleStartThinking() {
        setRuntimeNote('');
        setUiState('loading');
        setTimer(0);
        setTimelineEvents([]);
        setMicStatus('idle');
        setLifecycleState('initializing');
        setSessionPhase('understanding');
        setSessionId(null);
        setIsAnalyzing(false);
        setIsIntervening(false);
        cleanupAudio();
        cleanupSocket();

        try {
            const response = await fetch(`${API_BASE_URL}/start_session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            if (!response.ok) {
                throw new Error('Unable to start the session.');
            }
            const session = await response.json();
            setSessionId(session.session_id);
            sessionIdRef.current = session.session_id;
            setProblemText(session.problem_payload?.raw_text || 'Problem unavailable.');
            setSessionPhase(session.initial_state?.phase || 'understanding');
            setLifecycleState(session.initial_state?.lifecycle_state || 'active');
            connectSocket(session.session_id);
            sessionStartedAtRef.current = performance.now();
            chunkIndexRef.current = 0;
            setUiState('active');
            await initializeAudioRuntime();
            setMicStatus('recording');
        } catch (error) {
            cleanupAudio();
            cleanupSocket();
            setUiState('pre_session');
            setRuntimeNote(error instanceof Error ? error.message : 'Unable to initialize the runtime.');
        }
    }

    function handleToggleMic() {
        if (uiState !== 'active' || !mediaStreamRef.current) return;
        const recorder = mediaRecorderRef.current;
        if (micStatus === 'recording') {
            desiredMicStateRef.current = 'paused';
            setMicStatus('paused');
            if (recordingTimerRef.current) {
                window.clearTimeout(recordingTimerRef.current);
                recordingTimerRef.current = null;
            }
            if (recorder && recorder.state === 'recording') {
                recorder.stop();
            }
            return;
        }
        if (micStatus === 'paused') {
            desiredMicStateRef.current = 'recording';
            resetFeatureStats();
            setMicStatus('recording');
            startRecorderCycle(mediaStreamRef.current);
        }
    }

    async function handleEndSession() {
        if (!sessionIdRef.current) return;
        try {
            streamingEnabledRef.current = false;
            desiredMicStateRef.current = 'idle';
            if (recordingTimerRef.current) {
                window.clearTimeout(recordingTimerRef.current);
                recordingTimerRef.current = null;
            }
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
                mediaRecorderRef.current.stop();
            }
            cleanupAudio();
            setMicStatus('idle');
            await fetch(`${API_BASE_URL}/end_session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionIdRef.current,
                    final_timestamps: {
                        start_time: 0,
                        end_time: timerRef.current,
                    },
                }),
            });
            setLifecycleState('closed');
            setUiState('completed');
        } catch {
            setRuntimeNote('Unable to close the session cleanly.');
        } finally {
            cleanupSocket();
        }
    }

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(251,191,36,0.16),transparent_22%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_42%,#edf3f7_100%)] px-3 py-3 text-slate-950 sm:px-4 lg:px-5">
            <div className="mx-auto grid max-w-[1720px] gap-3 xl:h-[calc(100vh-1.5rem)] xl:grid-cols-[1.04fr_1.28fr_0.98fr]">
                <ProblemPanel problemText={problemText} />
                <CognitiveIDE
                    uiState={uiState}
                    timer={timer}
                    micStatus={micStatus}
                    statusText={statusText}
                    waveform={waveform}
                    sessionPhase={sessionPhase}
                    lifecycleState={lifecycleState}
                    runtimeNote={runtimeNote}
                    onStart={handleStartThinking}
                    onToggleMic={handleToggleMic}
                    onEndSession={handleEndSession}
                />
                <TimelinePanel events={timelineEvents} />
            </div>
        </div>
    );
}
