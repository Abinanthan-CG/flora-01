import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// Exact verified stance velocities & turn angular velocity from build_quadruped.py (zero foot slip!)
const WALK_VEL   = 0.26 / (0.75 * 2.0);          // 0.173333 m/s forward
const BACK_VEL   = 0.20 / (0.75 * 2.0);          // 0.133333 m/s reverse (no throttle while backing up!)
const TROT_VEL   = 0.34 / (0.56 * (28 / 24));    // 0.520408 m/s forward trot
const TURN_OMEGA = 0.24 / (0.56 * 1.0);          // 0.428571 rad/s (24.6 deg/s) exact zero-slip in-place yaw!

const PART_ROLES = [
  ['carapace', 'Faceted Ceramic Carapace'],
  ['chassis', 'Anodized Aluminum Spine'],
  ['chest_grille', 'Chest Radiator Intake'],
  ['solar_hood', 'Front Hood PV Array'],
  ['solar_flank', 'Flank PV Solar Array'],
  ['planter_collar', 'Octagonal Planter & Drip Ring'],
  ['planter_soil', 'Botanical Soil Substrate'],
  ['planter_moss', 'Dual-Tone Velvety Moss'],
  ['planter_plants', 'UV-Veined Ferns & Sprouts'],
  ['pedestal_turret', 'Canopy Yaw Base Turret'],
  ['pedestal_drums', '4-Bolt Pitch Pivot Drums'],
  ['pedestal_yfork', 'Sculpted Organic Y-Pedestal'],
  ['canopy_shell', 'Aerospace Leaf Canopy Frame'],
  ['canopy_solar', '6-Bay Curved PV Canopy'],
  ['canopy_leds', 'LED Grow-Light Diffuser Deck'],
  ['rear_pods', 'Dual-Bay Battery/Water Pods'],
  ['rear_pod_glows', 'Rear X-Vent & Status Optics'],
  ['belly_conduit', 'Rear Hydraulic Braid Conduit'],
  ['neck_collar', 'Articulated Neck Bellows'],
  ['neck_shell', 'Armored Neck Bridge'],
  ['head_shell', 'Sensor Head Casing'],
  ['head_bezel', 'Front Optical Bezel'],
  ['head_optics', 'Dual Circular Vision Optics'],
  ['head_chin', 'Faceted Chin Skid Guard'],
  ['ant_vane', 'Rear Telemetry Antenna Strut'],
  ['ant_tip', 'Luminous Antenna Beacon'],
  ['shoulder_cowl', '3D-Crowned Shoulder Armor'],
  ['shoulder_vents', 'Glowing Amber Louver Vents'],
  ['shoulder_drum', '104mm Harmonic Shoulder Drum'],
  ['shoulder_mount', 'Abduction Servo Bulkhead'],
  ['upper_arm', 'CNC Upper Foreleg Beam'],
  ['elbow_drum', '80mm 4-Bolt Harmonic Elbow'],
  ['elbow_collar', 'Bolted Lime Clamshell Collar'],
  ['forearm', 'CNC-Milled Channel Forearm'],
  ['hyd_barrel', 'Banjo-Fitted Hydraulic Barrel'],
  ['hyd_rod', 'Polished Chrome Piston Rod'],
  ['wrist_drum', '56mm Rotary Wrist Drum'],
  ['hip_cowl', '3D-Crowned Hip Armor'],
  ['hip_drum', '104mm Harmonic Hip Drum'],
  ['hip_mount', 'Rear Abduction Servo Mount'],
  ['thigh', 'CNC-Milled Rear Thigh'],
  ['knee_drum', '80mm 4-Bolt Harmonic Knee'],
  ['knee_collar', 'Bolted Lime Knee Guard'],
  ['shin', 'CNC-Milled Rear Shin & Ram'],
  ['hock_drum', '56mm Rotary Hock Drum'],
  ['metatarsal', 'Digitigrade Metatarsal Strut'],
  ['hose_flex', 'Flex-Skinned Braided Conduit'],
  ['paw_ankle', 'Forked Ankle Clevis Block'],
  ['paw_pad', '7-Rib Rubber Traction Paw'],
];

function inferRole(name) {
  for (const [k, label] of PART_ROLES) {
    if (name.includes(k)) return label;
  }
  return 'Mechanical Assembly';
}

// ============================================================================
// 1. RENDERER, SCENE, POST-PROCESSING & STUDIO STAGE
// ============================================================================
const container = document.getElementById('viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.04;
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1f2421);
scene.fog = new THREE.FogExp2(0x1f2421, 0.055);

// Dual-Path PMREM IBL: Studio RoomEnvironment (for Studio Grid) + Physical Outdoor Sky/Sun/Ground IBL (for Conservatory!)
const pmrem = new THREE.PMREMGenerator(renderer);
pmrem.compileEquirectangularShader();
const studioEnvTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
let outdoorEnvTex = null;
scene.environment = studioEnvTex;
scene.environmentIntensity = 0.65;
const maxAniso = Math.min(16, renderer.capabilities.getMaxAnisotropy());

const camera = new THREE.PerspectiveCamera(44, window.innerWidth / window.innerHeight, 0.04, 140);
camera.position.set(2.45, 1.16, 2.35);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.065;
controls.target.set(0.02, 0.56, 0.0);
controls.minDistance = 0.45;
controls.maxDistance = 15.5;
controls.maxPolarAngle = Math.PI * 0.492;
controls._dragging = false;
controls.addEventListener('start', () => { controls._dragging = true; });
controls.addEventListener('end', () => { controls._dragging = false; });

// Post-processing with delicate optical UnrealBloom (high threshold so white armor never blooms!)
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.09, // subtle optical glow, never harsh
  0.28, // tight natural halo radius
  1.28  // threshold strictly above sunlit ceramic white highlights
);
composer.addPass(bloomPass);
composer.addPass(new OutputPass());

// ============================================================================
// 2. LIGHTING RIG & PRECISION ARCHITECTURAL SCROLLING FLOOR
// ============================================================================
const hemiLight = new THREE.HemisphereLight(0xfff4e0, 0x2b332d, 0.65);
scene.add(hemiLight);

const sunLight = new THREE.DirectionalLight(0xffd79e, 3.6);
sunLight.position.set(10.5, 6.2, 8.2);
sunLight.castShadow = true;
sunLight.shadow.mapSize.set(4096, 4096);
sunLight.shadow.camera.near = 0.5;
sunLight.shadow.camera.far = 42;
const sBound = 10.6;
sunLight.shadow.camera.left = -sBound;
sunLight.shadow.camera.right = sBound;
sunLight.shadow.camera.top = sBound;
sunLight.shadow.camera.bottom = -sBound;
sunLight.shadow.bias = -0.00022;
sunLight.shadow.normalBias = 0.014;
sunLight.shadow.radius = 1.6;
scene.add(sunLight);
scene.add(sunLight.target);

const rimLight = new THREE.DirectionalLight(0xdceeff, 0.95);
rimLight.position.set(-3.0, 2.2, -2.5);
scene.add(rimLight);

// Soft warm-lime canopy grow-light bouncing gently onto the moss & ferns
const growLight = new THREE.PointLight(0xc8f542, 0.85, 1.35, 2.0);
growLight.position.set(-0.02, 0.92, 0.0);
scene.add(growLight);

// Crisp procedural 0.25m architectural slate grid floor texture
function makeGridTexture(bgHex, lineHex, majHex) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 512;
  const ctx = c.getContext('2d');
  ctx.fillStyle = bgHex;
  ctx.fillRect(0, 0, 512, 512);
  // Subtle micro-concrete grain
  for (let i = 0; i < 2400; i++) {
    const x = Math.random() * 512, y = Math.random() * 512;
    ctx.fillStyle = Math.random() > 0.5 ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.025)';
    ctx.fillRect(x, y, 2, 2);
  }
  // 4x4 sub-cells = 0.25m each per 1.0m repeat tile
  ctx.strokeStyle = lineHex;
  ctx.lineWidth = 2;
  for (let k = 1; k < 4; k++) {
    const p = k * 128;
    ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, 512); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(512, p); ctx.stroke();
  }
  // Major 1.0m border hairline + cross tick
  ctx.strokeStyle = majHex;
  ctx.lineWidth = 3;
  ctx.strokeRect(0, 0, 512, 512);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(36, 36); // 36m x 36m floor => exact 1.00m per tile repeat!
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

const floorTextures = {
  obsidian: makeGridTexture('#0d110e', 'rgba(184,220,86,0.14)', 'rgba(184,220,86,0.28)'),
  golden:   makeGridTexture('#2a2f2b', 'rgba(255,255,255,0.11)', 'rgba(184,220,86,0.26)'),
  gallery:  makeGridTexture('#b8bcb5', 'rgba(30,36,32,0.13)', 'rgba(30,36,32,0.26)'),
};

const floorMat = new THREE.MeshStandardMaterial({
  map: floorTextures.golden,
  roughness: 0.42,
  metalness: 0.14,
});
const floorMesh = new THREE.Mesh(new THREE.PlaneGeometry(36, 36), floorMat);
floorMesh.rotation.x = -Math.PI / 2;
floorMesh.receiveShadow = true;

// Ground world container (rotates cleanly during treadmill preview turns!)
const worldGroup = new THREE.Group();
scene.add(worldGroup);

// Studio Grid sub-world (shown in 'studio' mode)
const studioGroup = new THREE.Group();
studioGroup.add(floorMesh);
studioGroup.visible = false;
worldGroup.add(studioGroup);

// AnyScene Solarpunk Conservatory sub-world (loaded from courtyard_env_web.glb, default ON!)
const conservatoryGroup = new THREE.Group();
worldGroup.add(conservatoryGroup);

