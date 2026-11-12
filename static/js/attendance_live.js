// Live Camera AI Attendance Engine

let videoStream = null;
let scanningInterval = null;
let isProcessingFrame = false;

const videoEl = document.getElementById('liveVideo');
const overlayCanvas = document.getElementById('overlayCanvas');
const sessionActiveBadge = document.getElementById('sessionActiveBadge');
const presentCounter = document.getElementById('livePresentCounter');
const recentMarkedCard = document.getElementById('recentMarkedCard');
const studentRosterTable = document.getElementById('rosterTableBody');

// Web Audio API Beep Generator for recognition confirmation
function playSuccessBeep() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
        osc.frequency.exponentialRampToValueAtTime(1320, audioCtx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.15);
    } catch (e) {
        // Audio context may require user interaction first
    }
}

async function startCamera() {
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: 'user'
            },
            audio: false
        });
        if (videoEl) {
            videoEl.srcObject = videoStream;
            videoEl.play();
        }
        if (sessionActiveBadge) {
            sessionActiveBadge.className = 'badge bg-success';
            sessionActiveBadge.innerHTML = '<i class="bi bi-broadcast"></i> Scanning Live';
        }
        startScanningLoop();
    } catch (err) {
        console.warn('Camera failed:', err);
        if (sessionActiveBadge) {
            sessionActiveBadge.className = 'badge bg-warning text-dark';
            sessionActiveBadge.innerHTML = '<i class="bi bi-camera-video-off"></i> Camera Offline';
        }
    }
}

function stopCamera() {
    if (scanningInterval) clearInterval(scanningInterval);
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
    }
}

function startScanningLoop() {
    if (scanningInterval) clearInterval(scanningInterval);
    scanningInterval = setInterval(async () => {
        if (isProcessingFrame) return;
        if (!videoEl || videoEl.readyState < 2) return;

        isProcessingFrame = true;
        try {
            const canvas = document.createElement('canvas');
            canvas.width = videoEl.videoWidth || 640;
            canvas.height = videoEl.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
            const b64 = canvas.toDataURL('image/jpeg', 0.8);

            await sendFrameForRecognition(b64);
        } catch (e) {
            console.error('Frame processing error:', e);
        } finally {
            isProcessingFrame = false;
        }
    }, 900); // scan every 900ms
}

async function sendFrameForRecognition(base64Image) {
    const sessionId = window.ATTENDANCE_SESSION_ID;
    if (!sessionId) return;

    try {
        const res = await fetch('/api/recognize_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                image: base64Image
            })
        });

        const data = await res.json();
        if (data.success && data.faces) {
            drawFaceBoundingBoxes(data.faces);
            handleRecognitionResults(data.faces);
        }
    } catch (err) {
        console.error('API Error:', err);
    }
}

function drawFaceBoundingBoxes(faces) {
    if (!overlayCanvas || !videoEl) return;
    const ctx = overlayCanvas.getContext('2d');
    overlayCanvas.width = videoEl.videoWidth || 640;
    overlayCanvas.height = videoEl.videoHeight || 480;
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    faces.forEach(f => {
        if (!f.box) return;
        const [x, y, w, h] = f.box;

        if (f.status === 'MARKED_PRESENT') {
            ctx.strokeStyle = '#10b981'; // Green
            ctx.lineWidth = 3;
            ctx.strokeRect(x, y, w, h);

            ctx.fillStyle = '#10b981';
            ctx.fillRect(x, y - 24, w, 24);
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 12px Segoe UI, sans-serif';
            ctx.fillText(`${f.student?.roll_number} (${f.confidence}%)`, x + 5, y - 7);
        } else if (f.status === 'ALREADY_MARKED') {
            ctx.strokeStyle = '#f59e0b'; // Amber
            ctx.lineWidth = 3;
            ctx.strokeRect(x, y, w, h);

            ctx.fillStyle = '#f59e0b';
            ctx.fillRect(x, y - 24, w, 24);
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 12px Segoe UI, sans-serif';
            ctx.fillText(`${f.student?.roll_number} [Marked]`, x + 5, y - 7);
        } else {
            ctx.strokeStyle = '#ef4444'; // Red
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, w, h);

            ctx.fillStyle = '#ef4444';
            ctx.fillRect(x, y - 20, w, 20);
            ctx.fillStyle = '#ffffff';
            ctx.font = '11px Segoe UI, sans-serif';
            ctx.fillText('Unregistered Face', x + 5, y - 5);
        }
    });
}

function handleRecognitionResults(faces) {
    faces.forEach(f => {
        if (f.status === 'MARKED_PRESENT') {
            playSuccessBeep();
            updateLiveRoster(f.student?.student_id, 'Present', f.confidence);
            showRecentlyMarkedCard(f.student, f.confidence, f.marked_at);
        } else if (f.status === 'ALREADY_MARKED') {
            // Already marked toast / info
            console.log('Already marked:', f.student?.roll_number);
        }
    });
}

function showRecentlyMarkedCard(student, confidence, markedAt) {
    if (!recentMarkedCard) return;
    recentMarkedCard.classList.remove('d-none');
    recentMarkedCard.innerHTML = `
        <div class="card border-success bg-light shadow-sm">
            <div class="card-body p-2 d-flex align-items-center gap-2">
                <div class="bg-success text-white rounded-circle p-2 d-flex align-items-center justify-content-center" style="width: 36px; height: 36px;">
                    <i class="bi bi-check-lg"></i>
                </div>
                <div class="flex-grow-1">
                    <strong class="text-success">${student.full_name}</strong>
                    <div class="small text-muted">${student.roll_number} | Match: ${confidence}% | ${markedAt.split(' ')[1] || markedAt}</div>
                </div>
                <span class="badge bg-success">Marked Present</span>
            </div>
        </div>
    `;
}

function updateLiveRoster(studentId, status, confidence) {
    if (!studentId) return;
    const row = document.getElementById(`studentRow-${studentId}`);
    if (row) {
        const statusCell = row.querySelector('.status-col');
        if (statusCell) {
            statusCell.innerHTML = `<span class="badge bg-success"><i class="bi bi-check-circle"></i> ${status}</span>`;
        }
        const timeCell = row.querySelector('.time-col');
        if (timeCell) {
            const now = new Date();
            timeCell.textContent = now.toLocaleTimeString();
        }
        const confCell = row.querySelector('.conf-col');
        if (confCell && confidence) {
            confCell.textContent = `${confidence}%`;
        }
        row.classList.add('table-success');
    }

    // Update Counter
    if (presentCounter) {
        let current = parseInt(presentCounter.textContent || '0');
        presentCounter.textContent = current + 1;
    }
}

// Manual Marking Trigger
async function markStudentManually(studentId, status) {
    const sessionId = window.ATTENDANCE_SESSION_ID;
    try {
        const res = await fetch('/api/manual_mark_student', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                student_id: studentId,
                status: status
            })
        });
        const data = await res.json();
        if (data.success) {
            updateLiveRoster(studentId, status, null);
        } else {
            alert(data.message || 'Error marking attendance');
        }
    } catch (e) {
        alert('Failed to mark student manually.');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (videoEl) {
        startCamera();
    }
});

window.addEventListener('beforeunload', () => {
    stopCamera();
});
