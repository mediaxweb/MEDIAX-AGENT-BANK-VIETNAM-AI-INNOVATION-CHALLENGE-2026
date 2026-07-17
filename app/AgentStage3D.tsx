"use client";

import { Check, Clock3, LoaderCircle, ShieldCheck, UserCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

type StageMode = "builder" | "run";

type AgentStage3DProps = {
  mode: StageMode;
  selected?: string;
  onSelect?: (id: string) => void;
  runStep?: number;
  compact?: boolean;
};

const team = [
  { id: "orchestrator", name: "Điều phối viên AI", color: "#8b5cf6" },
  { id: "credit", name: "Chuyên gia tín dụng", color: "#1677ff" },
  { id: "compliance", name: "Chuyên gia tuân thủ", color: "#f59e0b" },
  { id: "operations", name: "Chuyên gia vận hành", color: "#22c55e" },
];

function getState(index: number, mode: StageMode, runStep: number) {
  if (mode === "run") return index < 2 ? "done" : index === 2 ? "running" : "waiting";
  const step = [1, 2, 2, 3][index];
  if (!runStep) return "ready";
  if (runStep > step) return "done";
  if (runStep === step) return "running";
  return "waiting";
}

export default function AgentStage3D({ mode, selected = "credit", onSelect, runStep = 0, compact = false }: AgentStage3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const animationRef = useRef<Record<string, { mixer: THREE.AnimationMixer; clips: THREE.AnimationClip[] }>>({});
  const ringsRef = useRef<Record<string, THREE.Mesh>>({});
  const stateRef = useRef({ mode, selected, runStep });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => { stateRef.current = { mode, selected, runStep }; }, [mode, selected, runStep]);

  useEffect(() => {
    const host = mountRef.current;
    if (!host) return;
    let disposed = false;
    let frame = 0;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x07111f, 0.045);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0, compact ? 3.4 : 4.3, compact ? 8.7 : 9.8);
    camera.lookAt(0, 1, 0);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xbddcff, 0x07111f, 2.2));
    const key = new THREE.DirectionalLight(0xffffff, 3.4);
    key.position.set(-4, 7, 5);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x5fa6ff, 2.2);
    rim.position.set(5, 3, -4);
    scene.add(rim);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(6.2, 64),
      new THREE.MeshStandardMaterial({ color: 0x0c192b, metalness: 0.35, roughness: 0.76, transparent: true, opacity: 0.95 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.02;
    scene.add(floor);
    const grid = new THREE.GridHelper(11, 22, 0x27496d, 0x162b43);
    grid.position.y = 0.005;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.45;
    scene.add(grid);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const characterRoots: THREE.Object3D[] = [];
    const positions = compact
      ? [[-2.55, 0.35], [-0.85, -0.2], [0.85, -0.2], [2.55, 0.35]]
      : [[-3.15, 0.55], [-1.05, -0.35], [1.05, -0.35], [3.15, 0.55]];

    const loader = new GLTFLoader();
    const draco = new DRACOLoader();
    draco.setDecoderPath("/vendor/draco/");
    loader.setDRACOLoader(draco);
    loader.load("/models/character.glb", (gltf) => {
      if (disposed) return;
      team.forEach((agent, index) => {
        const root = clone(gltf.scene);
        const box = new THREE.Box3().setFromObject(root);
        const height = Math.max(box.max.y - box.min.y, 0.01);
        const scale = (compact ? 1.62 : 1.85) / height;
        root.scale.setScalar(scale);
        const normalized = new THREE.Box3().setFromObject(root);
        root.position.set(positions[index][0], -normalized.min.y, positions[index][1]);
        root.rotation.y = index < 2 ? 0.14 : -0.14;
        root.userData.agentId = agent.id;
        root.traverse((part: any) => {
          part.userData.agentId = agent.id;
          if (part.isMesh) {
            part.castShadow = true;
            part.material = part.material.clone();
            if (part.material.color && /shirt|body|top|sweater/i.test(part.name)) part.material.color.lerp(new THREE.Color(agent.color), 0.55);
          }
        });
        scene.add(root);
        characterRoots.push(root);

        const mixer = new THREE.AnimationMixer(root);
        animationRef.current[agent.id] = { mixer, clips: gltf.animations };
        const idle = gltf.animations.find((clip) => clip.name === "Idle") || gltf.animations[0];
        if (idle) mixer.clipAction(idle).play();

        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.48, 0.58, 36),
          new THREE.MeshBasicMaterial({ color: agent.color, transparent: true, opacity: 0.25, side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI / 2;
        ring.position.set(positions[index][0], 0.018, positions[index][1]);
        scene.add(ring);
        ringsRef.current[agent.id] = ring;
      });
      setLoading(false);
    }, undefined, () => { if (!disposed) { setLoading(false); setLoadError(true); } });

    function resize() {
      if (!host) return;
      const width = host.clientWidth;
      const height = host.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    }
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();

    function handlePointer(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(characterRoots, true)[0];
      const id = hit?.object.userData.agentId;
      if (id && onSelect) onSelect(id);
    }
    renderer.domElement.addEventListener("pointerup", handlePointer);

    const clock = new THREE.Clock();
    function animate() {
      const delta = Math.min(clock.getDelta(), 0.05);
      Object.entries(animationRef.current).forEach(([id, item]) => {
        item.mixer.update(delta);
        const index = team.findIndex((agent) => agent.id === id);
        const status = getState(index, stateRef.current.mode, stateRef.current.runStep);
        const wanted = status === "running" ? "Talk" : status === "done" ? "Happy" : id === stateRef.current.selected ? "Wave" : "Idle";
        const current = (item.mixer as any)._mediaxClip;
        if (current !== wanted) {
          item.mixer.stopAllAction();
          const clip = item.clips.find((candidate) => candidate.name === wanted) || item.clips.find((candidate) => candidate.name === "Idle") || item.clips[0];
          if (clip) item.mixer.clipAction(clip).reset().fadeIn(0.25).play();
          (item.mixer as any)._mediaxClip = wanted;
        }
      });
      Object.entries(ringsRef.current).forEach(([id, ring]) => {
        const active = id === stateRef.current.selected;
        (ring.material as THREE.MeshBasicMaterial).opacity = active ? 0.9 : 0.22;
        const pulse = active ? 1 + Math.sin(performance.now() * 0.004) * 0.08 : 1;
        ring.scale.setScalar(pulse);
      });
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    }
    animate();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerup", handlePointer);
      draco.dispose();
      animationRef.current = {};
      ringsRef.current = {};
      scene.traverse((object: any) => {
        object.geometry?.dispose?.();
        if (Array.isArray(object.material)) object.material.forEach((material: THREE.Material) => material.dispose());
        else object.material?.dispose?.();
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [compact, onSelect]);

  return <div className={`agent-stage-3d ${compact ? "compact" : ""}`}>
    <div ref={mountRef} className="agent-stage-canvas" aria-label="Đội chuyên gia AI dạng 3D" />
    {loading && <div className="agent-stage-loading"><LoaderCircle className="spinning" /><span>Đang chuẩn bị đội chuyên gia 3D...</span></div>}
    {loadError && <div className="agent-stage-loading"><span>Không thể tải mô hình 3D</span></div>}
    <div className="agent-stage-legend">
      {team.map((agent, index) => {
        const status = getState(index, mode, runStep);
        return <button key={agent.id} className={selected === agent.id ? "selected" : ""} onClick={() => onSelect?.(agent.id)}>
          <i style={{ background: agent.color }} />
          <span><strong>{agent.name}</strong><small>{status === "running" ? "Đang xử lý" : status === "done" ? "Hoàn thành" : status === "waiting" ? "Đang chờ" : "Sẵn sàng"}</small></span>
          {status === "done" ? <Check /> : status === "running" ? <LoaderCircle className="spinning" /> : <Clock3 />}
        </button>;
      })}
    </div>
    {!compact && <div className="approval-gate"><ShieldCheck /><span><strong>Bước kiểm soát cuối</strong><small>Mọi quyết định đều cần chuyên viên phê duyệt</small></span><UserCheck /></div>}
    <a className="agent-stage-credit" href="https://unboring.net" target="_blank" rel="noreferrer">Mô hình 3D: Arturo Paracuellos · CC BY-NC 4.0</a>
  </div>;
}