// Atmospheric Rayleigh + Mie Sky Dome with Drifting Sunlit Cumulus Clouds & Live Sun Disc!
const skyUniforms = {
  uTopColor: { value: new THREE.Color(0x1f5b8f) },
  uMidColor: { value: new THREE.Color(0x5b94b8) },
  uHorizonColor: { value: new THREE.Color(0xf6c788) },
  uGroundColor: { value: new THREE.Color(0x2c3627) },
  uSunDir: { value: new THREE.Vector3(0.72, 0.40, 0.56).normalize() },
  uSunColor: { value: new THREE.Color(0xfff1cc) },
  uCloudColor: { value: new THREE.Color(0xffe8c7) },
  uCloudShadow: { value: new THREE.Color(0x6d8299) },
  uCloudAmt: { value: 0.52 },
  uNightAmt: { value: 0.0 },
  uTime: { value: 0.0 },
};
const skyMat = new THREE.ShaderMaterial({
  uniforms: skyUniforms,
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  vertexShader: `
    varying vec3 vDir;
    void main() {
      vDir = normalize(position);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform vec3 uTopColor;
    uniform vec3 uMidColor;
    uniform vec3 uHorizonColor;
    uniform vec3 uGroundColor;
    uniform vec3 uSunDir;
    uniform vec3 uSunColor;
    uniform vec3 uCloudColor;
    uniform vec3 uCloudShadow;
    uniform float uCloudAmt;
    uniform float uNightAmt;
    uniform float uTime;
    varying vec3 vDir;

    float hash21(vec2 p) {
      p = fract(p * vec2(123.34, 456.21));
      p += dot(p, p + 45.32);
      return fract(p.x * p.y);
    }
    float vnoise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      return mix(
        mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x),
        mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x),
        f.y
      );
    }
    float fbm(vec2 p) {
      float v = 0.0, a = 0.5;
      mat2 rot = mat2(0.80, -0.60, 0.60, 0.80);
      for (int i = 0; i < 4; i++) {
        v += a * vnoise(p);
        p = rot * p * 2.04 + vec2(17.1, 31.7);
        a *= 0.5;
      }
      return v;
    }

    void main() {
      vec3 d = normalize(vDir);
      vec3 sDir = normalize(uSunDir);
      float h = d.y;

      // 3-stop physical Rayleigh sky gradient (rich cerulean zenith -> seamless golden horizon haze)
      vec3 sky;
      if (h >= 0.0) {
        float t1 = smoothstep(0.0, 0.24, h);
        float t2 = smoothstep(0.18, 0.82, h);
        sky = mix(uHorizonColor, uMidColor, t1);
        sky = mix(sky, uTopColor, t2);
      } else {
        sky = mix(uHorizonColor, uGroundColor, smoothstep(0.02, 0.34, -h));
      }

      // Warm Mie atmospheric horizon scatter toward the sun
      float sunCos = max(dot(d, sDir), 0.0);
      float horizBand = exp(-abs(h) * 6.5);
      sky += uSunColor * (pow(sunCos, 6.0) * 0.24 * horizBand + pow(sunCos, 28.0) * 0.26 + pow(sunCos, 380.0) * 1.45);

      // Drifting sunlit cumulus cloud deck on the upper dome
      if (h > 0.025 && uCloudAmt > 0.01) {
        vec2 cuv = d.xz / (h + 0.20) * 1.15 + vec2(uTime * 0.008, uTime * 0.004);
        float c1 = fbm(cuv);
        float c2 = fbm(cuv * 2.3 - vec2(uTime * 0.006, -uTime * 0.003));
        float density = smoothstep(0.47, 0.78, c1 * 0.72 + c2 * 0.28) * smoothstep(0.025, 0.18, h) * uCloudAmt;
        // Directional silver/gold rim-lighting on clouds facing the sun!
        float lit = clamp(0.32 + 0.68 * pow(sunCos, 2.2) + 0.30 * c2, 0.0, 1.0);
        vec3 cloudCol = mix(uCloudShadow, uCloudColor, lit) + uSunColor * pow(sunCos, 10.0) * 0.35;
        sky = mix(sky, cloudCol, density * 0.78);
      }

      // Subtle crisp starfield in Obsidian night mode
      if (uNightAmt > 0.05 && h > 0.05) {
        vec2 suv = floor(d.xz / (h + 0.15) * 140.0);
        float st = step(0.9965, hash21(suv)) * smoothstep(0.05, 0.35, h) * uNightAmt;
        sky += vec3(0.85, 0.92, 1.0) * st * 0.9;
      }

      gl_FragColor = vec4(sky, 1.0);
    }
  `,
});
const skyDome = new THREE.Mesh(new THREE.SphereGeometry(98, 32, 20), skyMat);
conservatoryGroup.add(skyDome);

// Offscreen Outdoor IBL Cube-Probe Builder (replaces milky white studio RoomEnvironment in Conservatory!)
const iblScene = new THREE.Scene();
const iblSkyDome = new THREE.Mesh(new THREE.SphereGeometry(20, 24, 14), skyMat);
iblScene.add(iblSkyDome);
const iblSunGlow = new THREE.Mesh(
  new THREE.SphereGeometry(2.2, 12, 8),
  new THREE.MeshBasicMaterial({ color: 0xffefc8 })
);
iblScene.add(iblSunGlow);

function rebuildOutdoorIBL() {
  if (state.world !== 'conservatory') {
    scene.environment = studioEnvTex;
    return;
  }
  iblSunGlow.position.copy(skyUniforms.uSunDir.value).multiplyScalar(14.0);
  iblSunGlow.material.color.copy(skyUniforms.uSunColor.value).multiplyScalar(state.env === 'obsidian' ? 0.8 : 2.6);
  const nextTex = pmrem.fromScene(iblScene, 0.025).texture;
  if (outdoorEnvTex) outdoorEnvTex.dispose();
  outdoorEnvTex = nextTex;
  scene.environment = outdoorEnvTex;
}

// Live Conservatory Breeze & Animated Mirror Rainwater Shader uniforms
const envAnimUniforms = {
  uTime: { value: 0.0 },
};

const waterUniforms = {
  uTime: envAnimUniforms.uTime,
  uSunDir: skyUniforms.uSunDir,
  uSunColor: skyUniforms.uSunColor,
  uSkyTop: skyUniforms.uTopColor,
  uSkyHorizon: skyUniforms.uHorizonColor,
};
const mirrorWaterMat = new THREE.ShaderMaterial({
  uniforms: waterUniforms,
  transparent: true,
  vertexShader: `
    varying vec3 vWorldPos;
    void main() {
      vec4 wp = modelMatrix * vec4(position, 1.0);
      vWorldPos = wp.xyz;
      gl_Position = projectionMatrix * viewMatrix * wp;
    }
  `,
  fragmentShader: `
    uniform float uTime;
    uniform vec3 uSunDir;
    uniform vec3 uSunColor;
    uniform vec3 uSkyTop;
    uniform vec3 uSkyHorizon;
    varying vec3 vWorldPos;

    void main() {
      vec2 p = vWorldPos.xz;
      // Gentle multi-directional concentric + breeze capillary water ripples
      float t = uTime * 1.15;
      float w1 = sin(p.x * 9.5 + t * 1.4) * cos(p.y * 8.2 - t * 1.1);
      float w2 = sin((p.x * 14.0 - p.y * 12.0) + t * 1.9) * 0.5;
      float w3 = cos(length(p - vec2(0.0, 8.1)) * 18.0 - t * 2.8) * 0.45;
      vec3 N = normalize(vec3((w1 + w2) * 0.018, 1.0, (w2 + w3) * 0.018));

      vec3 V = normalize(cameraPosition - vWorldPos);
      vec3 R = reflect(-V, N);
      float fres = 0.06 + 0.94 * pow(1.0 - max(dot(N, V), 0.0), 4.2);

      // Reflected sky gradient + golden sun specular glint
      vec3 reflSky = mix(uSkyHorizon, uSkyTop, clamp(pow(max(R.y, 0.0), 0.45), 0.0, 1.0));
      vec3 sDir = normalize(uSunDir);
      float spec = pow(max(dot(R, sDir), 0.0), 220.0) * 1.85 + pow(max(dot(R, sDir), 0.0), 28.0) * 0.25;
      // Deep architectural emerald-slate water absorption
      vec3 deepCol = vec3(0.025, 0.058, 0.052);
      vec3 col = mix(deepCol, reflSky, clamp(fres * 1.08, 0.14, 0.92)) + uSunColor * spec;
      float alpha = clamp(0.76 + fres * 0.22, 0.76, 0.97);
      gl_FragColor = vec4(col, alpha);
    }
  `,
});

function applyMaxAnisotropy(mat) {
  if (!mat) return;
  for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap']) {
    if (mat[k]) {
      mat[k].anisotropy = maxAniso;
      mat[k].needsUpdate = true;
    }
  }
}

function attachFoliageWind(mat, amp = 0.032, isPlanterFoliage = false) {
  if (!mat || mat.userData._windAttached) return;
  mat.userData._windAttached = true;
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uWindTime = envAnimUniforms.uTime;
    shader.uniforms.uWindAmp = { value: amp };
    shader.uniforms.uLeafSunDir = skyUniforms.uSunDir;
    shader.uniforms.uLeafNight = skyUniforms.uNightAmt;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `#include <common>\nuniform float uWindTime;\nuniform float uWindAmp;`)
      .replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
        float wMask = uv.y * uv.y;
        float wPhase = position.x * 1.7 + position.z * 1.3 + uWindTime * 1.65;
        transformed.x += sin(wPhase) * uWindAmp * wMask;
        transformed.z += cos(wPhase * 0.85 + 0.7) * uWindAmp * 0.75 * wMask;`
      );
    if (isPlanterFoliage) {
      // Physically-inspired sunlit botanical subsurface translucency (prevents dark silhouette leaves!)
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', `#include <common>\nuniform vec3 uLeafSunDir;\nuniform float uLeafNight;`)
        .replace(
          '#include <dithering_fragment>',
          `float dayFac = 1.0 - uLeafNight * 0.85;
          vec3 sssTint = diffuseColor.rgb * vec3(1.15, 1.45, 0.55) * (0.42 + 0.45 * max(uLeafSunDir.y, 0.1)) * dayFac;
          gl_FragColor.rgb += sssTint * 0.36;
          #include <dithering_fragment>`
        );
    }
  };
}

