'use client';

import React from 'react';
import { useJarvisVoice } from '@/hooks/useJarvisVoice';
import styles from './jarvis-voice.module.css';

export default function JarvisVoiceWidget() {
  const { isRecording, isSpeaking, voiceError, startListening, stopListening } = useJarvisVoice();

  // Determine current interaction state
  const state = isSpeaking ? 'speaking' : isRecording ? 'listening' : 'idle';

  const handleToggle = () => {
    if (isRecording) {
      stopListening();
    } else {
      startListening();
    }
  };

  return (
    <div className={styles.voiceWidget} role="region" aria-label="VayuVani Voice Co-Pilot">
      {voiceError ? (
        <div id="vayuvani-error" className={styles.voiceError} role="alert">
          {voiceError}
        </div>
      ) : null}
      <button
        type="button"
        className={styles.orbButton}
        data-state={state}
        onClick={handleToggle}
        title={isRecording ? 'Tap to pause VayuVani' : 'Tap to speak with VayuVani AI'}
        aria-label={isRecording ? 'Stop voice interaction' : 'Start voice interaction with VayuVani'}
        aria-describedby={voiceError ? 'vayuvani-error' : undefined}
      >
        <div className={styles.orbAura} aria-hidden="true" />
        <div className={styles.orbCore}>
          <div className={`${styles.fluidWave} ${styles.wave1}`} aria-hidden="true" />
          <div className={`${styles.fluidWave} ${styles.wave2}`} aria-hidden="true" />

          <svg className={styles.voiceMicIcon} viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <defs>
              <linearGradient id="voice-mic-gradient" x1="5" y1="2" x2="19" y2="22" gradientUnits="userSpaceOnUse">
                <stop stopColor="#00c7ff" />
                <stop offset="0.34" stopColor="#5856d6" />
                <stop offset="0.7" stopColor="#bf5af2" />
                <stop offset="1" stopColor="#ff375f" />
              </linearGradient>
            </defs>
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" stroke="url(#voice-mic-gradient)" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="url(#voice-mic-gradient)" />
            <line x1="12" x2="12" y1="19" y2="22" stroke="url(#voice-mic-gradient)" />
          </svg>
        </div>
      </button>
    </div>
  );
}
