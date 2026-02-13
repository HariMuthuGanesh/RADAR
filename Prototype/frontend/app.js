import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Configuration
const WS_URL = 'ws://localhost:8000/ws/radar';
let isLive = true;
let pointsData = [];

// DOM Elements
const frameIdEl = document.getElementById('frame-id');
const pointCountEl = document.getElementById('point-count');
const avgVelocityEl = document.getElementById('avg-velocity');
const statusTagEl = document.getElementById('status-tag');
const statusTextEl = statusTagEl.querySelector('.status-text');
const modeLiveBtn = document.getElementById('mode-live');
const modeFileBtn = document.getElementById('mode-file');
const uploadSection = document.getElementById('upload-section');
const csvUploadInput = document.getElementById('csv-upload');
const fileNameEl = document.getElementById('file-name');

// Three.js Setup
const canvas = document.getElementById('radar-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(5, 5, 5);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// Grid and Visualization
const gridHelper = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
gridHelper.rotation.x = Math.PI / 2;
scene.add(gridHelper);

const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
scene.add(ambientLight);

// Point Cloud Geometry
const maxPoints = 5000;
const geometry = new THREE.BufferGeometry();
const positions = new Float32Array(maxPoints * 3);
const colors = new Float32Array(maxPoints * 3);

geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

const material = new THREE.PointsMaterial({
    size: 0.15,
    vertexColors: true,
    transparent: true,
    opacity: 0.8,
    sizeAttenuation: true
});

const pointCloud = new THREE.Points(geometry, material);
scene.add(pointCloud);

// Helper: Update Point Cloud
function updatePointCloud(points) {
    const posAttr = geometry.attributes.position;
    const colAttr = geometry.attributes.color;

    let totalVel = 0;

    points.forEach((p, i) => {
        if (i >= maxPoints) return;

        // Update positions (x, y, z)
        posAttr.array[i * 3] = p.x;
        posAttr.array[i * 3 + 1] = p.z; // Top-down flip
        posAttr.array[i * 3 + 2] = -p.y;

        // Update colors based on velocity
        const v = Math.abs(p.v);
        totalVel += v;
        const color = new THREE.Color().setHSL(0.6 - (v * 0.1), 0.8, 0.5);
        colAttr.array[i * 3] = color.r;
        colAttr.array[i * 3 + 1] = color.g;
        colAttr.array[i * 3 + 2] = color.b;
    });

    // Reset remaining points to infinity (hide them)
    for (let i = points.length; i < maxPoints; i++) {
        posAttr.array[i * 3] = 1000;
        posAttr.array[i * 3 + 1] = 1000;
        posAttr.array[i * 3 + 2] = 1000;
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;

    // Update Stats
    pointCountEl.innerText = points.length;
    avgVelocityEl.innerText = `${(totalVel / (points.length || 1)).toFixed(2)} m/s`;
}

// WebSocket Logic
let socket;
function connectWS() {
    if (!isLive) return;

    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        statusTagEl.classList.replace('disconnected', 'connected');
        statusTextEl.innerText = 'LIVE';
    };

    socket.onmessage = (event) => {
        if (!isLive) return;
        const data = JSON.parse(event.data);
        if (data.points) {
            frameIdEl.innerText = data.frame;
            updatePointCloud(data.points);
        }
    };

    socket.onclose = () => {
        statusTagEl.classList.replace('connected', 'disconnected');
        statusTextEl.innerText = 'DISCONNECTED';
        if (isLive) setTimeout(connectWS, 3000);
    };
}

// CSV Upload Logic
csvUploadInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    fileNameEl.innerText = file.name;
    const reader = new FileReader();

    reader.onload = (event) => {
        const text = event.target.result;
        const rows = text.split('\n').slice(1); // Skip header
        const parsedPoints = rows.map(row => {
            const cols = row.split(',');
            if (cols.length < 5) return null;
            // frame,x,y,z,velocity
            return {
                x: parseFloat(cols[1]),
                y: parseFloat(cols[2]),
                z: parseFloat(cols[3]),
                v: parseFloat(cols[4])
            };
        }).filter(p => p !== null);

        updatePointCloud(parsedPoints);
        frameIdEl.innerText = 'FILE';
    };

    reader.readAsText(file);
});

// UI Event Handlers
modeLiveBtn.onclick = () => {
    isLive = true;
    modeLiveBtn.classList.add('active');
    modeFileBtn.classList.remove('active');
    uploadSection.style.display = 'none';
    connectWS();
};

modeFileBtn.onclick = () => {
    isLive = false;
    modeLiveBtn.classList.remove('active');
    modeFileBtn.classList.add('active');
    uploadSection.style.display = 'block';
    if (socket) socket.close();
};

// Handle Resize
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// Animation Loop
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

// Start
connectWS();
animate();