// Interactive mist particle burst & blooming station visual state
const stationVisuals = []; // { data, bloomed, bloomProg, beaconRing, blossoms[] }
const mistParticles = [];
let envMeta = null;

// Sparkling water-mist burst emitter (triggered when pressing [E] at a planter bed!)
const mistGeo = new THREE.BufferGeometry();
const MIST_N = 64;
const mistPos = new Float32Array(MIST_N * 3);
const mistVel = [];
let mistLife = 0;
for (let i = 0; i < MIST_N; i++) {
  mistPos[i * 3 + 1] = -99;
  mistVel.push(new THREE.Vector3());
}
mistGeo.setAttribute('position', new THREE.BufferAttribute(mistPos, 3));
const mistMat = new THREE.PointsMaterial({
  color: 0xc9f7ff, size: 0.048, transparent: true, opacity: 0.0, depthWrite: false,
});
const mistPoints = new THREE.Points(mistGeo, mistMat);
scene.add(mistPoints);

function triggerMistBurst(origin) {
  mistLife = 1.6;
  mistMat.opacity = 0.85;
  for (let i = 0; i < MIST_N; i++) {
    mistPos[i * 3] = origin.x + (Math.random() - 0.5) * 0.25;
    mistPos[i * 3 + 1] = origin.y + 0.55 + Math.random() * 0.25;
    mistPos[i * 3 + 2] = origin.z + (Math.random() - 0.5) * 0.25;
    const a = Math.random() * Math.PI * 2;
    const spd = 0.45 + Math.random() * 0.95;
    mistVel[i].set(Math.cos(a) * spd, 0.55 + Math.random() * 0.85, Math.sin(a) * spd);
  }
  mistGeo.attributes.position.needsUpdate = true;
}

