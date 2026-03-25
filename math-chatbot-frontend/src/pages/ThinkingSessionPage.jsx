import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import ProblemPanel from '../components/cognitive/ProblemPanel';
import CognitiveIDE from '../components/cognitive/CognitiveIDE';
import TimelinePanel from '../components/cognitive/TimelinePanel';
import { COGNITIVE_API_BASE as API_BASE_URL, COGNITIVE_WS_BASE as WS_BASE_URL } from '../config/api';
const CHUNK_DURATION_MS = 5000;
const ANALYSER_FFT_SIZE = 2048;
const MIN_VOICE_THRESHOLD = 0.01;
const NOISE_MULTIPLIER = 2.05;
const UPLOAD_GRACE_SECONDS = 10;

function createIdleWaveform() {
    return Array.from({ length: 20 }, () => 10);
}

function formatTimer(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function labelFromProbability(probability) {
    if (probability >= 0.45) return 'high';
    if (probability >= 0.2) return 'moderate';
    return 'low';
}

function normaliseCategory(category) {
    if (['understanding', 'parameter', 'strategy', 'delay', 'deviation', 'execution', 'intervention', 'signal', 'system'].includes(category)) {
        return category;
    }
    return 'signal';
}

function normaliseWrongStepAnalysis(analysis, questionNumber = null) {
    if (!analysis || typeof analysis !== 'object') {
        return {
            available: false,
            summary: '',
            thinking_mistakes: [],
            solving_mistakes: [],
            strengths: [],
            next_focus: [],
        };
    }

    const mapItems = (items, stage) => (Array.isArray(items) ? items : []).map((item, index) => ({
        ...item,
        finding_id: item?.finding_id || `ws-${stage}-${questionNumber || 'x'}-${index + 1}`,
        question_number: item?.question_number || questionNumber,
        stage: item?.stage || stage,
    }));

    const thinking = mapItems(analysis.thinking_mistakes, 'thinking');
    const solving = mapItems(analysis.solving_mistakes, 'solving');

    return {
        available: Boolean(analysis.available || thinking.length || solving.length),
        generated_by: analysis.generated_by || 'aggregate',
        summary: analysis.summary || '',
        thinking_mistakes: thinking,
        solving_mistakes: solving,
        strengths: Array.isArray(analysis.strengths) ? analysis.strengths.filter(Boolean) : [],
        next_focus: Array.isArray(analysis.next_focus) ? analysis.next_focus.filter(Boolean) : [],
    };
}

function buildAggregateWrongStepAnalysis(rounds) {
    const thinking = [];
    const solving = [];
    const strengths = [];
    const nextFocus = [];

    rounds.forEach((round, index) => {
        const analysis = normaliseWrongStepAnalysis(round?.report?.wrong_step_analysis, round?.questionNumber || index + 1);
        thinking.push(...analysis.thinking_mistakes);
        solving.push(...analysis.solving_mistakes);
        strengths.push(...analysis.strengths);
        nextFocus.push(...analysis.next_focus);
    });

    const totalItems = thinking.length + solving.length;
    return {
        available: totalItems > 0,
        generated_by: 'aggregate',
        summary: totalItems > 0
            ? `${totalItems} wrong-step pattern${totalItems === 1 ? '' : 's'} were detected across this session.`
            : 'No wrong-step pattern was available across the completed reports.',
        thinking_mistakes: thinking,
        solving_mistakes: solving,
        strengths: [...new Set(strengths)],
        next_focus: [...new Set(nextFocus)],
    };
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

function buildAggregateReport(rounds, reports) {
    const safeReports = reports.filter(Boolean);
    const totalThinkingTime = rounds.reduce((sum, round) => sum + (round.thinkingSeconds || 0), 0);
    const totalSolvingTime = rounds.reduce((sum, round) => sum + (round.solvingSeconds || 0), 0);
    const correctAnswers = rounds.filter((round) => round.answerResult?.correct).length;
    const attemptedAnswers = rounds.filter((round) => round.answerResult).length;

    const timelineMetrics = safeReports.reduce((totals, report) => {
        const metrics = report.timeline_metrics || {};
        return {
            understanding_time_seconds: totals.understanding_time_seconds + (metrics.understanding_time_seconds || 0),
            strategy_delay_seconds: totals.strategy_delay_seconds + (metrics.strategy_delay_seconds || 0),
            deviation_time_seconds: totals.deviation_time_seconds + (metrics.deviation_time_seconds || 0),
            execution_time_seconds: totals.execution_time_seconds + (metrics.execution_time_seconds || 0),
            verification_time_seconds: totals.verification_time_seconds + (metrics.verification_time_seconds || 0),
            decision_efficiency_score: totals.decision_efficiency_score + (metrics.decision_efficiency_score || 0),
        };
    }, {
        understanding_time_seconds: 0,
        strategy_delay_seconds: 0,
        deviation_time_seconds: 0,
        execution_time_seconds: 0,
        verification_time_seconds: 0,
        decision_efficiency_score: 0,
    });

    const avgEfficiency = safeReports.length > 0
        ? Number((timelineMetrics.decision_efficiency_score / safeReports.length).toFixed(2))
        : 0;

    const validationState = safeReports.reduce((acc, report) => {
        const vs = report.validation_state || {};
        acc.path_alignment_score += vs.path_alignment_score || 0;
        acc.progress_ratio += vs.progress_ratio || 0;
        acc.deviation_score += vs.deviation_score || 0;
        acc.inefficiency_score += vs.inefficiency_score || 0;
        acc.oscillation_index += vs.oscillation_index || 0;
        acc.on_graph_nodes += vs.on_graph_nodes || 0;
        acc.off_graph_nodes += vs.off_graph_nodes || 0;
        return acc;
    }, {
        path_alignment_score: 0,
        progress_ratio: 0,
        deviation_score: 0,
        inefficiency_score: 0,
        oscillation_index: 0,
        on_graph_nodes: 0,
        off_graph_nodes: 0,
    });

    if (safeReports.length > 0) {
        validationState.path_alignment_score = Number((validationState.path_alignment_score / safeReports.length).toFixed(3));
        validationState.progress_ratio = Number((validationState.progress_ratio / safeReports.length).toFixed(3));
        validationState.deviation_score = Number((validationState.deviation_score / safeReports.length).toFixed(3));
        validationState.inefficiency_score = Number((validationState.inefficiency_score / safeReports.length).toFixed(3));
        validationState.oscillation_index = Number((validationState.oscillation_index / safeReports.length).toFixed(3));
    }

    const predictiveReports = safeReports
        .map((report) => report.predictive_analytics)
        .filter((item) => item?.available);
    const predictiveAnalytics = predictiveReports.length > 0
        ? (() => {
            const totals = predictiveReports.reduce((acc, item) => {
                acc.predicted += item.predicted_total_time_seconds || 0;
                acc.observed += item.observed_total_time_seconds || 0;
                acc.confusion += item.confusion_probability || 0;
                if ((item.confusion_probability || 0) >= 0.45) {
                    acc.highRisk += 1;
                }
                return acc;
            }, {
                predicted: 0,
                observed: 0,
                confusion: 0,
                highRisk: 0,
            });

            const averageConfusion = Number((totals.confusion / predictiveReports.length).toFixed(4));
            return {
                enabled: true,
                available: true,
                model_status: 'ready',
                predicted_total_time_seconds: Number(totals.predicted.toFixed(2)),
                observed_total_time_seconds: Number(totals.observed.toFixed(2)),
                time_delta_seconds: Number((totals.observed - totals.predicted).toFixed(2)),
                confusion_probability: averageConfusion,
                confusion_risk_level: labelFromProbability(averageConfusion),
                question_count: predictiveReports.length,
                high_risk_questions: totals.highRisk,
                summary: `Across ${predictiveReports.length} report${predictiveReports.length === 1 ? '' : 's'}, the model expected ${formatTimer(Math.round(totals.predicted))} and observed ${formatTimer(Math.round(totals.observed))}. Average confusion risk was ${(averageConfusion * 100).toFixed(1)}%.`,
            };
        })()
        : {
            enabled: true,
            available: false,
            model_status: 'unavailable',
            summary: 'Predictive analytics was not available for the completed questions.',
        };

    const aggregateWrongStepAnalysis = buildAggregateWrongStepAnalysis(rounds);
    const roundsWithAnalysis = rounds.map((round, index) => ({
        ...round,
        report: round?.report
            ? {
                ...round.report,
                wrong_step_analysis: normaliseWrongStepAnalysis(round.report.wrong_step_analysis, round.questionNumber || index + 1),
            }
            : round?.report || null,
    }));

    return {
        session_type: 'aggregate',
        generated_at: new Date().toISOString(),
        total_questions: rounds.length,
        completed_questions: rounds.length,
        correct_answers: correctAnswers,
        attempted_answers: attemptedAnswers,
        total_thinking_time: totalThinkingTime,
        total_solving_time: totalSolvingTime,
        total_session_time: totalThinkingTime + totalSolvingTime,
        total_chunks: safeReports.reduce((sum, report) => sum + (report.total_chunks || 0), 0),
        total_interventions: safeReports.reduce((sum, report) => sum + (report.total_interventions || 0), 0),
        timeline_metrics: {
            ...timelineMetrics,
            decision_efficiency_score: avgEfficiency,
        },
        validation_state: validationState,
        thinking_graph: safeReports
            .map((report, index) => report.thinking_graph ? `Q${index + 1}: ${report.thinking_graph}` : '')
            .filter(Boolean)
            .join(' | '),
        insight: `${correctAnswers}/${rounds.length} questions were correct. Total thinking time was ${formatTimer(totalThinkingTime)} and total solving time was ${formatTimer(totalSolvingTime)}.`,
        improvement_rule: correctAnswers === rounds.length
            ? 'Keep the same rhythm: think first, solve silently, then verify before uploading.'
            : 'Keep separating thinking from solving, and spend a few extra seconds checking the final numeric answer before uploading.',
        detailed_report: roundsWithAnalysis
            .filter((round) => round?.report)
            .map((round, index) => ({
                question_number: round?.questionNumber || index + 1,
                insight: round?.report?.insight || '',
                improvement_rule: round?.report?.improvement_rule || '',
                detailed_analysis: round?.report?.detailed_analysis || '',
                time_analysis: round?.report?.time_analysis || null,
                predictive_analytics: round?.report?.predictive_analytics || null,
                wrong_step_analysis: round?.report?.wrong_step_analysis || null,
            })),
        wrong_step_analysis: aggregateWrongStepAnalysis,
        predictive_analytics: predictiveAnalytics,
        rounds: roundsWithAnalysis,
    };
}

export default function ThinkingSessionPage() {
    const [uiStage, setUiStage] = useState('pre_session');
    const [launchStage, setLaunchStage] = useState('countdown');
    const [countdownValue, setCountdownValue] = useState(3);
    const [thinkingTimer, setThinkingTimer] = useState(0);
    const [solvingTimer, setSolvingTimer] = useState(0);
    const [statusText, setStatusText] = useState('Idle...');
    const [sessionPhase, setSessionPhase] = useState('understanding');
    const [lifecycleState, setLifecycleState] = useState('initializing');
    const [waveform, setWaveform] = useState(() => createIdleWaveform());
    const [problemText, setProblemText] = useState('The problem will appear here when the session starts.');
    const [timelineEvents, setTimelineEvents] = useState([]);
    const [runtimeNote, setRuntimeNote] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isIntervening, setIsIntervening] = useState(false);
    const [interventionMessage, setInterventionMessage] = useState(null);
    const [answerResult, setAnswerResult] = useState(null);
    const [isValidating, setIsValidating] = useState(false);
    const [isEndingSession, setIsEndingSession] = useState(false);
    const [questionNumber, setQuestionNumber] = useState(1);
    const [completedRounds, setCompletedRounds] = useState([]);
    const [validationState, setValidationState] = useState(null);
    const [uploadGraceUsed, setUploadGraceUsed] = useState(0);

    const navigate = useNavigate();
    const location = useLocation();

    const wsRef = useRef(null);
    const heartbeatRef = useRef(null);
    const thinkingTimerRef = useRef(0);
    const solvingTimerRef = useRef(0);
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
    const questionFinalizedRef = useRef(false);
    const uiStageRef = useRef('pre_session');
    const uploadStartedAtRef = useRef(null);

    const launchConfig = useMemo(() => {
        const stateConfig = location.state && typeof location.state === 'object' ? location.state : null;
        if (stateConfig?.topic) {
            return stateConfig;
        }

        try {
            const storedConfig = JSON.parse(sessionStorage.getItem('mathmend_thinking_launch') || 'null');
            return storedConfig?.topic ? storedConfig : null;
        } catch {
            return null;
        }
    }, [location.state]);

    const selectedTopic = launchConfig?.topic || 'Algebra';
    const sessionMode = launchConfig?.mode === 'pro' ? 'pro' : 'normal';

    useEffect(() => {
        thinkingTimerRef.current = thinkingTimer;
    }, [thinkingTimer]);

    useEffect(() => {
        solvingTimerRef.current = solvingTimer;
    }, [solvingTimer]);

    useEffect(() => {
        uiStageRef.current = uiStage;
    }, [uiStage]);

    useEffect(() => {
        if (isIntervening) {
            setStatusText('Intervention...');
            return;
        }
        if (isAnalyzing) {
            setStatusText('Checking thinking...');
            return;
        }
        if (uiStage === 'thinking') {
            setStatusText('Thinking in progress');
            return;
        }
        if (uiStage === 'solving') {
            setStatusText('Solving silently');
            return;
        }
        if (uiStage === 'question_done') {
            setStatusText('Question complete');
            return;
        }
        setStatusText('Idle...');
    }, [isAnalyzing, isIntervening, uiStage]);

    useEffect(() => {
        if (uiStage !== 'thinking') {
            return undefined;
        }
        const interval = window.setInterval(() => {
            setThinkingTimer((current) => current + 1);
        }, 1000);
        return () => window.clearInterval(interval);
    }, [uiStage]);

    useEffect(() => {
        if (uiStage !== 'solving') {
            return undefined;
        }
        const interval = window.setInterval(() => {
            setSolvingTimer((current) => current + 1);
        }, 1000);
        return () => window.clearInterval(interval);
    }, [uiStage]);

    useEffect(() => () => {
        cleanupAudio();
        cleanupSocket();
        if (interventionTimeoutRef.current) {
            window.clearTimeout(interventionTimeoutRef.current);
        }
    }, []);

    useEffect(() => {
        setLaunchStage('countdown');
        setCountdownValue(3);
    }, []);

    useEffect(() => {
        if (launchStage !== 'countdown') {
            return undefined;
        }

        if (countdownValue <= 1) {
            const primingTimeout = window.setTimeout(() => {
                setLaunchStage('priming');
            }, 900);
            return () => window.clearTimeout(primingTimeout);
        }

        const tickTimeout = window.setTimeout(() => {
            setCountdownValue((current) => current - 1);
        }, 900);

        return () => window.clearTimeout(tickTimeout);
    }, [launchStage, countdownValue]);

    useEffect(() => {
        if (launchStage !== 'priming') {
            return undefined;
        }

        const startTimeout = window.setTimeout(() => {
            setLaunchStage('hidden');
            handleStartThinking();
        }, 1000);

        return () => window.clearTimeout(startTimeout);
    }, [launchStage]);

    function appendTimelineEvent(nextEvent) {
        setTimelineEvents((current) => {
            if (current.some((event) => event.id === nextEvent.id)) {
                return current;
            }
            const next = [...current, nextEvent];
            return next.slice(-12);
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
                setValidationState(data.validation_state || null);
                return;
            }
            if (type === 'phase_change') {
                setSessionPhase(data.phase || 'understanding');
                if (uiStageRef.current === 'thinking') {
                    setLifecycleState('active');
                }
                return;
            }
            if (type === 'status_update') {
                if (!isAnalyzing && !isIntervening && uiStageRef.current === 'thinking') {
                    setStatusText(data.status || 'Thinking in progress');
                }
                return;
            }
            if (type === 'timeline_event') {
                appendTimelineEvent(timelineItemFromSocket(data));
                return;
            }
            if (type === 'validation_state') {
                setValidationState(data.validation_state || null);
                return;
            }
            if (type === 'intervention' && uiStageRef.current === 'thinking') {
                setIsIntervening(true);
                setInterventionMessage(data.message || 'Think about your approach.');
                appendTimelineEvent(
                    timelineItemFromSocket({
                        event_id: `intervention-${data.timestamp}`,
                        category: 'intervention',
                        message: 'Cognitive Coach',
                        detail: data.message,
                        timestamp: data.timestamp,
                    }),
                );
                if (interventionTimeoutRef.current) {
                    window.clearTimeout(interventionTimeoutRef.current);
                }
                interventionTimeoutRef.current = window.setTimeout(() => {
                    setIsIntervening(false);
                    setInterventionMessage(null);
                }, 5000);
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
        if (!streamingEnabledRef.current || !sessionIdRef.current || !sessionStartedAtRef.current || uiStageRef.current !== 'thinking') {
            return;
        }
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
            ? new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 160000 })
            : new MediaRecorder(stream, { audioBitsPerSecond: 160000 });

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
            if (blob && blob.size > 0 && streamingEnabledRef.current && uiStageRef.current === 'thinking') {
                await streamChunk(blob);
            }
            if (streamingEnabledRef.current && desiredMicStateRef.current === 'recording' && mediaStreamRef.current && uiStageRef.current === 'thinking') {
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
                sampleRate: { ideal: 48000 },
            },
        });
        const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
        const audioContext = new AudioContextCtor();
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = ANALYSER_FFT_SIZE;
        analyser.smoothingTimeConstant = 0.84;
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
            if (!activeAnalyser || !streamingEnabledRef.current || uiStageRef.current !== 'thinking') return;
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
                    stats.noiseFloor = stats.noiseFloor * 0.96 + rms * 0.04;
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

    function resetQuestionUi() {
        setThinkingTimer(0);
        setSolvingTimer(0);
        setTimelineEvents([]);
        setAnswerResult(null);
        setRuntimeNote('');
        setIsAnalyzing(false);
        setIsIntervening(false);
        setInterventionMessage(null);
        setSessionPhase('understanding');
        setLifecycleState('initializing');
        setWaveform(createIdleWaveform());
        setValidationState(null);
        setUploadGraceUsed(0);
        uploadStartedAtRef.current = null;
        questionFinalizedRef.current = false;
    }

    function stopThinkingCapture() {
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
        cleanupSocket();
    }

    async function handleStartThinking() {
        if (uiStageRef.current !== 'pre_session') {
            return;
        }
        resetQuestionUi();
        setUiStage('loading');
        cleanupAudio();
        cleanupSocket();

        try {
            const response = await fetch(`${API_BASE_URL}/start_session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: launchConfig?.userId || null,
                    session_metadata: {
                        topic: selectedTopic,
                        mode: sessionMode,
                        source: launchConfig?.source || 'thinking-session',
                    },
                }),
            });
            if (!response.ok) {
                throw new Error('Unable to start the question.');
            }
            const session = await response.json();
            setProblemText(session.problem_payload?.raw_text || 'Problem unavailable.');
            setSessionPhase(session.initial_state?.phase || 'understanding');
            setLifecycleState('active');
            setValidationState(session.initial_state?.validation_state || null);
            sessionIdRef.current = session.session_id;
            connectSocket(session.session_id);
            sessionStartedAtRef.current = performance.now();
            chunkIndexRef.current = 0;
            setUiStage('thinking');
            await initializeAudioRuntime();
        } catch (error) {
            cleanupAudio();
            cleanupSocket();
            setUiStage('pre_session');
            setRuntimeNote(error instanceof Error ? error.message : 'Unable to initialize the question.');
        }
    }

    function handleStartSolving() {
        stopThinkingCapture();
        setLifecycleState('solving');
        setUiStage('solving');
        setIsIntervening(false);
        setInterventionMessage(null);
        setStatusText('Solving silently');
    }

    async function finalizeCurrentQuestion({ shouldPersistRound }) {
        if (!sessionIdRef.current || questionFinalizedRef.current) {
            return null;
        }

        questionFinalizedRef.current = true;
        stopThinkingCapture();

        const currentSessionId = sessionIdRef.current;
        try {
            await fetch(`${API_BASE_URL}/end_session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    final_timestamps: {
                        start_time: 0,
                        end_time: thinkingTimerRef.current,
                    },
                }),
            });
        } catch (error) {
            console.error('Unable to close question session', error);
        }

        const round = {
            questionNumber,
            sessionId: currentSessionId,
            problemText,
            thinkingSeconds: thinkingTimerRef.current,
            solvingSeconds: Math.max(solvingTimerRef.current - uploadGraceUsed, 0),
            uploadGraceUsed,
            answerResult,
        };

        if (shouldPersistRound) {
            setCompletedRounds((current) => [...current, round]);
            setQuestionNumber((current) => current + 1);
        }

        sessionIdRef.current = null;
        return round;
    }

    async function handleUploadAnswer(file) {
        if (!sessionIdRef.current || uiStage !== 'solving') return;
        setIsValidating(true);
        setRuntimeNote('');
        try {
            const currentSessionId = sessionIdRef.current;
            uploadStartedAtRef.current = performance.now();
            const imageB64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const result = reader.result;
                    if (typeof result !== 'string') {
                        reject(new Error('Unable to read the uploaded image.'));
                        return;
                    }
                    resolve(result.includes(',') ? result.split(',')[1] : result);
                };
                reader.onerror = () => reject(reader.error || new Error('Unable to read the uploaded image.'));
                reader.readAsDataURL(file);
            });

            const response = await fetch(`${API_BASE_URL}/validate_answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    image_b64: imageB64,
                }),
            });
            if (!response.ok) {
                throw new Error('Answer validation failed.');
            }

            const data = await response.json();
            const graceUsed = Math.min(
                UPLOAD_GRACE_SECONDS,
                Math.max(0, Math.round((performance.now() - (uploadStartedAtRef.current || performance.now())) / 1000)),
            );
            setUploadGraceUsed(graceUsed);
            setAnswerResult(data);
            const round = await finalizeCurrentQuestion({ shouldPersistRound: false });
            const finalRound = {
                ...(round || {}),
                questionNumber,
                sessionId: round?.sessionId || currentSessionId,
                problemText,
                thinkingSeconds: thinkingTimerRef.current,
                solvingSeconds: Math.max(solvingTimerRef.current - graceUsed, 0),
                uploadGraceUsed: graceUsed,
                answerResult: data,
            };
            setCompletedRounds((current) => [...current, finalRound]);
            setQuestionNumber((current) => current + 1);
            setUiStage('question_done');
            setLifecycleState('completed');
        } catch (error) {
            console.error('Answer validation error:', error);
            setRuntimeNote(error instanceof Error ? error.message : 'Unable to validate answer.');
        } finally {
            uploadStartedAtRef.current = null;
            setIsValidating(false);
        }
    }

    function handleNextQuestion() {
        resetQuestionUi();
        setProblemText('The problem will appear here when the session starts.');
        setUiStage('pre_session');
        setLaunchStage('hidden');
    }

    async function handleEndSession() {
        if (isEndingSession) return;
        setIsEndingSession(true);
        setRuntimeNote('');

        try {
            let rounds = [...completedRounds];

            if (sessionIdRef.current && !questionFinalizedRef.current) {
                const round = await finalizeCurrentQuestion({ shouldPersistRound: false });
                if (round) {
                    rounds = [...rounds, round];
                }
            }

            if (rounds.length === 0) {
                setRuntimeNote('Complete at least one question before ending the session.');
                setIsEndingSession(false);
                return;
            }

            const reports = await Promise.all(
                rounds.map(async (round) => {
                    try {
                        const response = await fetch(`${API_BASE_URL}/generate_report`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ session_id: round.sessionId }),
                        });
                        if (!response.ok) {
                            return null;
                        }
                        return await response.json();
                    } catch {
                        return null;
                    }
                }),
            );

            const roundsWithReports = rounds.map((round, index) => ({
                ...round,
                report: reports[index] || null,
            }));
            const aggregateReport = buildAggregateReport(roundsWithReports, reports);
            localStorage.setItem('mathmend_session_report', JSON.stringify(aggregateReport));
            localStorage.setItem('mathmend_session_id', rounds[0].sessionId);
            localStorage.setItem('mathmend_session_time', String(aggregateReport.total_session_time || 0));
            navigate('/thinking-report');
        } catch (error) {
            console.error('Unable to end session', error);
            setRuntimeNote('Unable to generate the final report.');
            setIsEndingSession(false);
        }
    }

    return (
        <div className="relative min-h-screen bg-[radial-gradient(circle_at_top,rgba(251,191,36,0.16),transparent_22%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_42%,#edf3f7_100%)] px-3 py-3 text-slate-950 sm:px-4 lg:px-5">
            <AnimatePresence>
                {launchStage !== 'hidden' && (
                    <motion.div
                        key={launchStage}
                        initial={{ opacity: 1 }}
                        exit={{ opacity: 0, transition: { duration: 0.45 } }}
                        className={`fixed inset-0 z-50 flex items-center justify-center overflow-hidden ${
                            sessionMode === 'pro'
                                ? 'bg-[radial-gradient(circle_at_top,rgba(251,191,36,0.3),transparent_20%),linear-gradient(180deg,#020617_0%,#111827_55%,#1e293b_100%)]'
                                : 'bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.24),transparent_20%),linear-gradient(180deg,#0f172a_0%,#172554_55%,#0f172a_100%)]'
                        }`}
                    >
                        <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ repeat: Infinity, duration: sessionMode === 'pro' ? 10 : 14, ease: 'linear' }}
                            className="absolute h-[72vw] w-[72vw] rounded-full border border-white/10"
                        />
                        <motion.div
                            animate={{ rotate: -360, scale: [1, 1.06, 1] }}
                            transition={{ repeat: Infinity, duration: sessionMode === 'pro' ? 7 : 9, ease: 'linear' }}
                            className="absolute h-[54vw] w-[54vw] rounded-full border border-white/10"
                        />
                        <div className="relative px-6 text-center text-white">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.42em] text-white/55">
                                {sessionMode === 'pro' ? 'Pro Launch' : 'Thinking Launch'}
                            </p>
                            <p className="mt-4 text-sm uppercase tracking-[0.24em] text-white/70">{selectedTopic}</p>
                            <AnimatePresence mode="wait">
                                {launchStage === 'countdown' ? (
                                    <motion.div
                                        key={countdownValue}
                                        initial={{ opacity: 0, scale: 0.72, filter: 'blur(8px)' }}
                                        animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                                        exit={{ opacity: 0, scale: 1.18, filter: 'blur(10px)' }}
                                        transition={{ duration: 0.42 }}
                                        className="mt-5 text-[28vw] font-black leading-none tracking-[-0.08em] sm:text-[18rem]"
                                    >
                                        {countdownValue}
                                    </motion.div>
                                ) : (
                                    <motion.div
                                        key="priming"
                                        initial={{ opacity: 0, y: 24 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0 }}
                                        className="mt-8"
                                    >
                                        <p className="text-4xl font-black uppercase tracking-[0.14em] text-amber-200 sm:text-6xl">
                                            Think
                                        </p>
                                        <p className="mt-4 text-sm leading-7 text-white/72">
                                            Runtime is priming. Microphone capture starts in one second.
                                        </p>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="mx-auto grid max-w-[1720px] gap-3 xl:grid-cols-[1.02fr_1.18fr_0.94fr]">
                <ProblemPanel problemText={problemText} />
                <CognitiveIDE
                    uiStage={uiStage}
                    thinkingTimer={thinkingTimer}
                    effectiveSolvingTimer={Math.max(solvingTimer - uploadGraceUsed, 0)}
                    uploadGraceUsed={uploadGraceUsed}
                    waveform={waveform}
                    runtimeNote={runtimeNote}
                    answerResult={answerResult}
                    isValidating={isValidating}
                    isEndingSession={isEndingSession}
                    onStartThinking={handleStartThinking}
                    onStartSolving={handleStartSolving}
                    onEndSession={handleEndSession}
                    onUploadAnswer={handleUploadAnswer}
                    onNextQuestion={handleNextQuestion}
                />
                <TimelinePanel
                    events={timelineEvents}
                    validationState={validationState}
                    sessionPhase={sessionPhase}
                    lifecycleState={lifecycleState}
                    statusText={statusText}
                    uiStage={uiStage}
                    interventionMessage={interventionMessage}
                />
            </div>

            <div className="mx-auto mt-3 grid max-w-[1720px] gap-3 rounded-[22px] border border-slate-200/80 bg-white/88 p-3 shadow-[0_16px_50px_rgba(15,23,42,0.06)] md:grid-cols-7">
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Question</p>
                    <p className="mt-1 text-sm font-bold text-slate-900">{Math.max(1, questionNumber - (uiStage === 'question_done' ? 1 : 0))}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Completed</p>
                    <p className="mt-1 text-sm font-bold text-slate-900">{completedRounds.length}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Phase</p>
                    <p className="mt-1 text-sm font-bold text-slate-900">{sessionPhase.replaceAll('_', ' ')}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Status</p>
                    <p className="mt-1 text-sm font-bold text-slate-900">{statusText}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Upload Grace</p>
                    <p className="mt-1 text-sm font-bold text-slate-900">{formatTimer(uploadGraceUsed)} used</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Topic Lock</p>
                    <p className="mt-1 text-sm font-bold text-slate-900">{selectedTopic}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Mode</p>
                    <p className="mt-1 text-sm font-bold capitalize text-slate-900">{sessionMode}</p>
                </div>
            </div>
        </div>
    );
}
