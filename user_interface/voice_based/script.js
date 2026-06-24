 const ring = document.getElementById('ring');
  const status = document.getElementById('status');
  let conversationActive = false;
  let currentState = 'idle';
  let thinkingTimer = null;
  let speakingTimer = null;
  let recognizing = false;
  let currentAudio = null;
  let currentFetch = null;

  const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  document.addEventListener('keydown', function(event) {
      if (event.code !== 'Space') return;
      event.preventDefault();
      if (!conversationActive) {
          conversationActive = true;
          startListening();
      } else {
          endConversation();
      }
  });

  function startListening() {
      clearTimers();
      if (currentAudio) { currentAudio.pause(); currentAudio = null; }
      if (currentFetch) { currentFetch.abort(); currentFetch = null; }
      setRingState('listening');
      startRecognition();
  }

  function startRecognition() {
      if (recognizing) return;
      try { recognition.start(); recognizing = true; } catch(e) {}
  }

  recognition.onend = function() {
      recognizing = false;
      if (!conversationActive) return;
      setTimeout(() => startRecognition(), 100);
  };

  recognition.onresult = async function(event) {
      const transcript = event.results[0][0].transcript;
      console.log('Heard:', transcript);

      if (currentState === 'thinking' || currentState === 'speaking') {
          startListening();
          return;
      }

      setRingState('thinking');

      try {
          const controller = new AbortController();
          currentFetch = controller;
          const response = await fetch('http://localhost:5000/voice', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ text: transcript }),
              signal: controller.signal
          });
          currentFetch = null;

          if (!conversationActive) return;

          const audioBlob = await response.blob();
          const audioUrl = URL.createObjectURL(audioBlob);
          currentAudio = new Audio(audioUrl);

          setRingState('speaking');

          currentAudio.onended = function() {
              URL.revokeObjectURL(audioUrl);
              if (conversationActive) startListening();
          };

          currentAudio.play();

      } catch(e) {
          console.error('Server error:', e);
          if (conversationActive) startListening();
      }
  };

  recognition.onerror = function(event) {
      recognizing = false;
      if (!conversationActive) return;
      if (event.error === 'not-allowed') { endConversation(); return; }
      setTimeout(() => startRecognition(), 300);
  };

  function endConversation() {
      conversationActive = false;
      clearTimers();
      recognizing = false;
      recognition.abort();
      setRingState('idle');
  }

  function clearTimers() {
      clearTimeout(thinkingTimer);
      clearTimeout(speakingTimer);
  }

  const statusLabels = {
      idle: 'standby',
      listening: 'listening',
      thinking: 'processing',
      speaking: 'responding'
  };

  function setRingState(state) {
      currentState = state;
      ['listening', 'thinking', 'speaking'].forEach(s => ring.classList.remove(s));
      if (state !== 'idle') ring.classList.add(state);
      status.textContent = statusLabels[state] || state;
  }