function buildStationDecorations(meta) {
  const beaconGeo = new THREE.RingGeometry(0.24, 0.31, 32);
  const flowerGeo = new THREE.OctahedronGeometry(0.11, 1);
  for (const st of meta.stations || []) {
    const bMat = new THREE.MeshBasicMaterial({
      color: 0xf2a83b, transparent: true, opacity: 0.72, side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(beaconGeo, bMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(st.approach[0], 0.014, st.approach[2]);
    conservatoryGroup.add(ring);

    // 5 luminous solarpunk blossom buds hidden inside each planter (bloom smoothly when misted!)
    const blossoms = [];
    for (let k = 0; k < 5; k++) {
      const a = (k / 5) * Math.PI * 2 + 0.4;
      const r = k === 0 ? 0.08 : 0.48;
      const fm = new THREE.MeshStandardMaterial({
        color: 0xf6ff8c, emissive: 0xb8f242, emissiveIntensity: 1.35, roughness: 0.25,
      });
      const fl = new THREE.Mesh(flowerGeo, fm);
      fl.position.set(st.center[0] + Math.cos(a) * r, 0.95 + (k === 0 ? 0.28 : 0.12), st.center[2] + Math.sin(a) * r);
      fl.scale.setScalar(0.001);
      conservatoryGroup.add(fl);
      blossoms.push(fl);
    }
    stationVisuals.push({ data: st, bloomed: false, bloomProg: 0, beaconRing: ring, beaconMat: bMat, blossoms });
  }
}

function resolveEnvCollisions(pos) {
  if (state.world !== 'conservatory' || !envMeta) {
    pos.x = THREE.MathUtils.clamp(pos.x, -10, 10);
    pos.z = THREE.MathUtils.clamp(pos.z, -10, 10);
    return;
  }
  const R = 0.56; // robot horizontal clearance radius
  const b = envMeta.bounds;
  pos.x = THREE.MathUtils.clamp(pos.x, b.minX + R, b.maxX - R);
  pos.z = THREE.MathUtils.clamp(pos.z, b.minZ + R, b.maxZ - R);

  for (const col of envMeta.colliders || []) {
    if (col.type === 'circle') {
      const dx = pos.x - col.x;
      const dz = pos.z - col.z;
      const minD = col.r + R;
      const d2 = dx * dx + dz * dz;
      if (d2 < minD * minD) {
        const d = Math.sqrt(d2) || 0.001;
        pos.x = col.x + (dx / d) * minD;
        pos.z = col.z + (dz / d) * minD;
      }
    } else if (col.type === 'aabb') {
      const cx = THREE.MathUtils.clamp(pos.x, col.minX, col.maxX);
      const cz = THREE.MathUtils.clamp(pos.z, col.minZ, col.maxZ);
      const dx = pos.x - cx;
      const dz = pos.z - cz;
      const d2 = dx * dx + dz * dz;
      if (d2 < R * R) {
        if (d2 > 1e-6) {
          const d = Math.sqrt(d2);
          pos.x = cx + (dx / d) * R;
          pos.z = cz + (dz / d) * R;
        } else {
          // Inside AABB fallback: push out along nearest edge
          const dl = Math.abs(pos.x - col.minX), dr = Math.abs(col.maxX - pos.x);
          const dt = Math.abs(pos.z - col.minZ), db = Math.abs(col.maxZ - pos.z);
          const m = Math.min(dl, dr, dt, db);
          if (m === dl) pos.x = col.minX - R;
          else if (m === dr) pos.x = col.maxX + R;
          else if (m === dt) pos.z = col.minZ - R;
          else pos.z = col.maxZ + R;
        }
      }
    }
  }
}

// Subtle sunlit floating pollen/dust motes
const moteCount = 90;
const moteGeo = new THREE.BufferGeometry();
const motePos = new Float32Array(moteCount * 3);
const motePhase = new Float32Array(moteCount);
for (let i = 0; i < moteCount; i++) {
  const r = 1.1 + Math.random() * 4.5;
  const a = Math.random() * Math.PI * 2;
  motePos[i * 3] = Math.cos(a) * r;
  motePos[i * 3 + 1] = 0.25 + Math.random() * 2.1;
  motePos[i * 3 + 2] = Math.sin(a) * r;
  motePhase[i] = Math.random() * Math.PI * 2;
}
moteGeo.setAttribute('position', new THREE.BufferAttribute(motePos, 3));
const moteMat = new THREE.PointsMaterial({
  color: 0xeaf5a6,
  size: 0.022,
  transparent: true,
  opacity: 0.55,
  depthWrite: false,
});
const motes = new THREE.Points(moteGeo, moteMat);
scene.add(motes);

// ============================================================================
// 3. STATE & ROBOT RUNTIME
// ============================================================================
const state = {
  world: 'conservatory', // 'conservatory' (AnyScene rooftop world) | 'studio' (precision scrolling grid)
  env: 'golden',
  action: 'Idle_Scan',
  playing: true,
  speed: 1.0,
  sunAzDeg: 38,
  sunElDeg: 24,
  sunTrack: true,
  explode: 0.0,
  showSkeleton: false,
  wireframe: false,
  growLightsOn: true,
  driveMode: false,
  soundOn: false,
  uiHidden: false,
  // Drive kinematics
  pos: new THREE.Vector3(0, 0, 0),
  yaw: 0,
  driveSpeed: 0,
  driveOverrideAction: null, // 'Inspect_Plant' or 'Sun_Bloom_Stretch'
  camLerp: null,
};

const keys = new Set();
const robotRoot = new THREE.Group();
scene.add(robotRoot);

let mixer = null;
let actions = {};
let activeClipName = null;
let partMeta = {};
let partMeshes = [];
let explodeData = [];
let skeletonHelper = null;
let bonesByName = {};
let restQuats = {};
let boneLocalAxes = {}; // { boneName: { fwd, up, left } } in bone local space!
let preLayerQuats = {}; // clean post-mixer quaternions restored before next mixer.update()
let smoothCanopyYaw = 0;
let smoothCanopyPitch = 0;
let smoothSteer = 0;    // smoothed steering signal [-1..+1] (+1 = turning left)
const tmpQ = new THREE.Quaternion();
const tmpQ2 = new THREE.Quaternion();
const AXIS_Y = new THREE.Vector3(0, 1, 0);
const AXIS_Z = new THREE.Vector3(0, 0, 1);
let growMaterials = [];
let selectedMesh = null;
let selectedOrigEmissive = null;

// Live hydraulic oscilloscope history
const scopeCanvas = document.getElementById('hyd-scope');
const scopeCtx = scopeCanvas.getContext('2d');
const scopeHist = new Array(130).fill(306.6);
const tmpV1 = new THREE.Vector3();
const tmpV2 = new THREE.Vector3();
const tmpV3 = new THREE.Vector3();

// ============================================================================
// 4. PROCEDURAL WEBAUDIO ENGINE (OPTIONAL SERVO HUM + SYNCED FOOTSTEPS)
// ============================================================================
let audioCtx = null;
let servoOsc = null;
let servoGain = null;
let lastStepIndex = -1;

function initAudio() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  servoOsc = audioCtx.createOscillator();
  servoOsc.type = 'triangle';
  servoOsc.frequency.value = 140;
  const filter = audioCtx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.value = 420;
  servoGain = audioCtx.createGain();
  servoGain.gain.value = 0.0;
  servoOsc.connect(filter).connect(servoGain).connect(audioCtx.destination);
  servoOsc.start();
}

function playFootstepTick(loud = 0.08) {
  if (!state.soundOn || !audioCtx || audioCtx.state !== 'running') return;
  const now = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const g = audioCtx.createGain();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(125, now);
  osc.frequency.exponentialRampToValueAtTime(48, now + 0.055);
  g.gain.setValueAtTime(loud, now);
  g.gain.exponentialRampToValueAtTime(0.0008, now + 0.065);
  osc.connect(g).connect(audioCtx.destination);
  osc.start(now);
  osc.stop(now + 0.07);
}

// ============================================================================
// 5. LOAD DRACO GLB + METADATA
// ============================================================================
const loaderEl = document.getElementById('loader');
const loaderBar = document.getElementById('loader-bar');
const loaderText = document.getElementById('loader-text');

async function loadAssets() {
  try {
    const infoRes = await fetch('./assets/flora_quad_info.json');
    if (infoRes.ok) {
      const info = await infoRes.json();
      for (const p of info.part_table || []) {
        partMeta[p.name] = p;
      }
    }
  } catch (e) {
    console.warn('Metadata JSON optional load skipped:', e);
  }

  try {
    const metaRes = await fetch('./assets/env_meta.json');
    if (metaRes.ok) {
      envMeta = await metaRes.json();
      buildStationDecorations(envMeta);
    }
  } catch (e) {
    console.warn('Env meta JSON optional load skipped:', e);
  }

  const draco = new DRACOLoader();
  draco.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/');
  const gltfLoader = new GLTFLoader();
  gltfLoader.setDRACOLoader(draco);

  // Load AnyScene Pass 2 Solarpunk Conservatory environment GLB (Draco+WebP + Cycles Contact AO!)
  gltfLoader.load(
    './assets/courtyard_env_web.glb?v=2',
    (envGltf) => {
      envGltf.scene.traverse((o) => {
        if (o.isMesh) {
          const nm = o.name || '';
          // Upgrade rainwater basin plane to live animated Fresnel ripple mirror shader!
          if (nm.includes('Water_Surface')) {
            o.material = mirrorWaterMat;
            o.receiveShadow = false;
            o.castShadow = false;
            return;
          }
          o.receiveShadow = !nm.includes('Solarpunk_Skyline') && !nm.includes('Treeline_Canopy');
          o.castShadow = !(
            nm.includes('Terrace_Floor') ||
            nm.includes('Terrace_Trim') ||
            nm.includes('Balustrade_Glass') ||
            nm.includes('Pergola_Skylights') ||
            nm.includes('Solarpunk_Skyline') ||
            nm.includes('Treeline_Canopy')
          );
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          for (const m of mats) {
            if (!m) continue;
            applyMaxAnisotropy(m);
            const mn = m.name || '';
            // Amplify Cycles baked Contact AO on the Roman travertine floor for rich grounding!
            if (mn.includes('E_travertine') && m.aoMap) {
              m.aoMapIntensity = 1.28;
              m.envMapIntensity = 0.65;
            }
            // Crisp alpha-cutout shadows + gentle live breeze sway + sunlit leaf translucency!
            if (mn.includes('E_monstera') || mn.includes('E_fern') || mn.includes('E_tree_canopy')) {
              const isPlanter = mn.includes('E_monstera') || mn.includes('E_fern');
              m.alphaTest = 0.45;
              m.transparent = false;
              m.depthWrite = true;
              m.side = THREE.DoubleSide;
              if (isPlanter) {
                m.color.setRGB(1.65, 1.80, 1.30);
                m.envMapIntensity = 0.95;
              }
              attachFoliageWind(m, mn.includes('E_fern') ? 0.042 : (mn.includes('E_monstera') ? 0.026 : 0.055), isPlanter);
            }
            // Crisp rich reflection on dark anodized steel, brushed brass & glass skylights
            if (mn.includes('E_steel_dark') || mn.includes('E_brass')) {
              m.envMapIntensity = 1.25;
            }
            if (mn.includes('E_skylight_glass') || mn.includes('E_glass_rail')) {
              m.depthWrite = false;
              m.envMapIntensity = 1.35;
            }
            if (mn.includes('E_facade')) {
              m.envMapIntensity = 0.95;
            }
          }
        }
      });
      conservatoryGroup.add(envGltf.scene);
    },
    undefined,
    (err) => console.warn('Environment GLB load warning:', err)
  );

  gltfLoader.load(
    './assets/flora_quad_web.glb',
    (gltf) => {
      const model = gltf.scene;
      robotRoot.add(model);

      // Index bones, meshes, shadows & emissive materials (group multi-material primitives by Blender part!)
      const bodyCenter = new THREE.Vector3(0, 0.54, 0);
      const partGroups = new Map();
      // Capture exact world-to-local axis bases in rest pose (zero axis-sign guesswork!)
      robotRoot.updateMatrixWorld(true);
      const rFwd = new THREE.Vector3(1, 0, 0);
      const rUp  = new THREE.Vector3(0, 1, 0);
      const rLeft = new THREE.Vector3(0, 0, -1);
      model.traverse((obj) => {
        if (obj.isBone) {
          bonesByName[obj.name] = obj;
          restQuats[obj.name] = obj.quaternion.clone();
          const invWorldQ = new THREE.Quaternion();
          obj.getWorldQuaternion(invWorldQ).invert();
          boneLocalAxes[obj.name] = {
            fwd:  rFwd.clone().applyQuaternion(invWorldQ).normalize(),
            up:   rUp.clone().applyQuaternion(invWorldQ).normalize(),
            left: rLeft.clone().applyQuaternion(invWorldQ).normalize(),
          };
        }
        if (obj.isMesh) {
          obj.castShadow = true;
          obj.receiveShadow = true;
          partMeshes.push(obj);

          // Resolve canonical Blender part name (P_*) across multi-material primitives
          const canonical = (obj.parent && obj.parent.name && obj.parent.name.startsWith('P_'))
            ? obj.parent.name
            : obj.name.replace(/_\d+$/, '');
          obj.userData.partName = canonical;
          if (!partGroups.has(canonical)) partGroups.set(canonical, []);
          partGroups.get(canonical).push(obj);

          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          for (const m of mats) {
            if (!m) continue;
            applyMaxAnisotropy(m);
            if (m.name && m.name.includes('M_glow_')) {
              // Calibrate HDR emissive strength for Three.js ACESFilmic + Bloom (vivid color, no white blowout)
              const calibrated = Math.min(m.emissiveIntensity || 1.0, 1.48);
              m.emissiveIntensity = calibrated;
              growMaterials.push({ mat: m, baseIntensity: calibrated });
            }
          }
        }
      });

      // Compute one unified radial explode vector per physical Blender part (keeps bolts & seams attached!)
      for (const [partName, meshes] of partGroups.entries()) {
        const box = new THREE.Box3();
        for (const m of meshes) {
          m.geometry.computeBoundingBox();
          box.union(m.geometry.boundingBox);
        }
        const ctr = new THREE.Vector3();
        box.getCenter(ctr);
        const dir = ctr.clone().sub(bodyCenter);
        if (dir.lengthSq() < 0.001) dir.set(0, 1, 0);
        dir.normalize();
        const dist = 0.22 + Math.min(0.30, ctr.distanceTo(bodyCenter) * 0.48);
        for (const m of meshes) {
          explodeData.push({ mesh: m, basePos: m.position.clone(), dir, dist });
        }
      }

      // Skeleton X-Ray helper
      skeletonHelper = new THREE.SkeletonHelper(model);
      skeletonHelper.visible = false;
      scene.add(skeletonHelper);

      // Setup AnimationMixer & all 5 verified actions
      mixer = new THREE.AnimationMixer(model);
      for (const clip of gltf.animations) {
        actions[clip.name] = mixer.clipAction(clip);
      }
      // Step 1 initial tick immediately so telemetry & pose are live even on frame 0
      switchAction(state.action, 0.0);
      mixer.update(0.016);

      // Apply initial world, environment & sun
      applyWorld(state.world);
      updateSunPosition();

      // Expose read-only diagnostics handle
      window.__FLORA__ = {
        get animations() { return Object.keys(actions); },
        get parts() { return partGroups.size; },
        get bones() { return Object.keys(bonesByName).length; },
        get activeAction() { return activeClipName; },
        capture() {
          controls.update();
          composer.render();
          return renderer.domElement.toDataURL('image/jpeg', 0.88);
        },
        snapCam(presetName) {
          const p = CAM_PRESETS[presetName];
          if (!p) return false;
          state.camLerp = null;
          const rot = new THREE.Euler(0, state.yaw, 0);
          camera.position.copy(new THREE.Vector3(...p.pos).applyEuler(rot).add(state.pos));
          controls.target.copy(new THREE.Vector3(...p.tgt).applyEuler(rot).add(state.pos));
          controls.update();
          return true;
        },
        stepDemo(dtSec) {
          if (mixer) {
            mixer.update(dtSec);
            robotRoot.updateMatrixWorld(true);
            if (bonesByName['B_FL_hyd_cyl'] && bonesByName['B_FL_hyd_rod']) {
              bonesByName['B_FL_hyd_cyl'].getWorldPosition(tmpV1);
              bonesByName['B_FL_hyd_rod'].getWorldPosition(tmpV2);
              return Number((tmpV1.distanceTo(tmpV2) * 1000.0).toFixed(2));
            }
          }
          return null;
        },
      };

      loaderBar.style.width = '100%';
      loaderText.textContent = `Ready · ${partGroups.size} parts · ${Object.keys(bonesByName).length} bones`;
      setTimeout(() => loaderEl.classList.add('fade-out'), 260);
    },
    (xhr) => {
      if (xhr.total) {
        const pct = Math.min(98, Math.round((xhr.loaded / xhr.total) * 100));
        loaderBar.style.width = `${pct}%`;
        loaderText.textContent = `Loading Draco GLB... ${pct}%`;
      }
    },
    (err) => {
      loaderText.textContent = `Load error: ${err.message || err}`;
      console.error('GLB load failed:', err);
    }
  );
}

// ============================================================================
// 6. ACTIONS, LIGHTING, CAMERA PRESETS & SUN-TRACKING
// ============================================================================
function switchAction(name, fadeSec = 0.28) {
  if (!actions[name] || activeClipName === name) return;
  const next = actions[name];
  const prev = activeClipName ? actions[activeClipName] : null;
  next.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).play();
  if (prev && fadeSec > 0) {
    prev.crossFadeTo(next, fadeSec, false);
  } else if (prev) {
    prev.stop();
  }
  activeClipName = name;
  state.action = name;

  // Update UI pill & buttons
  document.querySelectorAll('.act-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.action === name);
  });
  const shortMap = {
    Idle_Scan: 'IDLE SCAN',
    Walk_Cycle: 'WALK FWD',
    Walk_Back: 'WALK BACK',
    Trot_Cycle: 'TROT',
    Turn_Left: 'TURN LEFT',
    Turn_Right: 'TURN RIGHT',
    Inspect_Plant: 'INSPECT',
    Sun_Bloom_Stretch: 'SUN SALUTE',
  };
  document.getElementById('active-mode-pill').textContent = shortMap[name] || name;
  const initVel = name === 'Walk_Cycle' ? WALK_VEL * state.speed
    : (name === 'Walk_Back' ? -BACK_VEL * state.speed
    : (name === 'Trot_Cycle' ? TROT_VEL * state.speed : 0));
  document.getElementById('vel-val').textContent = `${initVel.toFixed(3)} m/s`;
}

