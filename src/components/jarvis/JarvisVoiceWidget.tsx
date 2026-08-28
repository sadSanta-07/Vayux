'use client';

import React from 'react';
import { useJarvisVoice } from '@/hooks/useJarvisVoice';
import styles from './jarvis-voice.module.css';

export default function JarvisVoiceWidget() {
  const { isRecording, isSpeaking, startListening, stopListening } = useJarvisVoice();

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
      {/* Fluid Glowing Voice Orb - Enlarages on click and glows/flows organically */}
      <button
        type="button"
        className={styles.orbButton}
        data-state={state}
        onClick={handleToggle}
        title={isRecording ? 'Tap to pause VayuVani' : 'Tap to speak with VayuVani AI'}
        aria-label={isRecording ? 'Stop voice interaction' : 'Start voice interaction with VayuVani'}
      >
        <div className={styles.orbAura} aria-hidden="true" />
        <div className={styles.orbCore}>
          <div className={`${styles.fluidWave} ${styles.wave1}`} aria-hidden="true" />
          <div className={`${styles.fluidWave} ${styles.wave2}`} aria-hidden="true" />

          {/* Dynamic Mic / Soundwave Icon */}
          <svg className={styles.micIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {isSpeaking ? (
              <>
                <path d="M2 10v4" />
                <path d="M6 6v12" />
                <path d="M10 3v18" />
                <path d="M14 7v10" />
                <path d="M18 5v14" />
                <path d="M22 10v4" />
              </>
            ) : isRecording ? (
              <>
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" x2="12" y1="19" y2="22" />
              </>
            ) : (
              <>
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" x2="12" y1="19" y2="22" />
              </>
            )}
          </svg>
        </div>
      </button>
    </div>
  );
}
