// Webcam Face Enrollment System

let videoStream = null;
const videoElement = document.getElementById('webcamVideo');
const captureBtn = document.getElementById('startCaptureBtn');
const progressBar = document.getElementById('enrollProgressBar');
const statusBadge = document.getElementById('enrollStatusBadge');
const thumbnailsContainer = document.getElementById('samplesThumbnails');

async function initWebcam() {
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: 'user'
            },
            audio: false
        });
        if (videoElement) {
            videoElement.srcObject = videoStream;
            videoElement.play();
        }
        if (statusBadge) {
            statusBadge.className = 'badge bg-success';
            statusBadge.textContent = 'Camera Active';
        }
    } catch (err) {
        console.warn('Webcam access error:', err);
        if (statusBadge) {
            statusBadge.className = 'badge bg-warning text-dark';
            statusBadge.textContent = 'Camera Blocked / Unavailable';
        }
        const errorAlert = document.getElementById('cameraErrorAlert');
        if (errorAlert) {
            errorAlert.classList.remove('d-none');
            errorAlert.innerHTML = `<strong>Webcam Notice:</strong> ${err.message || 'Could not access local camera.'} You can use the synthetic face generator below to test model training without hardware.`;
        }
    }
}

function captureFrameBase64() {
    if (!videoElement) return null;
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth || 640;
    canvas.height = videoElement.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
}

// Generate an artificial face canvas sample for simulation/fallback
function generateSyntheticFaceSample(rollNumber) {
    const canvas = document.createElement('canvas');
    canvas.width = 200;
    canvas.height = 200;
    const ctx = canvas.getContext('2d');
    
    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, 200, 200);
    grad.addColorStop(0, '#e2e8f0');
    grad.addColorStop(1, '#94a3b8');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 200, 200);

    // Oval Face
    ctx.fillStyle = '#fbcfe8';
    ctx.beginPath();
    ctx.ellipse(100, 100, 60, 75, 0, 0, 2 * Math.PI);
    ctx.fill();

    // Eyes
    ctx.fillStyle = '#1e293b';
    ctx.beginPath();
    ctx.arc(80, 85, 6, 0, 2 * Math.PI);
    ctx.arc(120, 85, 6, 0, 2 * Math.PI);
    ctx.fill();

    // Mouth
    ctx.beginPath();
    ctx.arc(100, 125, 20, 0, Math.PI);
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 3;
    ctx.stroke();

    return canvas.toDataURL('image/jpeg', 0.85);
}

async function startFaceRegistration(studentId, rollNumber) {
    const samplesNeeded = 10;
    const samples = [];
    
    if (captureBtn) captureBtn.disabled = true;
    if (thumbnailsContainer) thumbnailsContainer.innerHTML = '';
    
    for (let i = 1; i <= samplesNeeded; i++) {
        let frameB64 = null;
        if (videoStream && videoElement && videoElement.readyState >= 2) {
            frameB64 = captureFrameBase64();
        } else {
            // Synthetic fallback
            frameB64 = generateSyntheticFaceSample(rollNumber);
        }

        if (frameB64) {
            samples.push(frameB64);
            
            // Add thumbnail
            if (thumbnailsContainer) {
                const img = document.createElement('img');
                img.src = frameB64;
                img.className = 'img-thumbnail me-1 mb-1';
                img.style.width = '60px';
                img.style.height = '60px';
                img.style.objectFit = 'cover';
                thumbnailsContainer.appendChild(img);
            }
        }

        // Update progress
        const pct = Math.round((i / samplesNeeded) * 100);
        if (progressBar) {
            progressBar.style.width = `${pct}%`;
            progressBar.textContent = `${pct}%`;
        }

        await new Promise(r => setTimeout(r, 200));
    }

    // Send to backend
    try {
        if (statusBadge) {
            statusBadge.className = 'badge bg-info';
            statusBadge.textContent = 'Processing & Training LBPH Model...';
        }

        const response = await fetch('/api/register_face_samples', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: studentId,
                samples: samples
            })
        });

        const resData = await response.json();
        if (resData.success) {
            if (statusBadge) {
                statusBadge.className = 'badge bg-success';
                statusBadge.textContent = 'Face Registered Successfully!';
            }
            alert('Face samples registered and AI model retrained successfully!');
            window.location.href = '/admin/students';
        } else {
            alert('Error: ' + (resData.message || 'Failed to register face samples.'));
            if (captureBtn) captureBtn.disabled = false;
        }
    } catch (err) {
        console.error('Registration error:', err);
        alert('Server communication error during face enrollment.');
        if (captureBtn) captureBtn.disabled = false;
    }
}

// Auto init on page load if element exists
if (videoElement) {
    initWebcam();
}