function applyWorld(worldName) {
  state.world = worldName;
  document.querySelectorAll('[data-world]').forEach((b) => {
    b.classList.toggle('active', b.dataset.world === worldName);
  });
  conservatoryGroup.visible = (worldName === 'conservatory');
  studioGroup.visible = (worldName === 'studio');
  if (worldName === 'conservatory') {
    worldGroup.rotation.y = 0;
  }
  const bc = document.getElementById('biome-counter');
  if (bc) bc.classList.toggle('hidden', worldName !== 'conservatory');
  if (worldName !== 'conservatory') {
    const pe = document.getElementById('station-prompt');
    if (pe) pe.classList.add('hidden');
  }
  applyEnvironment(state.env);
  updateSunPosition();
}

function applyEnvironment(envName) {
  state.env = envName;
  document.querySelectorAll('[data-env]').forEach((b) => {
    b.classList.toggle('active', b.dataset.env === envName);
  });
  floorMat.map = floorTextures[envName];
  floorMat.needsUpdate = true;
  const isCons = state.world === 'conservatory';

  if (envName === 'obsidian') {
    scene.background.setHex(0x070d12);
    scene.fog.color.setHex(0x0d171c);
    scene.fog.density = isCons ? 0.011 : 0.085;
    renderer.toneMappingExposure = isCons ? 0.96 : 0.94;
    scene.environmentIntensity = isCons ? 0.42 : 0.24;
    hemiLight.color.setHex(0x527fa6);
    hemiLight.groundColor.setHex(0x101815);
    hemiLight.intensity = isCons ? 0.26 : 0.20;
    sunLight.intensity = isCons ? 1.45 : 0.78;
    sunLight.color.setHex(0x9ec5f5);
    rimLight.intensity = isCons ? 0.55 : 1.15;
    rimLight.color.setHex(0xc8e8ff);
    skyUniforms.uTopColor.value.setHex(0x050b14);
    skyUniforms.uMidColor.value.setHex(0x0c1b29);
    skyUniforms.uHorizonColor.value.setHex(0x1b3336);
    skyUniforms.uGroundColor.value.setHex(0x070b0a);
    skyUniforms.uSunColor.value.setHex(0x96c2f0);
    skyUniforms.uCloudColor.value.setHex(0x284357);
    skyUniforms.uCloudShadow.value.setHex(0x0d1a24);
    skyUniforms.uCloudAmt.value = 0.35;
    skyUniforms.uNightAmt.value = 1.0;
    floorMat.roughness = 0.24;
    floorMat.metalness = 0.30;
    bloomPass.strength = 0.18;
    bloomPass.radius = 0.34;
    bloomPass.threshold = 1.05;
    moteMat.opacity = 0.58;
  } else if (envName === 'golden') {
    const bgHex = isCons ? 0xd9b88c : 0x1f2421;
    scene.background.setHex(bgHex);
    scene.fog.color.setHex(isCons ? 0xe6c79c : 0x1f2421);
    scene.fog.density = isCons ? 0.0046 : 0.048;
    renderer.toneMappingExposure = isCons ? 1.04 : 0.94;
    scene.environmentIntensity = isCons ? 0.52 : 0.62;
    hemiLight.color.setHex(0x9dc7e8);
    hemiLight.groundColor.setHex(0x3a3225);
    hemiLight.intensity = isCons ? 0.34 : 0.58;
    sunLight.intensity = isCons ? 3.85 : 1.85;
    sunLight.color.setHex(0xffd28f);
    rimLight.intensity = isCons ? 0.24 : 0.75;
    rimLight.color.setHex(0x8dbce6);
    skyUniforms.uTopColor.value.setHex(0x1a568a);
    skyUniforms.uMidColor.value.setHex(0x568fb5);
    skyUniforms.uHorizonColor.value.setHex(0xf5c484);
    skyUniforms.uGroundColor.value.setHex(0x2a3524);
    skyUniforms.uSunColor.value.setHex(0xfff0c2);
    skyUniforms.uCloudColor.value.setHex(0xffebd0);
    skyUniforms.uCloudShadow.value.setHex(0x697f96);
    skyUniforms.uCloudAmt.value = 0.55;
    skyUniforms.uNightAmt.value = 0.0;
    floorMat.roughness = 0.44;
    floorMat.metalness = 0.12;
    bloomPass.strength = 0.11;
    bloomPass.radius = 0.28;
    bloomPass.threshold = 1.18;
    moteMat.opacity = 0.45;
  } else {
    // Gallery crisp Mediterranean midday daylight
    const bgHex = isCons ? 0xb4d6eb : 0xd2d5cf;
    scene.background.setHex(bgHex);
    scene.fog.color.setHex(isCons ? 0xc6dfee : 0xd2d5cf);
    scene.fog.density = isCons ? 0.0040 : 0.042;
    renderer.toneMappingExposure = isCons ? 1.00 : 0.94;
    scene.environmentIntensity = isCons ? 0.58 : 0.85;
    hemiLight.color.setHex(0xbbe0ff);
    hemiLight.groundColor.setHex(0x46483e);
    hemiLight.intensity = isCons ? 0.44 : 0.95;
    sunLight.intensity = isCons ? 3.45 : 1.50;
    sunLight.color.setHex(0xfff6e3);
    rimLight.intensity = isCons ? 0.28 : 0.65;
    rimLight.color.setHex(0xd4ebff);
    skyUniforms.uTopColor.value.setHex(0x1b6cb0);
    skyUniforms.uMidColor.value.setHex(0x67a7d6);
    skyUniforms.uHorizonColor.value.setHex(0xd6eaf5);
    skyUniforms.uGroundColor.value.setHex(0x3a4734);
    skyUniforms.uSunColor.value.setHex(0xffffff);
    skyUniforms.uCloudColor.value.setHex(0xffffff);
    skyUniforms.uCloudShadow.value.setHex(0x88a4bd);
    skyUniforms.uCloudAmt.value = 0.48;
    skyUniforms.uNightAmt.value = 0.0;
    floorMat.roughness = 0.64;
    floorMat.metalness = 0.04;
    bloomPass.strength = 0.04;
    bloomPass.radius = 0.20;
    bloomPass.threshold = 1.38;
    moteMat.opacity = 0.12;
  }
  rebuildOutdoorIBL();
}

let _lastIblSunMs = 0;
function updateSunPosition(forceIbl = false) {
  const az = THREE.MathUtils.degToRad(state.sunAzDeg);
  const el = THREE.MathUtils.degToRad(state.sunElDeg);
  const dx = Math.cos(el) * Math.cos(az);
  const dy = Math.sin(el);
  const dz = Math.cos(el) * Math.sin(az);
  const r = state.world === 'conservatory' ? 16.0 : 6.0;
  sunLight.position.set(
    state.pos.x + r * dx,
    r * dy,
    state.pos.z + r * dz
  );
  sunLight.target.position.set(state.pos.x, 0.5, state.pos.z);
  sunLight.target.updateMatrixWorld();
  skyUniforms.uSunDir.value.set(dx, dy, dz).normalize();
  if (forceIbl && state.world === 'conservatory') {
    const now = performance.now();
    if (now - _lastIblSunMs > 180) {
      _lastIblSunMs = now;
      rebuildOutdoorIBL();
    }
  }
}

const CAM_PRESETS = {
  hero:       { pos: [2.45, 1.16,  2.35], tgt: [ 0.02, 0.56, 0.00] },
  world:      { pos: [4.25, 2.35,  5.35], tgt: [-0.35, 0.78, -0.45] },
  canopy:     { pos: [0.68, 1.16,  0.76], tgt: [-0.02, 0.84, 0.00] },
  hydraulics: { pos: [0.62, 0.34, -0.82], tgt: [ 0.18, 0.24, -0.16] },
  rear:       { pos: [-0.88, 0.44, -0.84], tgt: [-0.40, 0.34, -0.15] },
  side:       { pos: [0.00, 0.54,  2.55], tgt: [ 0.00, 0.50, 0.00] },
};

function jumpCamera(presetName) {
  const p = CAM_PRESETS[presetName];
  if (!p) return;
  document.querySelectorAll('[data-cam]').forEach((b) => {
    b.classList.toggle('active', b.dataset.cam === presetName);
  });
  // Rotate preset offset by robot's current drive yaw & position
  const rot = new THREE.Euler(0, state.yaw, 0);
  const targetPos = new THREE.Vector3(...p.pos).applyEuler(rot).add(state.pos);
  const targetLook = new THREE.Vector3(...p.tgt).applyEuler(rot).add(state.pos);
  state.camLerp = {
    t: 0,
    p0: camera.position.clone(),
    p1: targetPos,
    t0: controls.target.clone(),
    t1: targetLook,
  };
}

// ============================================================================
// 7. CLICK-TO-INSPECT PART RAYCASTER
// ============================================================================
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downPos = { x: 0, y: 0 };

function clearSelection() {
  if (selectedMesh && selectedOrigEmissive) {
    const mats = Array.isArray(selectedMesh.material) ? selectedMesh.material : [selectedMesh.material];
    mats.forEach((m, i) => {
      if (m && m.emissive && selectedOrigEmissive[i]) {
        m.emissive.copy(selectedOrigEmissive[i]);
      }
    });
  }
  selectedMesh = null;
  selectedOrigEmissive = null;
  document.getElementById('part-card').classList.add('hidden');
}

function selectMesh(mesh) {
  clearSelection();
  selectedMesh = mesh;
  const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  selectedOrigEmissive = mats.map((m) => (m && m.emissive ? m.emissive.clone() : null));
  mats.forEach((m) => {
    if (m && m.emissive && (!m.name || !m.name.includes('M_glow_'))) {
      m.emissive.setHex(0x475c18);
    }
  });
  const baseName = mesh.userData.partName || mesh.name.replace(/_\d+$/, '');
  const meta = partMeta[baseName] || partMeta[mesh.name];
  const tris = meta ? meta.tris : Math.round((mesh.geometry.index ? mesh.geometry.index.count : mesh.geometry.attributes.position.count) / 3);
  document.getElementById('part-name').textContent = baseName;
  document.getElementById('part-bone').textContent = meta ? meta.bone : 'B_torso';
  document.getElementById('part-tris').textContent = tris.toLocaleString();
  document.getElementById('part-role').textContent = inferRole(baseName);
  document.getElementById('part-card').classList.remove('hidden');
}

renderer.domElement.addEventListener('pointerdown', (e) => {
  downPos = { x: e.clientX, y: e.clientY };
});
renderer.domElement.addEventListener('pointerup', (e) => {
  if (state.uiHidden) return;
  if (Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y) > 5) return;
  pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(partMeshes, false);
  if (hits.length > 0) {
    selectMesh(hits[0].object);
  } else {
    clearSelection();
  }
});

// ============================================================================
// 8. UI EVENT WIRING & KEYBOARD DRIVE CONTROLS
// ============================================================================
document.querySelectorAll('[data-world]').forEach((btn) => {
  btn.addEventListener('click', () => applyWorld(btn.dataset.world));
});
document.querySelectorAll('[data-env]').forEach((btn) => {
  btn.addEventListener('click', () => applyEnvironment(btn.dataset.env));
});
document.querySelectorAll('[data-cam]').forEach((btn) => {
  btn.addEventListener('click', () => jumpCamera(btn.dataset.cam));
});
document.querySelectorAll('.act-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (state.driveMode) toggleDriveMode(false);
    switchAction(btn.dataset.action, 0.28);
  });
});

const btnPlay = document.getElementById('btn-play');
btnPlay.addEventListener('click', () => {
  state.playing = !state.playing;
  btnPlay.textContent = state.playing ? 'Pause' : 'Play';
  btnPlay.setAttribute('aria-pressed', String(state.playing));
});

const speedSlider = document.getElementById('speed-slider');
const speedVal = document.getElementById('speed-val');
speedSlider.addEventListener('input', () => {
  state.speed = parseFloat(speedSlider.value);
  speedVal.textContent = `${state.speed.toFixed(2)}×`;
});

const sunAz = document.getElementById('sun-az');
const sunEl = document.getElementById('sun-el');
sunAz.addEventListener('input', () => {
  state.sunAzDeg = parseFloat(sunAz.value);
  document.getElementById('sun-az-val').textContent = `${Math.round(state.sunAzDeg)}°`;
  updateSunPosition(true);
});
sunEl.addEventListener('input', () => {
  state.sunElDeg = parseFloat(sunEl.value);
  document.getElementById('sun-el-val').textContent = `${Math.round(state.sunElDeg)}°`;
  updateSunPosition(true);
});
document.getElementById('chk-suntrack').addEventListener('change', (e) => {
  state.sunTrack = e.target.checked;
});

const explodeSlider = document.getElementById('explode-slider');
explodeSlider.addEventListener('input', () => {
  state.explode = parseFloat(explodeSlider.value) / 100.0;
  document.getElementById('explode-val').textContent = `${Math.round(state.explode * 100)}%`;
});

const btnSkel = document.getElementById('btn-skeleton');
btnSkel.addEventListener('click', () => {
  state.showSkeleton = !state.showSkeleton;
  btnSkel.setAttribute('aria-pressed', String(state.showSkeleton));
  btnSkel.classList.toggle('active', state.showSkeleton);
  if (skeletonHelper) skeletonHelper.visible = state.showSkeleton;
});

const btnWire = document.getElementById('btn-wireframe');
btnWire.addEventListener('click', () => {
  state.wireframe = !state.wireframe;
  btnWire.setAttribute('aria-pressed', String(state.wireframe));
  btnWire.classList.toggle('active', state.wireframe);
  partMeshes.forEach((m) => {
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    mats.forEach((mt) => { if (mt) mt.wireframe = state.wireframe; });
  });
});

const btnGrow = document.getElementById('btn-growlight');
btnGrow.addEventListener('click', () => {
  state.growLightsOn = !state.growLightsOn;
  btnGrow.setAttribute('aria-pressed', String(state.growLightsOn));
  btnGrow.classList.toggle('active', state.growLightsOn);
  growLight.intensity = state.growLightsOn ? 0.85 : 0.0;
  growMaterials.forEach(({ mat, baseIntensity }) => {
    mat.emissiveIntensity = state.growLightsOn ? baseIntensity : 0.04;
  });
});

document.getElementById('btn-clear-part').addEventListener('click', clearSelection);

const btnSound = document.getElementById('btn-sound');
btnSound.addEventListener('click', () => {
  initAudio();
  if (audioCtx.state === 'suspended') audioCtx.resume();
  state.soundOn = !state.soundOn;
  btnSound.textContent = state.soundOn ? 'Audio: On' : 'Audio: Off';
  btnSound.setAttribute('aria-pressed', String(state.soundOn));
  if (!state.soundOn && servoGain) servoGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.05);
});

const btnDrive = document.getElementById('btn-drive');
const driveHint = document.getElementById('drive-hint');
const orbitHint = document.getElementById('orbit-hint');

function toggleDriveMode(force) {
  state.driveMode = typeof force === 'boolean' ? force : !state.driveMode;
  btnDrive.setAttribute('aria-pressed', String(state.driveMode));
  driveHint.classList.toggle('hidden', !state.driveMode);
  orbitHint.classList.toggle('hidden', state.driveMode);
  if (state.driveMode) {
    state.playing = true;
    btnPlay.textContent = 'Pause';
    state.driveOverrideAction = null;
    worldGroup.rotation.y = 0;
    floorMat.map.offset.set(0, 0);
    switchAction('Idle_Scan', 0.25);
  } else {
    state.pos.set(0, 0, 0);
    state.yaw = 0;
    robotRoot.position.set(0, 0, 0);
    robotRoot.rotation.set(0, 0, 0);
    worldGroup.rotation.y = 0;
    controls.target.set(0.02, 0.50, 0);
    jumpCamera('hero');
  }
}
btnDrive.addEventListener('click', () => toggleDriveMode());

const btnTogglePanel = document.getElementById('btn-toggle-panel');
const drawerEl = document.getElementById('console-drawer');
btnTogglePanel.addEventListener('click', () => {
  const collapsed = drawerEl.classList.toggle('collapsed');
  btnTogglePanel.setAttribute('aria-expanded', String(!collapsed));
});

const btnHideUi = document.getElementById('btn-hide-ui');
const btnShowUi = document.getElementById('btn-show-ui');

function toggleUiHidden(force) {
  state.uiHidden = typeof force === 'boolean' ? force : !state.uiHidden;
  document.body.classList.toggle('ui-hidden', state.uiHidden);
  if (btnHideUi) btnHideUi.setAttribute('aria-pressed', String(state.uiHidden));
  if (btnShowUi) {
    btnShowUi.classList.toggle('hidden', !state.uiHidden);
    btnShowUi.setAttribute('aria-pressed', String(state.uiHidden));
  }
  if (state.uiHidden && selectedMesh) clearSelection();
}
if (btnHideUi) btnHideUi.addEventListener('click', () => toggleUiHidden(true));
if (btnShowUi) btnShowUi.addEventListener('click', () => toggleUiHidden(false));

window.addEventListener('keydown', (e) => {
  const tag = e.target?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;
  const k = e.key.toLowerCase();
  if (k === 'h' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    if (!e.repeat) toggleUiHidden();
    return;
  }
  keys.add(k);
  if (k === 'escape' && state.driveMode) toggleDriveMode(false);
  // Seamless roaming: pressing WASD / Arrow keys immediately engages Drive Mode!
  if (!state.driveMode && ['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(k)) {
    toggleDriveMode(true);
  }
  if (state.driveMode && (k === 'e' || k === ' ')) {
    e.preventDefault();
    state.driveOverrideAction = k === 'e' ? 'Inspect_Plant' : 'Sun_Bloom_Stretch';
    switchAction(state.driveOverrideAction, 0.25);
    // If pressing [E] near an interactive conservatory planter bed, mist & bloom it!
    if (k === 'e' && state.world === 'conservatory') {
      for (const sv of stationVisuals) {
        const d = Math.hypot(state.pos.x - sv.data.center[0], state.pos.z - sv.data.center[2]);
        if (d < sv.data.radius + 1.15) {
          triggerMistBurst(new THREE.Vector3(sv.data.center[0], 0.55, sv.data.center[2]));
          if (!sv.bloomed) {
            sv.bloomed = true;
            sv.beaconMat.color.setHex(0xb8dc56);
            sv.beaconMat.opacity = 0.28;
            const done = stationVisuals.filter(x => x.bloomed).length;
            const bc = document.getElementById('biome-counter');
            if (bc) bc.textContent = `BIOME ${done}/${stationVisuals.length}`;
          }
        }
      }
    }
  }
});
window.addEventListener('keyup', (e) => {
  const k = e.key.toLowerCase();
  keys.delete(k);
  if (state.driveMode && (k === 'e' || k === ' ')) {
    state.driveOverrideAction = null;
  }
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});

// ============================================================================
// 9. LIVE HYDRAULIC OSCILLOSCOPE RENDERER
// ============================================================================
const hydDistEl = document.getElementById('hyd-dist-val');
const velEl = document.getElementById('vel-val');

function drawHydraulicScope(distMm) {
  scopeHist.push(distMm);
  if (scopeHist.length > 130) scopeHist.shift();

  const w = scopeCanvas.width, h = scopeCanvas.height;
  scopeCtx.clearRect(0, 0, w, h);

  // Subtle horizontal calibration grid (290mm..330mm)
  scopeCtx.strokeStyle = 'rgba(255,255,255,0.08)';
  scopeCtx.lineWidth = 1;
  for (let i = 1; i <= 3; i++) {
    const y = (h * i) / 4;
    scopeCtx.beginPath(); scopeCtx.moveTo(0, y); scopeCtx.lineTo(w, y); scopeCtx.stroke();
  }

  // Filled waveform gradient
  scopeCtx.beginPath();
  for (let i = 0; i < scopeHist.length; i++) {
    const x = (i / (scopeHist.length - 1)) * w;
    const norm = THREE.MathUtils.clamp((scopeHist[i] - 285) / 48, 0, 1);
    const y = h - 6 - norm * (h - 12);
    if (i === 0) scopeCtx.moveTo(x, y);
    else scopeCtx.lineTo(x, y);
  }
  scopeCtx.strokeStyle = '#f2a83b';
  scopeCtx.lineWidth = 2;
  scopeCtx.stroke();

  // Live endpoint dot
  const lastNorm = THREE.MathUtils.clamp((distMm - 285) / 48, 0, 1);
  const ly = h - 6 - lastNorm * (h - 12);
  scopeCtx.fillStyle = '#b8dc56';
  scopeCtx.beginPath();
  scopeCtx.arc(w - 2, ly, 3.2, 0, Math.PI * 2);
  scopeCtx.fill();

  hydDistEl.textContent = `${distMm.toFixed(1)} mm`;
}

// ============================================================================
// 10. MAIN 60 FPS ANIMATION & SIMULATION LOOP
// ============================================================================
const clock = new THREE.Clock();
let totalTime = 0;

function animate() {
  requestAnimationFrame(animate);
  const rawDt = Math.min(clock.getDelta(), 0.05);
  const dt = state.playing ? rawDt * state.speed : 0;
  totalTime += rawDt;

  // --- WASD Interactive Drive Kinematics (Zero-Slip 3D Turning + Free-Orbit Translating Follow Cam!) ---
  let curVel = 0;
  let curOmega = 0;
  if (state.driveMode) {
    const fwd = (keys.has('w') || keys.has('arrowup') ? 1 : 0) - (keys.has('s') || keys.has('arrowdown') ? 1 : 0);
    const turn = (keys.has('a') || keys.has('arrowleft') ? 1 : 0) - (keys.has('d') || keys.has('arrowright') ? 1 : 0);
    const fast = keys.has('shift');

    if (!state.driveOverrideAction) {
      if (fwd > 0) {
        const targetAct = fast ? 'Trot_Cycle' : 'Walk_Cycle';
        switchAction(targetAct, 0.22);
        curVel = (fast ? TROT_VEL : WALK_VEL) * state.speed;
      } else if (fwd < 0) {
        // Reverse: ALWAYS careful Walk_Back — throttle/trot is strictly disabled while backing up!
        switchAction('Walk_Back', 0.22);
        curVel = -BACK_VEL * state.speed;
      } else if (turn > 0) {
        switchAction('Turn_Left', 0.18);
      } else if (turn < 0) {
        switchAction('Turn_Right', 0.18);
      } else {
        switchAction('Idle_Scan', 0.28);
      }
    }

    // Exact zero-slip angular velocity during in-place pivot turn (TURN_OMEGA = 0.4286 rad/s)!
    // Gentle realistic steering arc during forward/reverse movement
    if (fwd === 0 && turn !== 0) {
      curOmega = turn * TURN_OMEGA * state.speed;
    } else if (fwd > 0 && turn !== 0) {
      curOmega = turn * (fast ? 0.72 : 0.48) * state.speed;
    } else if (fwd < 0 && turn !== 0) {
      curOmega = -turn * 0.42 * state.speed;
    }

    const prevPos = state.pos.clone();
    state.yaw += curOmega * rawDt;
    const moveStep = curVel * rawDt;
    state.pos.x += Math.cos(state.yaw) * moveStep;
    state.pos.z -= Math.sin(state.yaw) * moveStep;
    resolveEnvCollisions(state.pos);

    robotRoot.position.copy(state.pos);
    robotRoot.rotation.y = state.yaw;

    // Translate camera smoothly WITH robot movement WITHOUT whipping or crossing the center pole!
    const deltaPos = state.pos.clone().sub(prevPos);
    camera.position.add(deltaPos);
    controls.target.lerp(new THREE.Vector3(state.pos.x, 0.50, state.pos.z), 0.18);
    // Gentle spherical azimuth behind-alignment when moving forward (NEVER linear lerp through robot center!)
    if (fwd > 0 && !controls._dragging) {
      const off = camera.position.clone().sub(controls.target);
      const horizR = Math.hypot(off.x, off.z);
      if (horizR > 0.25) {
        const curAz = Math.atan2(off.z, off.x);
        const behindAz = Math.atan2(Math.sin(state.yaw), -Math.cos(state.yaw));
        const dAz = Math.atan2(Math.sin(behindAz - curAz), Math.cos(behindAz - curAz));
        const newAz = curAz + dAz * (1.0 - Math.exp(-rawDt * 0.85));
        const targetR = THREE.MathUtils.lerp(horizR, THREE.MathUtils.clamp(horizR, 1.9, 3.1), 0.04);
        camera.position.x = controls.target.x + Math.cos(newAz) * targetR;
        camera.position.z = controls.target.z + Math.sin(newAz) * targetR;
      }
    }
    updateSunPosition();
  } else {
    // Treadmill exact zero-slip floor scrolling (Studio Grid) OR in-world rotation (Conservatory)
    if (state.playing && activeClipName === 'Walk_Cycle') {
      curVel = WALK_VEL * state.speed;
      if (state.world === 'studio') {
        floorMat.map.offset.x = (floorMat.map.offset.x + curVel * rawDt) % 1.0;
      }
    } else if (state.playing && activeClipName === 'Walk_Back') {
      curVel = -BACK_VEL * state.speed;
      if (state.world === 'studio') {
        floorMat.map.offset.x = (floorMat.map.offset.x + curVel * rawDt + 1.0) % 1.0;
      }
    } else if (state.playing && activeClipName === 'Trot_Cycle') {
      curVel = TROT_VEL * state.speed;
      if (state.world === 'studio') {
        floorMat.map.offset.x = (floorMat.map.offset.x + curVel * rawDt) % 1.0;
      }
    } else if (state.playing && activeClipName === 'Turn_Left') {
      curOmega = TURN_OMEGA * state.speed;
      if (state.world === 'studio') {
        worldGroup.rotation.y -= curOmega * rawDt;
      } else {
        state.yaw += curOmega * rawDt;
        robotRoot.rotation.y = state.yaw;
      }
    } else if (state.playing && activeClipName === 'Turn_Right') {
      curOmega = -TURN_OMEGA * state.speed;
      if (state.world === 'studio') {
        worldGroup.rotation.y -= curOmega * rawDt;
      } else {
        state.yaw += curOmega * rawDt;
        robotRoot.rotation.y = state.yaw;
      }
    }
  }
  velEl.textContent = Math.abs(curOmega) > 0.01 && Math.abs(curVel) < 0.01
    ? `${THREE.MathUtils.radToDeg(curOmega).toFixed(1)}°/s`
    : `${curVel.toFixed(3)} m/s`;

  // Restore clean pre-layered bone quaternions BEFORE mixer.update() so procedural deltas
  // NEVER compound or confuse Three.js PropertyMixer during crossfades or 0-dt frames!
  for (const bname in preLayerQuats) {
    if (bonesByName[bname]) {
      bonesByName[bname].quaternion.copy(preLayerQuats[bname]);
    }
  }
  preLayerQuats = {};

  // Update AnimationMixer
  if (mixer) {
    mixer.update(dt);
  }

  // Helper: cleanly layer a local-axis delta while saving the raw mixer quaternion first
  const applyLocalAxisDelta = (bname, axisKey, rad) => {
    const b = bonesByName[bname];
    const ax = boneLocalAxes[bname]?.[axisKey];
    if (!b || !ax) return;
    if (!preLayerQuats[bname]) preLayerQuats[bname] = b.quaternion.clone();
    tmpQ2.setFromAxisAngle(ax, rad);
    b.quaternion.multiply(tmpQ2).normalize();
  };

  // --- Real-Time Curved-Turn Locomotion Layering (fixes W+A / W+D / S+A / S+D turning!) ---
  const isMovingCurve = state.driveMode && Math.abs(curVel) > 0.01 && Math.abs(curOmega) > 0.01;
  const targetSteer = isMovingCurve ? THREE.MathUtils.clamp(curOmega / 0.55, -1.2, 1.2) : 0.0;
  smoothSteer += (targetSteer - smoothSteer) * (1.0 - Math.exp(-rawDt * 9.0));

  if (Math.abs(smoothSteer) > 0.004 && boneLocalAxes['B_torso']) {
    // 1. Head & neck look smoothly into the turn (+around UP = left turn!)
    applyLocalAxisDelta('B_neck', 'up', smoothSteer * 0.22);
    applyLocalAxisDelta('B_head', 'up', smoothSteer * 0.28);

    // 2. Athletic torso bank roll into the curve (-around FWD leans top toward left!)
    const bankRad = -smoothSteer * (activeClipName === 'Trot_Cycle' ? 0.11 : 0.065);
    applyLocalAxisDelta('B_torso', 'fwd', bankRad);

    // 3. Phase-locked lateral hip abduction sidestepping on all 4 legs!
    const act = activeClipName ? actions[activeClipName] : null;
    const dur = act ? act.getClip().duration : 1.0;
    const phase = act ? ((act.time % dur) / dur) : 0.0;
    const isTrot = activeClipName === 'Trot_Cycle';
    const duty = isTrot ? 0.56 : 0.75;

    const lateralWave = (ph) => {
      const p = ((ph % 1.0) + 1.0) % 1.0;
      if (p < duty) {
        return 0.5 - p / duty;
      }
      const u = (p - duty) / (1.0 - duty);
      const s = u * u * u * (10 + u * (-15 + 6 * u));
      return -0.5 + s;
    };

    const phFL = isTrot ? phase : (phase - 0.25);
    const phFR = isTrot ? (phase - 0.5) : (phase - 0.75);
    const phRL = isTrot ? (phase - 0.5) : phase;
    const phRR = isTrot ? phase : (phase - 0.50);

    const latAmp = 0.14 * smoothSteer;
    applyLocalAxisDelta('B_FL_ab', 'fwd', -bankRad + latAmp * lateralWave(phFL));
    applyLocalAxisDelta('B_FR_ab', 'fwd', -bankRad + latAmp * lateralWave(phFR));
    applyLocalAxisDelta('B_RL_ab', 'fwd', -bankRad - latAmp * lateralWave(phRL));
    applyLocalAxisDelta('B_RR_ab', 'fwd', -bankRad - latAmp * lateralWave(phRR));
  }

  // Live Solar Canopy Sun-Tracking Override (C-infinity wrap-free + preserves rest quaternion!)
  if (state.sunTrack && bonesByName['B_canopy_yaw'] && bonesByName['B_canopy_pitch'] && restQuats['B_canopy_yaw']) {
    const sunWorldYaw = -THREE.MathUtils.degToRad(state.sunAzDeg);
    const relYaw = sunWorldYaw - state.yaw;
    // Continuous smooth periodic mapping (zero +-PI discontinuity when circling 360 degrees!)
    const targetYaw = Math.sin(relYaw) * 0.92;
    const targetPitch = THREE.MathUtils.clamp(THREE.MathUtils.degToRad(42 - state.sunElDeg) * 0.45, -0.32, 0.32);

    const k = 1.0 - Math.exp(-rawDt * 6.0);
    smoothCanopyYaw += (targetYaw - smoothCanopyYaw) * k;
    smoothCanopyPitch += (targetPitch - smoothCanopyPitch) * k;

    if (!preLayerQuats['B_canopy_yaw']) preLayerQuats['B_canopy_yaw'] = bonesByName['B_canopy_yaw'].quaternion.clone();
    if (!preLayerQuats['B_canopy_pitch']) preLayerQuats['B_canopy_pitch'] = bonesByName['B_canopy_pitch'].quaternion.clone();

    tmpQ.setFromAxisAngle(AXIS_Y, smoothCanopyYaw);
    bonesByName['B_canopy_yaw'].quaternion.copy(restQuats['B_canopy_yaw']).multiply(tmpQ).normalize();
    tmpQ.setFromAxisAngle(AXIS_Z, smoothCanopyPitch);
    bonesByName['B_canopy_pitch'].quaternion.copy(restQuats['B_canopy_pitch']).multiply(tmpQ).normalize();
  }

  // Smooth Exploded Assembly interpolation
  for (let i = 0; i < explodeData.length; i++) {
    const d = explodeData[i];
    if (state.explode > 0.001) {
      d.mesh.position.copy(d.basePos).addScaledVector(d.dir, d.dist * state.explode);
    } else {
      d.mesh.position.copy(d.basePos);
    }
  }

  // Keep canopy PointLight anchored beneath the moving solar canopy
  if (bonesByName['B_canopy_pitch']) {
    bonesByName['B_canopy_pitch'].getWorldPosition(tmpV3);
    growLight.position.set(tmpV3.x, tmpV3.y + 0.14, tmpV3.z);
  }

  // Live hydraulic piston distance measurement + oscilloscope
  if (bonesByName['B_FL_hyd_cyl'] && bonesByName['B_FL_hyd_rod']) {
    bonesByName['B_FL_hyd_cyl'].getWorldPosition(tmpV1);
    bonesByName['B_FL_hyd_rod'].getWorldPosition(tmpV2);
    const distMm = tmpV1.distanceTo(tmpV2) * 1000.0;
    drawHydraulicScope(distMm);
  }

  // Synced procedural servo hum & footstep audio ticks
  if (state.soundOn && audioCtx && servoGain && mixer && activeClipName) {
    const targetGain = state.playing ? (Math.abs(curVel) > 0.01 ? 0.025 : 0.010) : 0.0;
    servoGain.gain.setTargetAtTime(targetGain, audioCtx.currentTime, 0.08);
    servoOsc.frequency.setTargetAtTime(125 + Math.abs(curVel) * 240, audioCtx.currentTime, 0.08);
    if (state.playing && ['Walk_Cycle', 'Walk_Back', 'Trot_Cycle', 'Turn_Left', 'Turn_Right'].includes(activeClipName)) {
      const act = actions[activeClipName];
      const dur = act.getClip().duration;
      const stepsPerCycle = (activeClipName === 'Walk_Cycle' || activeClipName === 'Walk_Back') ? 4 : 2;
      const stepIdx = Math.floor(((act.time % dur) / dur) * stepsPerCycle);
      if (stepIdx !== lastStepIndex) {
        lastStepIndex = stepIdx;
        playFootstepTick(activeClipName === 'Trot_Cycle' ? 0.09 : 0.06);
      }
    }
  }

  // Advance live conservatory sky cloud drift, water ripples & foliage breeze!
  skyUniforms.uTime.value = totalTime;
  envAnimUniforms.uTime.value = totalTime;

  // Interactive Conservatory Botanical Stations, Blooming Blossoms & Sparkling Water Mist!
  const promptEl = document.getElementById('station-prompt');
  if (state.world === 'conservatory' && stationVisuals.length > 0) {
    let promptText = '';
    for (const sv of stationVisuals) {
      // Gentle beacon pulse for beds awaiting misting
      if (!sv.bloomed) {
        const s = 0.92 + 0.14 * Math.sin(totalTime * 3.2);
        sv.beaconRing.scale.setScalar(s);
      } else {
        sv.beaconRing.scale.setScalar(1.0);
        if (sv.bloomProg < 1.0) {
          sv.bloomProg = Math.min(1.0, sv.bloomProg + rawDt * 1.15);
          const sc = sv.bloomProg * sv.bloomProg * (3 - 2 * sv.bloomProg);
          for (const fl of sv.blossoms) {
            fl.scale.setScalar(Math.max(0.001, sc));
            fl.rotation.y += rawDt * 0.9;
          }
        }
      }
      if (state.driveMode) {
        const d = Math.hypot(state.pos.x - sv.data.center[0], state.pos.z - sv.data.center[2]);
        if (d < sv.data.radius + 1.15) {
          promptText = sv.bloomed
            ? `${sv.data.label} · THRIVING  ·  [E] MIST AGAIN`
            : `[E] INSPECT & MIST · ${sv.data.label}`;
        }
      }
    }
    if (!promptText && state.driveMode && envMeta?.dock) {
      const dd = Math.hypot(state.pos.x - envMeta.dock.center[0], state.pos.z - envMeta.dock.center[2]);
      if (dd < envMeta.dock.radius) {
        promptText = 'NORTH SOLAR DOCK ALIGNED · CHARGING & HYDRATION SYNC';
      }
    }
    if (promptEl) {
      if (promptText) {
        promptEl.textContent = promptText;
        promptEl.classList.remove('hidden');
      } else {
        promptEl.classList.add('hidden');
      }
    }
  } else if (promptEl) {
    promptEl.classList.add('hidden');
  }

  // Update sparkling water-mist particle burst
  if (mistLife > 0) {
    mistLife = Math.max(0, mistLife - rawDt);
    mistMat.opacity = (mistLife / 1.6) * 0.82;
    const mAttr = mistGeo.attributes.position;
    for (let i = 0; i < MIST_N; i++) {
      mistVel[i].y -= 1.35 * rawDt;
      mAttr.setXYZ(
        i,
        mAttr.getX(i) + mistVel[i].x * rawDt,
        Math.max(0.04, mAttr.getY(i) + mistVel[i].y * rawDt),
        mAttr.getZ(i) + mistVel[i].z * rawDt
      );
    }
    mAttr.needsUpdate = true;
  }

  // Gentle sunlit floating pollen motes drift
  const posAttr = moteGeo.attributes.position;
  for (let i = 0; i < moteCount; i++) {
    let y = posAttr.getY(i) + rawDt * 0.035;
    if (y > 2.35) y = 0.25;
    posAttr.setY(i, y);
  }
  posAttr.needsUpdate = true;

  // Smooth camera preset transition
  if (state.camLerp) {
    state.camLerp.t = Math.min(1, state.camLerp.t + rawDt * 2.4);
    const e = state.camLerp.t * state.camLerp.t * (3 - 2 * state.camLerp.t);
    camera.position.lerpVectors(state.camLerp.p0, state.camLerp.p1, e);
    controls.target.lerpVectors(state.camLerp.t0, state.camLerp.t1, e);
    if (state.camLerp.t >= 1) state.camLerp = null;
  }

  controls.update();
  composer.render();
}

loadAssets();
animate();
